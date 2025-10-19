#!/usr/bin/env python3
"""
eSAD Product Classification Module
Determines if products are commercial or personal using LLM analysis
"""

import json
import re
import os
import sys
from typing import Dict, List, Any, Optional

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from modules.core.llm_client import LLMClient

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Primary model for product classification - GPT-5 only
PRIMARY_MODEL = None
if "gpt_5" in OPENROUTER_GENERAL_MODELS:
    PRIMARY_MODEL = OPENROUTER_GENERAL_MODELS["gpt_5"]


def classify_product_commercial_vs_personal(invoice_data: Dict[str, Any], bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Classify if products are commercial or personal using LLM analysis."""
    
    # Extract product information
    products = []
    
    # From invoice items
    if 'items' in invoice_data and invoice_data['items']:
        for item in invoice_data['items']:
            products.append({
                'description': item.get('description', ''),
                'quantity': item.get('quantity', 0),
                'unit_price': item.get('unit_price', 0),
                'total_price': item.get('total_price', 0)
            })
    
    # From BOL cargo information
    if 'cargo_summary_table' in bol_data and bol_data['cargo_summary_table']:
        cargo_info = bol_data['cargo_summary_table']
        if isinstance(cargo_info, dict) and 'description' in cargo_info:
            products.append({
                'description': cargo_info['description'],
                'quantity': cargo_info.get('quantity', 0),
                'weight': cargo_info.get('weight', 0)
            })
    
    if not products:
        return {
            'product_classification': 'unknown',
            'reasoning': 'No product information found for classification'
        }
    
    # Use LLM to classify products
    classification_result = _classify_with_llm(products, verbose)
    
    return classification_result


def _classify_with_llm(products: List[Dict], verbose: bool = False) -> Dict[str, Any]:
    """Classify products using GPT-5 analysis."""
    
    if not PRIMARY_MODEL:
        if verbose:
            print("❌ GPT-5 model not available, using fallback classification")
        return _fallback_classification(products)
    
    # Create product summary for LLM
    product_summary = []
    for i, product in enumerate(products, 1):
        product_summary.append(f"Product {i}: {product['description']}")
        if product.get('quantity'):
            product_summary.append(f"  Quantity: {product['quantity']}")
        if product.get('unit_price'):
            product_summary.append(f"  Unit Price: ${product['unit_price']}")
        if product.get('total_price'):
            product_summary.append(f"  Total Price: ${product['total_price']}")
    
    products_text = "\n".join(product_summary)
    
    prompt = f"""
Analyze these products to determine if they are for COMMERCIAL or PERSONAL use:

{products_text}

Consider these factors:
- Product type and description
- Quantity (bulk quantities suggest commercial use)
- Unit prices (high unit prices may suggest commercial equipment)
- Total value
- Typical use patterns
- Scale context (e.g., household energy consumption patterns)

Return ONLY a JSON object:
{{
    "is_commercial": true or false,
    "confidence": "high" | "medium" | "low",
    "reasoning": "Brief explanation of the classification decision",
    "key_indicators": ["list", "of", "key", "factors"]
}}
"""

    try:
        response_text, success, error_type = llm.send_prompt(prompt, model=PRIMARY_MODEL)
        
        if not success:
            if verbose:
                print(f"❌ GPT-5 failed: {error_type}")
            return _fallback_classification(products)
        
        # Parse JSON response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            
            if verbose:
                print(f"🤖 GPT-5 result: {result}")
            
            # Convert is_commercial boolean to classification string
            classification = "commercial" if result.get('is_commercial', False) else "non-commercial"
            
            return {
                'product_classification': classification,
                'reasoning': result.get('reasoning', 'No reasoning provided')
            }
        else:
            if verbose:
                print("❌ GPT-5 response could not be parsed as JSON")
            return _fallback_classification(products)
            
    except Exception as e:
        if verbose:
            print(f"❌ GPT-5 exception: {e}")
        return _fallback_classification(products)


def _fallback_classification(products: List[Dict]) -> Dict[str, Any]:
    """Fallback classification using simple heuristics."""
    
    commercial_indicators = 0
    personal_indicators = 0
    
    for product in products:
        description = product.get('description', '').lower()
        quantity = product.get('quantity', 0)
        unit_price = product.get('unit_price', 0)
        
        # Commercial indicators
        if quantity > 10:
            commercial_indicators += 2
        if unit_price > 500:
            commercial_indicators += 1
        if any(word in description for word in ['commercial', 'business', 'industrial', 'wholesale']):
            commercial_indicators += 2
        
        # Personal indicators
        if quantity <= 5:
            personal_indicators += 1
        if any(word in description for word in ['personal', 'household', 'consumer', 'home']):
            personal_indicators += 2
    
    is_commercial = commercial_indicators > personal_indicators
    confidence = 'high' if abs(commercial_indicators - personal_indicators) > 2 else 'low'
    
    # Convert is_commercial boolean to classification string
    classification = "commercial" if is_commercial else "non-commercial"
    
    return {
        'product_classification': classification,
        'reasoning': f'Heuristic classification: {commercial_indicators} commercial vs {personal_indicators} personal indicators'
    }


def main():
    """Test function for the product classification module."""
    # Test data
    test_invoice = {
        "items": [{
            "description": "Lithium battery pack for commercial energy storage",
            "quantity": 2,
            "unit_price": 830,
            "total_price": 1660
        }],
        "totals": {"total_amount": 2110, "subtotal": 1660, "shipping_handling": 450},
        "currency": "USD"
    }
    
    test_bol = {
        "cargo_summary_table": {
            "description": "Commercial battery storage system",
            "quantity": 2,
            "weight": 50
        }
    }
    
    print("🧪 Testing Product Classification Module...")
    result = classify_product_commercial_vs_personal(test_invoice, test_bol, verbose=True)
    print(f"📋 Result: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()