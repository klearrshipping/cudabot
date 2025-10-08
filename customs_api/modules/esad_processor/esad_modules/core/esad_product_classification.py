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
import requests

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

try:
    from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS
except ImportError:
    # Fallback configuration if config import fails
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_URL = os.getenv('OPENROUTER_URL', 'https://openrouter.ai/api/v1/chat/completions')
    OPENROUTER_HEADERS = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost:3000',
        'X-Title': 'eSAD Product Classification'
    }


def classify_product_commercial_vs_personal(invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> Dict[str, Any]:
    """Classify if products are commercial or personal using LLM analysis"""
    
    # Extract product information
    products = []
    
    # From invoice items
    if 'items' in invoice_data and invoice_data['items']:
        for item in invoice_data['items']:
            products.append({
                'description': item.get('description', ''),
                'quantity': item.get('quantity', 0),
                'unit_price': item.get('unit_price', 0),
                'total_price': item.get('total_price', 0),
                'source': 'invoice'
            })
    
    # From BOL cargo details
    if 'cargo' in bol_data:
        cargo = bol_data['cargo']
        if isinstance(cargo, list):
            for item in cargo:
                products.append({
                    'description': item.get('nature_and_quantity_of_goods', ''),
                    'quantity': item.get('no_of_pieces', 0),
                    'unit_price': 0,
                    'total_price': 0,
                    'source': 'bol'
                })
        elif isinstance(cargo, dict):
            products.append({
                'description': cargo.get('commodity_description', ''),
                'quantity': cargo.get('package_count_and_description', 0),
                'unit_price': 0,
                'total_price': 0,
                'source': 'bol'
            })
    
    if not products:
        return {
            'classification': 'Personal',
            'confidence': 'low',
            'reasoning': 'No product information found - defaulting to Personal',
            'products_analyzed': 0
        }
    
    # Build comprehensive prompt with safe JSON serialization
    def safe_json_dumps(obj, max_depth=3, current_depth=0):
        """Safely serialize JSON with depth limit to avoid circular references"""
        if current_depth >= max_depth:
            return "[Max depth reached]"
        
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                try:
                    result[key] = safe_json_dumps(value, max_depth, current_depth + 1)
                except:
                    result[key] = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            return result
        elif isinstance(obj, list):
            result = []
            for item in obj:
                try:
                    result.append(safe_json_dumps(item, max_depth, current_depth + 1))
                except:
                    result.append(str(item)[:100] + "..." if len(str(item)) > 100 else str(item))
            return result
        else:
            return obj
    
    # Safely serialize data
    safe_invoice_data = safe_json_dumps(invoice_data)
    safe_bol_data = safe_json_dumps(bol_data)
    
    prompt = f"""
Analyze the following products to determine if they are COMMERCIAL or PERSONAL:

PRODUCTS TO ANALYZE:
{json.dumps(products, indent=2)}

ADDITIONAL CONTEXT:
- Invoice Data: {json.dumps(safe_invoice_data, indent=2)}
- BOL Data: {json.dumps(safe_bol_data, indent=2)}

CLASSIFICATION CRITERIA:

COMMERCIAL INDICATORS:
1. BUSINESS USE ITEMS:
   - Office equipment (computers, printers, furniture)
   - Industrial machinery and tools
   - Commercial vehicles (trucks, vans, delivery vehicles)
   - Professional equipment (medical, dental, construction)
   - Manufacturing supplies and raw materials
   - Wholesale quantities (bulk orders)
   - Business software and systems

2. HIGH-VALUE ITEMS:
   - Items over $5,000 USD
   - Luxury goods in commercial quantities
   - Professional-grade equipment
   - Industrial/commercial vehicles

3. COMMERCIAL QUANTITIES:
   - Bulk orders (multiple units of same item)
   - Wholesale quantities
   - Items clearly for resale
   - Professional/industrial quantities

4. BUSINESS ENTITIES:
   - Shipped to/from business addresses
   - Company names in shipping info
   - Commercial invoice formats
   - Business registration numbers

5. COMMERCIAL KEYWORDS:
   - "commercial", "industrial", "professional", "business"
   - "wholesale", "retail", "distribution", "manufacturing"
   - "equipment", "machinery", "systems", "tools"
   - Brand names with commercial models

PERSONAL INDICATORS:
1. HOUSEHOLD ITEMS:
   - Personal electronics (phones, laptops for personal use)
   - Clothing and personal accessories
   - Home appliances and furniture
   - Personal vehicles (cars, motorcycles for personal use)
   - Personal care items
   - Hobby and recreational items

2. PERSONAL QUANTITIES:
   - Single units or small quantities
   - Personal use quantities
   - Individual/household consumption

3. PERSONAL ADDRESSES:
   - Residential addresses
   - Individual names (not company names)
   - Personal shipping information

4. PERSONAL KEYWORDS:
   - "personal", "household", "individual", "private"
   - "home", "family", "personal use"
   - Consumer brand names

GREY ZONE PRODUCTS (Could be Commercial OR Personal):
- Inverters (1kw-15kw range - common in both homes and small businesses)
- Generators (portable to industrial - depends on size and context)
- Solar panels and equipment (residential vs commercial installations)
- Computers and electronics (personal vs business use)
- Tools and equipment (hobby vs professional use)
- Vehicles (personal vs commercial depending on type and use)
- Furniture (home vs office use)

IMPORTANT: Always identify grey zone products first, then apply contextual analysis.
If a product could reasonably be used for both personal and commercial purposes, it is a grey zone product.

GREY ZONE DECISION LOGIC:
When a product falls into the grey zone, determine classification based on CONSIGNEE TYPE + QUANTITY:

1. CONSIGNEE ANALYSIS:
   - Individual Name (John Smith, Mary Johnson) = PERSONAL CONSIGNEE
   - Company Name (ABC Ltd, XYZ Corp, Business Name) = COMMERCIAL CONSIGNEE
   - Business Address (office, warehouse, commercial building) = COMMERCIAL CONSIGNEE
   - Residential Address (home, apartment, house) = PERSONAL CONSIGNEE

2. CONTEXTUAL QUANTITY ANALYSIS:
   Analyze the quantity in context of the product type and consignee to determine if it suggests personal or commercial use:

   PERSONAL USE INDICATORS:
   - Quantity suggests individual/household consumption
   - Reasonable for personal use (e.g., 1 inverter for home, 2 laptops for family)
   - Not excessive for personal needs
   - Typical consumer quantities

   COMMERCIAL USE INDICATORS:
   - Quantity suggests business operations or resale
   - Excessive for personal consumption (e.g., 10 inverters, 50 laptops)
   - Bulk quantities indicating wholesale/distribution
   - Professional/industrial quantities

3. GREY ZONE DECISION LOGIC:
   For grey zone products, analyze the combination of:
   - CONSIGNEE TYPE (Individual vs Business Entity)
   - PRODUCT TYPE (Nature and typical use)
   - QUANTITY CONTEXT (Reasonable for personal vs commercial use)

   DECISION FRAMEWORK:
   1. Identify consignee type (Individual name vs Company name)
   2. Assess if quantity is reasonable for personal consumption of that product type
   3. Consider the nature of the product and its typical use patterns
   4. Make contextual determination based on all factors

   EXAMPLES OF CONTEXTUAL ANALYSIS:
   - Individual + 1 inverter = Personal (reasonable for home use)
   - Individual + 5 inverters = Commercial (excessive for personal use)
   - Individual + 10 Snickers = Personal (reasonable personal consumption)
   - Individual + 100 Snickers = Commercial (excessive for personal consumption)
   - Business + 1 inverter = Commercial (business entity)
   - Business + 10 inverters = Commercial (business entity + bulk quantity)

   CRITICAL: Individual names (like "Rafer Johnson", "John Smith", "Mary Johnson") should be treated as PERSONAL CONSIGNEES regardless of invoice type or supplier context.
   The consignee's individual name takes precedence over other contextual factors for grey zone products.

   IMPORTANT: Use contextual reasoning rather than rigid quantity thresholds.
   Consider what would be reasonable for personal vs commercial use based on the specific product and consignee.

4. BUSINESS ENTITY INDICATORS:
   - Company suffixes: Ltd, LLC, Inc, Corp, Co, Enterprise, etc.
   - Business registration numbers
   - Commercial addresses
   - Professional titles in names

5. PERSONAL ENTITY INDICATORS:
   - Individual names without company suffixes
   - Residential addresses
   - Personal titles (Mr., Mrs., Ms., Dr.)

MIXED INDICATORS:
- Combination of commercial and personal items
- Unclear business vs personal use
- Ambiguous quantities or values

CRITICAL REQUIREMENT: You MUST classify as either "Commercial" OR "Personal". NO "Mixed" or "Unknown" classifications are allowed.
If there are multiple products with different indicators, make a final determination based on the PREDOMINANT use case and consignee type.
If uncertain, use the consignee type as the tie-breaker (Individual = Personal, Business = Commercial).

Return ONLY a JSON object with:
{{
  "classification": "Commercial" | "Personal",
  "confidence": "high" | "medium" | "low",
  "reasoning": "Detailed explanation of classification decision including grey zone analysis and why this specific classification was chosen",
  "products_analyzed": number_of_products,
  "commercial_indicators": ["list of commercial indicators found"],
  "personal_indicators": ["list of personal indicators found"],
  "grey_zone_products": ["list of products that could be either commercial or personal"],
  "consignee_analysis": "Analysis of consignee type (individual vs business entity)",
  "quantity_analysis": "Contextual analysis of quantities and their implications for classification",
  "contextual_reasoning": "Detailed explanation of how consignee type, product type, and quantity context were evaluated to reach the FINAL Personal or Commercial decision"
}}
"""
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        result = json.loads(json_match.group())
        
        return result
        
    except Exception as e:
        return {
            'classification': 'Personal',
            'confidence': 'low',
            'reasoning': f'Classification failed: {str(e)} - defaulting to Personal',
            'products_analyzed': len(products),
            'commercial_indicators': [],
            'personal_indicators': [],
            'grey_zone_products': [],
            'consignee_analysis': f'Error in classification: {str(e)}',
            'quantity_analysis': f'Error in classification: {str(e)}',
            'contextual_reasoning': f'Error in classification: {str(e)}'
        }


def test_classification():
    """Test the classification function with comprehensive test cases"""
    
    print("=" * 80)
    print("TEST 1: PERSONAL - Individual consignee with grey zone product (10kw inverter)")
    print("=" * 80)
    
    test_invoice_personal = {
        'items': [
            {
                'description': '10kw inverter',
                'quantity': 1,
                'unit_price': 3000,
                'total_price': 3000
            }
        ],
        'invoice_details': {
            'consignee_name': 'Rafer Johnson',
            'consignee_address': '123 Main Street, Kingston, Jamaica',
            'invoice_number': 'INV-2024-001'
        },
        'totals': {
            'subtotal': 3000,
            'total': 3000
        },
        'currency': 'USD'
    }
    
    test_bol_personal = {
        'cargo': {
            'commodity_description': 'Electrical Equipment',
            'package_count_and_description': '1 Box',
            'no_of_pieces': 1
        },
        'consignee': {
            'name': 'Rafer Johnson',
            'address': '123 Main Street, Kingston, Jamaica'
        },
        'shipper': {
            'name': 'Solar Supplies Inc',
            'address': 'Miami, FL, USA'
        }
    }
    
    result1 = classify_product_commercial_vs_personal(test_invoice_personal, test_bol_personal)
    print(f"\n🎉 Test 1 Result:")
    print(json.dumps(result1, indent=2))
    print(f"\n✅ Classification: {result1['classification']}")
    print(f"✅ Confidence: {result1['confidence']}")
    
    print("\n" + "=" * 80)
    print("TEST 2: COMMERCIAL - Business entity with multiple inverters")
    print("=" * 80)
    
    test_invoice_commercial = {
        'items': [
            {
                'description': '10kw inverter',
                'quantity': 5,
                'unit_price': 3000,
                'total_price': 15000
            },
            {
                'description': 'Solar panels 500W',
                'quantity': 20,
                'unit_price': 250,
                'total_price': 5000
            }
        ],
        'invoice_details': {
            'consignee_name': 'Green Energy Solutions Ltd',
            'consignee_address': '45 Industrial Park, Kingston, Jamaica',
            'invoice_number': 'INV-2024-002'
        },
        'totals': {
            'subtotal': 20000,
            'total': 20000
        },
        'currency': 'USD'
    }
    
    test_bol_commercial = {
        'cargo': {
            'commodity_description': 'Solar Equipment and Inverters',
            'package_count_and_description': '25 Boxes',
            'no_of_pieces': 25
        },
        'consignee': {
            'name': 'Green Energy Solutions Ltd',
            'address': '45 Industrial Park, Kingston, Jamaica'
        },
        'shipper': {
            'name': 'Solar Wholesale Inc',
            'address': 'Miami, FL, USA'
        }
    }
    
    result2 = classify_product_commercial_vs_personal(test_invoice_commercial, test_bol_commercial)
    print(f"\n🎉 Test 2 Result:")
    print(json.dumps(result2, indent=2))
    print(f"\n✅ Classification: {result2['classification']}")
    print(f"✅ Confidence: {result2['confidence']}")
    
    print("\n" + "=" * 80)
    print("TEST 3: PERSONAL - Individual with household items")
    print("=" * 80)
    
    test_invoice_personal2 = {
        'items': [
            {
                'description': 'Laptop computer',
                'quantity': 1,
                'unit_price': 1200,
                'total_price': 1200
            },
            {
                'description': 'Clothing items',
                'quantity': 10,
                'unit_price': 50,
                'total_price': 500
            }
        ],
        'invoice_details': {
            'consignee_name': 'Mary Johnson',
            'consignee_address': '78 Residential Drive, Montego Bay, Jamaica',
            'invoice_number': 'INV-2024-003'
        },
        'totals': {
            'subtotal': 1700,
            'total': 1700
        },
        'currency': 'USD'
    }
    
    test_bol_personal2 = {
        'cargo': {
            'commodity_description': 'Personal Effects',
            'package_count_and_description': '2 Boxes',
            'no_of_pieces': 2
        },
        'consignee': {
            'name': 'Mary Johnson',
            'address': '78 Residential Drive, Montego Bay, Jamaica'
        },
        'shipper': {
            'name': 'Amazon Fulfillment',
            'address': 'New York, USA'
        }
    }
    
    result3 = classify_product_commercial_vs_personal(test_invoice_personal2, test_bol_personal2)
    print(f"\n🎉 Test 3 Result:")
    print(json.dumps(result3, indent=2))
    print(f"\n✅ Classification: {result3['classification']}")
    print(f"✅ Confidence: {result3['confidence']}")
    
    print("\n" + "=" * 80)
    print("SUMMARY OF TESTS")
    print("=" * 80)
    print(f"Test 1 (Individual + 1 inverter): {result1['classification']}")
    print(f"Test 2 (Business + bulk equipment): {result2['classification']}")
    print(f"Test 3 (Individual + personal items): {result3['classification']}")
    print("=" * 80)


if __name__ == "__main__":
    test_classification()

