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

# Import config from the hscode_api directory
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
hscode_api_dir = os.path.dirname(current_dir)
sys.path.insert(0, hscode_api_dir)

from config import (
    OPENROUTER_API_KEY, OPENROUTER_MODELS, OPENROUTER_CONFIG
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

def chat_completion(messages, model_alias="mistral_small", api_key=None):
    # Use OpenRouter for single model classification
    return call_llm(
        messages, model_alias,
        OPENROUTER_CONFIG, OPENROUTER_MODELS,
        api_key or OPENROUTER_API_KEY
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

VEHICLE_DETECTION_PROMPT = """
You are an expert product classifier. Decide if the given product name refers to a motor vehicle (cars, SUVs, pickups, vans, trucks, buses, special-purpose road vehicles). Return exactly one word:

- vehicle  → if it is a motor vehicle
- non-vehicle → otherwise

Product name: {product_name}
Answer:
""".strip()

VEHICLE_INFO_TEMPLATE = """
For the {product_name}, provide the following information in JSON format:

- vehicle: the full vehicle name
- vehicle_type: the category (e.g., sedan, SUV, truck, coupe, etc.)
- propulsion_type: the propulsion system (e.g., internal combustion engine, electric, hybrid, plug-in hybrid)
- engine_options: an array of all available engine/motor configurations, each with:
  - type: engine/motor description (e.g., "2.0L I4 Turbo")
  - displacement_cc: engine displacement in cubic centimeters (for combustion engines)
  - notes: additional context (e.g., "Standard", "Optional", "Performance trim")

Example:
{{
  "vehicle": "2024 Honda Accord",
  "vehicle_type": "Midsize sedan",
  "propulsion_type": "Internal combustion engine",
  "engine_options": [
    {{
      "type": "1.5L I4 Turbo",
      "displacement_cc": 1500,
      "notes": "Standard engine"
    }},
    {{
      "type": "2.0L I4 Turbo",
      "displacement_cc": 2000,
      "notes": "Sport trim only"
    }}
  ]
}}

Format the response as valid JSON only, with no additional text.
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
        gather_model: str = "gpt_5_mini",
        class_models: Optional[List[str]] = None,
        api_key: Optional[str] = None,
    ):
        api_key = api_key or OPENROUTER_API_KEY
        self.gather_client = LLMClient(gather_model, api_key)
        self.class_clients = {
            m: LLMClient(m, api_key) for m in (class_models or list(OPENROUTER_MODELS))
        }
        self.product_information = ""  # To expose the collected information
    def _extract_vehicle_details_from_context(self, product_name: str, contextual_data: Dict[str, Any] = None) -> str:
        """
        Extract complete vehicle details from contextual_data (extracted from documents).
        Falls back to product_name if no contextual data available.
        """
        if not contextual_data:
            return product_name.strip()
        
        # Try to extract vehicle details from various sources in contextual_data
        vehicle_details = None
        
        # Check for vehicle info in product_details
        if 'product_details' in contextual_data and contextual_data['product_details']:
            product_details = contextual_data['product_details']
            if isinstance(product_details, dict):
                # Look for year, make, model in product_details
                year = product_details.get('year') or product_details.get('model_year')
                make = product_details.get('make') or product_details.get('manufacturer')
                model = product_details.get('model') or product_details.get('vehicle_model')
                
                if year and make and model:
                    vehicle_details = f"{year} {make} {model}"
        
        # Check for vehicle info in commodity field
        if not vehicle_details and 'commodity' in contextual_data:
            commodity = contextual_data['commodity']
            if commodity and isinstance(commodity, str):
                # Look for year pattern in commodity description
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', commodity)
                if year_match:
                    vehicle_details = commodity.strip()
        
        # Check for vehicle info in buyer_info or supplier_info
        if not vehicle_details:
            for info_key in ['buyer_info', 'supplier_info']:
                if info_key in contextual_data and contextual_data[info_key]:
                    info = contextual_data[info_key]
                    if isinstance(info, dict):
                        # Look for vehicle description in various fields
                        for field in ['description', 'product_description', 'item_description']:
                            if field in info and info[field]:
                                desc = info[field]
                                if isinstance(desc, str) and any(word in desc.lower() for word in ['vehicle', 'car', 'truck', 'suv', 'sedan']):
                                    vehicle_details = desc.strip()
                                    break
                        if vehicle_details:
                            break
        
        # Return the best vehicle details found, or fall back to product_name
        return vehicle_details if vehicle_details else product_name.strip()

    def collect_information(self, product_name: str, contextual_data: Dict[str, Any] = None) -> str:
        """Prompt 1: Collect product information using gather model."""
        # Primary detection: ask the LLM if this is a motor vehicle (with backup model)
        is_vehicle = False
        detection_prompt = VEHICLE_DETECTION_PROMPT.format(product_name=product_name)
        logger.info("🔍 VEHICLE DETECTION: Starting detection for '%s'", product_name)
        
        try:
            detection_answer = self.gather_client.chat("Vehicle detection", detection_prompt).strip().lower()
            logger.info("🔍 VEHICLE DETECTION: Primary model response: '%s'", detection_answer)
        except Exception as e:
            logger.error("🔍 VEHICLE DETECTION: Primary model failed: %s", str(e))
            detection_answer = ""

        if detection_answer not in ("vehicle", "non-vehicle"):
            # Backup detection using a secondary model
            logger.info("🔍 VEHICLE DETECTION: Primary response invalid, trying backup model")
            try:
                backup_client = LLMClient("gpt_5_nano")
                detection_answer = backup_client.chat("Vehicle detection", detection_prompt).strip().lower()
                logger.info("🔍 VEHICLE DETECTION: Backup model response: '%s'", detection_answer)
            except Exception as e:
                logger.error("🔍 VEHICLE DETECTION: Backup model failed: %s", str(e))
                detection_answer = "non-vehicle"

        is_vehicle = detection_answer.startswith("vehicle")
        logger.info("🔍 VEHICLE DETECTION: Final decision - is_vehicle: %s", is_vehicle)

        if is_vehicle:
            # Extract complete vehicle details from contextual_data (extracted from documents)
            formatted_vehicle_name = self._extract_vehicle_details_from_context(product_name, contextual_data)
            prompt = VEHICLE_INFO_TEMPLATE.format(product_name=formatted_vehicle_name)
            logger.info("Collecting VEHICLE-SPECIFIC information for: %s using %s", formatted_vehicle_name, self.gather_client.model_name)
        else:
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
    def run(self, product_name: str, contextual_data: Dict[str, Any] = None) -> Dict[str, HSCodeResult]:
        """Run the full two-stage classification pipeline."""
        # Stage 1: Collect information
        product_information = self.collect_information(product_name, contextual_data)
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
    parser.add_argument("--gather-model", default="gpt_5_mini",
                       help="Model for collecting product info (default: gpt_5_mini)")
    parser.add_argument("--class-models", 
                       help="Comma-separated list of models for classification (default: all)")
    parser.add_argument("--output", type=str, help="Output JSON file")
    return parser.parse_args()

def classify_product(product_name: str, contextual_data: Dict[str, Any] = None) -> dict:
    """Main entry point for classification."""
    try:
        classifier = HSCodeClassifier()
        results = classifier.run(product_name, contextual_data)
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
        
    except Exception as e:
        logger.error("Error in classify_product: %s", str(e))
        import traceback
        traceback.print_exc()
        
        # Return error result instead of None
        return {
            "product": product_name,
            "hs_codes": "Error",
            "product_information": f"Error occurred during classification: {str(e)}",
            "model_responses": {},
            "consensus_codes": [],
            "error": str(e)
        }

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