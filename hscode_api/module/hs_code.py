#!/usr/bin/env python3
"""
HS Code Classifier
A Python script that determines 6-digit Harmonized System codes for products
using a two-stage pipeline with multiple AI models.
"""

import os
import re
import json
import sys
import time
import logging
import argparse
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import requests
from requests.exceptions import RequestException

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    OPENROUTER_API_KEY, OPENROUTER_MODELS, OPENROUTER_CONFIG,
    GROQ_MODELS, GROQ_CONFIG, GROQ_API_KEY, MODEL_FALLBACK_MAP
)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("HSClassifier")

# ── LLM Helper ─────────────────────────────────────────────────────────────
def call_llm(messages, model_alias, config, models, api_key=None):
    model = models[model_alias]["name"]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": models[model_alias].get("temperature", 0.7),
        "max_tokens": models[model_alias].get("max_tokens", 1000),
    }
    headers = dict(config["headers"])
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(
        config["api_url"],
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]

def chat_completion(messages, model_alias="gpt4", api_key=None):
    # ① try OpenRouter
    try:
        return call_llm(
            messages, model_alias,
            OPENROUTER_CONFIG, OPENROUTER_MODELS,
            api_key or OPENROUTER_API_KEY
        )
    except Exception as err:
        logging.warning("OpenRouter error → %s – falling back to Groq", err)

        # ② choose a Groq-compatible alias
        groq_alias = MODEL_FALLBACK_MAP.get(model_alias, model_alias)
        if groq_alias not in GROQ_MODELS:
            groq_alias = "llama3_70b"          # last-resort default

        # ✅ new line – tells you which Groq model is actually used
        logging.info("Classifying with %s via Groq (%s)", model_alias, groq_alias)

        # ③ call Groq with the correct key
        return call_llm(
            messages, groq_alias,
            GROQ_CONFIG, GROQ_MODELS,
            api_key=os.getenv("GROQ_API_KEY", GROQ_API_KEY)
        )

# ── Prompt templates ───────────────────────────────────────────────────────
COLLECT_INFO_TEMPLATE = """
You are a sourcing expert. Based on the available data for **{product_name}**, answer the
following questions. If a detail is unknown, reply **Unknown**—do **not** guess.

1. What is the principal material or composition?
2. What is the product's primary function or use?
3. Is it packaged for retail sale or bulk?
4. Does it contain electrical or mechanical components?
5. Is it fresh, dried, frozen, or otherwise processed?

Return your answers as a bullet list, one bullet per question, in the same order,
with no additional commentary, JSON, or numbering.
""".strip()

CLASSIFICATION_TEMPLATE = """
You are an expert customs broker. Determine the 6-digit HS code for **{product_name}**.

Product data:
{product_information}

CRITICAL INSTRUCTIONS:
- Output EXACTLY 6 digits
- NO text before or after
- NO explanations
- NO formatting
- ONLY the 6 digits

WRONG: "The HS code is 080390"
WRONG: "080390 - Bananas"
WRONG: "Based on analysis... 080390"
RIGHT: 080390

OUTPUT:""".strip()

# ── Data class ─────────────────────────────────────────────────────────────
@dataclass
class HSCodeResult:
    product_name: str
    hs_code: str
    model_name: str
    confidence: float = 1.0

# ── Helper class ───────────────────────────────────────────────────────────
class LLMClient:
    """Generic LLM client with OpenRouter→Groq fallback."""
    def __init__(self, model_name: str, api_key: str = None):
        self.model_name = model_name
        self.api_key = api_key or OPENROUTER_API_KEY
    def chat(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return chat_completion(messages, model_alias=self.model_name, api_key=self.api_key)

# ── Classifier ─────────────────────────────────────────────────────────────
class HSCodeClassifier:
    """Runs Prompt 1 once (with gather-model), then Prompt 2 on each classification model."""
    def __init__(
        self,
        gather_model: str = "gpt4",
        class_models: Optional[List[str]] = None,
        api_key: Optional[str] = None,
    ):
        api_key = api_key or OPENROUTER_API_KEY
        self.gather_client = LLMClient(gather_model, api_key)
        self.class_clients = {
            m: LLMClient(m, api_key) for m in (class_models or list(OPENROUTER_MODELS))
        }
        self.product_information = ""  # To expose the collected information
    def collect_information(self, product_name: str) -> str:
        """Prompt 1: Collect product information using gather model."""
        prompt = COLLECT_INFO_TEMPLATE.format(product_name=product_name)
        logger.info("Collecting information for: %s using %s", product_name, self.gather_client.model_name)
        try:
            answer_block = self.gather_client.chat("Information collector", prompt)
            if not answer_block:
                raise RuntimeError("Prompt 1 returned empty response")
            logger.info("Product information collected:\n%s", answer_block)
            self.product_information = answer_block
            return answer_block
        except Exception as e:
            logger.error("Failed to collect information: %s", e)
            # Fallback information
            fallback = f"- Product name: {product_name}\n- Unable to collect detailed information"
            self.product_information = fallback
            return fallback
    def classify_with_model(self, client: LLMClient, product_name: str, 
                          product_information: str) -> Optional[str]:
        """Prompt 2: Classify using a specific model."""
        prompt = CLASSIFICATION_TEMPLATE.format(
            product_name=product_name,
            product_information=product_information,
        )
        try:
            logger.info("Classifying with %s", client.model_name)
            response = client.chat("Customs broker", prompt).strip()
            # Try to extract 6-digit code from response
            matches = re.findall(r'\b\d{6}\b', response)
            if matches:
                hs_code = matches[-1]  # Take the last one if multiple found
                logger.info("  %s returned: %s", client.model_name, hs_code)
                return hs_code
            else:
                logger.warning("  %s: No valid 6-digit code in response: %s", 
                             client.model_name, response[:100])
                return None
        except Exception as e:
            logger.error("  %s failed: %s", client.model_name, e)
            return None
    def calculate_consensus(self, results: Dict[str, HSCodeResult]) -> List[str]:
        """Calculate consensus from model outputs."""
        if not results:
            return []
        from collections import Counter
        hs_codes = [r.hs_code for r in results.values() if r.hs_code]
        code_counts = Counter(hs_codes)
        # Log consensus analysis
        logger.info("\nConsensus analysis:")
        for code, count in code_counts.most_common():
            logger.info("  %s: %d votes", code, count)
        # Sort by frequency (most common first)
        sorted_codes = [code for code, count in code_counts.most_common()]
        return sorted_codes
    def run(self, product_name: str) -> Dict[str, HSCodeResult]:
        """Run the full two-stage classification pipeline."""
        # Stage 1: Collect information
        product_information = self.collect_information(product_name)
        # Stage 2: Classify with each model
        results: Dict[str, HSCodeResult] = {}
        logger.info("\nClassifying based on collected information...")
        for name, client in self.class_clients.items():
            hs_code = self.classify_with_model(client, product_name, product_information)
            if hs_code:
                results[name] = HSCodeResult(
                    product_name=product_name,
                    hs_code=hs_code,
                    model_name=name,
                )
            # Small delay between models to avoid rate limiting
            time.sleep(0.5)
        return results

# ── Main functions ─────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HS Code Classifier – multi-model two-stage pipeline")
    parser.add_argument("product", type=str, help="Product name to classify")
    parser.add_argument("--gather-model", default="gpt4", 
                       help="Model for collecting product info (default: gpt4)")
    parser.add_argument("--class-models", 
                       help="Comma-separated list of models for classification (default: all)")
    parser.add_argument("--output", type=str, help="Output JSON file")
    return parser.parse_args()

def classify_product(product_name: str) -> dict:
    """Main entry point for classification."""
    classifier = HSCodeClassifier()
    results = classifier.run(product_name)
    hs_codes = classifier.calculate_consensus(results)
    
    # Build detailed output
    model_responses = {}
    for model_name, result in results.items():
        model_responses[model_name] = result.hs_code
    
    output = {
        "product": product_name,
        "hs_codes": ", ".join(hs_codes) if hs_codes else "No consensus",
        "product_information": classifier.product_information,
        "model_responses": model_responses,
        "consensus_codes": hs_codes
    }
    
    return output

def main():
    args = parse_args()
    product_name = args.product
    output_file = args.output
    
    # Parse class models if provided
    class_models = None
    if args.class_models:
        class_models = [m.strip() for m in args.class_models.split(",")]
    
    print(f"\n=== HS Code Classification for: {product_name} ===\n")
    
    # Create classifier with specified models
    classifier = HSCodeClassifier(
        gather_model=args.gather_model,
        class_models=class_models
    )
    
    try:
        results = classifier.run(product_name)
        hs_codes = classifier.calculate_consensus(results)
        
        # Build output
        model_responses = {}
        for model_name, result in results.items():
            model_responses[model_name] = result.hs_code
        
        output = {
            "product": product_name,
            "hs_codes": ", ".join(hs_codes) if hs_codes else "No consensus",
            "product_information": classifier.product_information,
            "model_responses": model_responses,
            "consensus_codes": hs_codes
        }
        
        # Save to file if requested
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)
            print(f"\nResults saved to: {output_file}")
        
        # Print results
        print("\n=== Final Results ===")
        print(json.dumps(output, indent=2))
        
    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()