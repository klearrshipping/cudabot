#!/usr/bin/env python3
"""
esad_product.py
────────────────
Extracts and standardizes product names from commercial descriptions in eSAD results.

Usage:
    python -m modules.esad_product <esad_json_path>

This script:
1. Extracts commercial_description from eSAD results
2. Uses LLM (Mistral, Kimi, DeepSeek) to identify and standardize the product name
3. Returns a clean, standardized product name
4. Handles various commercial description formats
"""

import sys
import json
import re
import requests
from typing import Optional, Dict, List
from modules.core.llm_client import LLMClient

def get_commercial_description_from_json(json_path: str) -> Optional[str]:
    """Extract commercial_description from eSAD results JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    extracted_fields = data['result']['extracted_fields']
    return extracted_fields.get('commercial_description', '')

def clean_commercial_description(description: str) -> str:
    """Clean and preprocess commercial description."""
    if not description:
        return ""
    
    # Remove common shipping terms and container info
    shipping_terms = [
        r'\d+\s*(?:FT|FOOT)\s*(?:STD|STANDARD)\s*CONTAINER',
        r'SAID\s+TO\s+CONTAIN',
        r'SHIPPERS\s+LOAD\s+STOW\s*&?\s*COU',
        r'SHIPPERS\s+LOAD\s+AND\s+COUNT',
        r'\d+\s*BOXES?\s+OF',
        r'\d+\s*PACKAGES?\s+OF',
        r'\d+\s*UNITS?\s+OF',
        r'CONTAINER\s+SAID\s+TO\s+CONTAIN',
        r'SEAL\s*[A-Z0-9]+',
        r'MARKS?\s*[A-Z0-9]+',
        r'WEIGHT\s*[0-9,\.]+',
        r'GROSS\s*WEIGHT\s*[0-9,\.]+',
        r'NET\s*WEIGHT\s*[0-9,\.]+',
        r'QUANTITY\s*[0-9,\.]+',
        r'QTY\s*[0-9,\.]+'
    ]
    
    cleaned = description.upper()
    for pattern in shipping_terms:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up extra spaces and punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned.strip())
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned.strip())
    
    return cleaned

def parse_llm_response(raw_response: str) -> Optional[str]:
    """Parse LLM response and extract product name."""
    if not raw_response:
        return None
    
    try:
        # Try to parse as JSON
        code_obj = json.loads(raw_response.strip())
        product_name = code_obj.get('product_name', '').strip()
        return product_name if product_name else None
    except (json.JSONDecodeError, AttributeError):
        # If JSON parsing fails, try to extract product name pattern
        import re
        product_match = re.search(r'"product_name"\s*:\s*"([^"]+)"', raw_response)
        if product_match:
            return product_match.group(1).strip()
        return None

def ask_llm_for_product_name(description: str, verbose: bool = False) -> Optional[str]:
    """Get the specific product name using LLM."""
    if not description or description.lower() in ['not specified', 'none', '']:
        return None
    
    llm = LLMClient()
    
    # Clean the description first
    cleaned_description = clean_commercial_description(description)
    
    if verbose:
        print(f"\n📦 Processing commercial description:")
        print(f"   Original: '{description}'")
        print(f"   Cleaned: '{cleaned_description}'")
    
    prompt = f"""
You are a customs documentation expert. Given the commercial description from a customs document: '{description}'

Cleaned description: '{cleaned_description}'

Your task is to extract a clean, specific product name from the description. Include the brand name and primary product type, plus key model identifiers when present. Remove excessive technical specifications, marketing language, and verbose details.

Examples:
- "2022 Tesla Model Y imported by an individual" → "2022 Tesla Model Y"
- "Apple iPhone 14 Pro smartphones" → "Apple iPhone 14 Pro smartphone"
- "EF ECOFLOW Solar Generator DELTA 2 Max 2048Wh with 4X100W 12V Solar Panels, High Efficiency Monocrystalline PV Modules, 2400W LFP Portable Power Station, AC + Solar Fast Dual Charging For Camping RV" → "EF ECOFLOW Solar Generator"
- "Nike Air Max 270 React Running Shoes Men's Size 10 Black/White Mesh Upper with Air Cushioning Technology" → "Nike Air Max 270 Running Shoes"
- "Samsung 65-inch QLED 4K Smart TV Model QN65Q80A with HDR10+ and Alexa Built-in 2023 Model" → "Samsung 65-inch QLED Smart TV"

Return ONLY a valid JSON object with a single field 'product_name', e.g. {{"product_name": "2022 Tesla Model Y"}}. 
Keep brand names, essential product types, and key model identifiers. Remove technical specs, marketing language, and excessive details.
Do NOT return generic categories like "Electric Vehicle" or "Electronics".
"""
    
    # Use Kimi as primary, Mistral as backup
    models = [
        "moonshotai/kimi-k2:free",                         # Primary - Kimi
        "mistralai/mistral-small-3.1-24b-instruct:free"   # Backup - Mistral
    ]
    
    # Test models with early termination
    for model in models:
        model_name = model.split('/')[-1].split(':')[0]
        if verbose:
            print(f"\n🧪 Testing model: {model_name}")
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            product_name = parse_llm_response(raw_response)
            
            if product_name:
                if verbose:
                    print(f"✅ {model_name} returned: {product_name}")
                return product_name
            else:
                if verbose:
                    print(f"❌ {model_name} did not return a valid product name.")
                
        except Exception as e:
            if verbose:
                print(f"❌ {model_name} exception: {e}")
    
    if verbose:
        print("🔥 All models failed to extract product name.")
    return None

def classify_with_hs_api(product_name: str, verbose: bool = False) -> Optional[Dict[str, str]]:
    """Classify product using HS Code API."""
    if not product_name:
        return None
    
    API_BASE_URL = "http://localhost:5000"
    
    if verbose:
        print(f"\n🔍 Classifying with HS Code API: {product_name}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/classify",
            json={"product_name": product_name, "verbose": verbose},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            if verbose:
                print(f"✅ HS Code API returned:")
                print(f"   HS Code: {result.get('hs_code', 'N/A')}")
                print(f"   Commodity Code: {result.get('commodity_code', 'N/A')}")
                print(f"   Description: {result.get('description', 'N/A')}")
            return result
        else:
            if verbose:
                print(f"❌ HS Code API error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        if verbose:
            print("❌ HS Code API connection failed. Make sure the API is running on http://localhost:5000")
        return None
    except requests.exceptions.Timeout:
        if verbose:
            print("❌ HS Code API request timed out")
        return None
    except Exception as e:
        if verbose:
            print(f"❌ HS Code API error: {str(e)}")
        return None

def process_commercial_description(description: str, verbose: bool = False, get_hs_code: bool = True) -> Dict[str, str]:
    """Process commercial description and return standardized product information with optional HS code classification."""
    results = {
        'original_description': description,
        'cleaned_description': clean_commercial_description(description),
        'product_name': None,
        'hs_code': None,
        'commodity_code': None,
        'hs_description': None
    }
    
    if description and description.lower() not in ['not specified', 'none', '']:
        # Get product name from LLM
        product_name = ask_llm_for_product_name(description, verbose=verbose)
        results['product_name'] = product_name
        
        # Optionally get HS code classification
        if get_hs_code and product_name:
            hs_result = classify_with_hs_api(product_name, verbose=verbose)
            if hs_result:
                results['hs_code'] = hs_result.get('hs_code')
                results['commodity_code'] = hs_result.get('commodity_code')
                results['hs_description'] = hs_result.get('description')
        
    return results

def main():
    """Main function with improved error handling."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_product <esad_json_path>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        # Get commercial description from eSAD results
        description = get_commercial_description_from_json(json_path)
        print(f"📋 Extracted commercial description:")
        print(f"   {description}")
        
        # Process commercial description
        results = process_commercial_description(description)
        
        # Display results
        print(f"\n🏆 Product Classification Results:")
        print("=" * 60)
        print(f"   Original Description: {results['original_description']}")
        print(f"   Cleaned Description: {results['cleaned_description']}")
        print(f"   Standardized Product Name: {results['product_name'] if results['product_name'] else 'FAILED'}")
        
        # Display HS Code results if available
        if results['hs_code']:
            print(f"\n📋 HS Code Classification:")
            print(f"   HS Code: {results['hs_code']}")
            print(f"   Commodity Code: {results['commodity_code']}")
            print(f"   Description: {results['hs_description']}")
        elif results['product_name']:
            print(f"\n⚠️  Product name extracted but HS Code API unavailable")
        
        # Summary
        if results['product_name']:
            print(f"\n✅ Successfully processed product: {results['product_name']}")
            if results['hs_code']:
                print(f"✅ HS Code classification: {results['hs_code']}")
        else:
            print(f"\n❌ Failed to extract product name")
        
    except FileNotFoundError:
        print(f"Error: File '{json_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file '{json_path}'.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 