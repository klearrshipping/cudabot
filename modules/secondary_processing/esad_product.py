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

def ask_llm_for_product_name(description: str) -> Optional[str]:
    """Get the standardized product name using LLM."""
    if not description or description.lower() in ['not specified', 'none', '']:
        return None
    
    llm = LLMClient()
    
    # Clean the description first
    cleaned_description = clean_commercial_description(description)
    
    prompt = f"""
You are a customs documentation expert. Given the commercial description from a customs document: '{description}'

Cleaned description: '{cleaned_description}'

Your task is to extract and standardize the main product name. Focus on the actual product, not shipping details, quantities, or container information.

Return ONLY a valid JSON object with a single field 'product_name', e.g. {{"product_name": "Footwear"}}, where the value is the standardized product name. Use clear, simple product names. Do not return any explanation or extra text.
"""
    
    # Use Kimi as primary, Mistral as backup
    models = [
        "moonshotai/kimi-k2:free",                         # Primary - Kimi
        "mistralai/mistral-small-3.1-24b-instruct:free"   # Backup - Mistral
    ]
    
    results = {}
    
    # Test models with early termination
    for model in models:
        model_name = model.split('/')[-1].split(':')[0]
        print(f"\n🧪 Testing model: {model_name}")
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            product_name = parse_llm_response(raw_response)
            
            if product_name:
                print(f"✅ {model_name} returned: {product_name}")
                results[model_name] = product_name
                # Early termination after first success
                break
            else:
                print(f"❌ {model_name} did not return a valid product name.")
                results[model_name] = None
                
        except Exception as e:
            print(f"❌ {model_name} exception: {e}")
            results[model_name] = None
    
    # Show results from tested models
    print(f"\n📊 Model Results:")
    print("=" * 40)
    for model_name, product_name in results.items():
        status = "✅ SUCCESS" if product_name else "❌ FAILED"
        print(f"   {model_name}: {product_name if product_name else 'No response'} ({status})")
    
    # Return the first successful result, or None if all failed
    for model_name, product_name in results.items():
        if product_name:
            return product_name
    
    print("🔄 All models failed to extract product name.")
    return None

def process_commercial_description(description: str) -> Dict[str, str]:
    """Process commercial description and return standardized product information."""
    results = {
        'original_description': description,
        'cleaned_description': clean_commercial_description(description),
        'product_name': None
    }
    
    if description and description.lower() not in ['not specified', 'none', '']:
        print(f"\n📦 Processing commercial description:")
        print(f"   Original: '{description}'")
        print(f"   Cleaned: '{results['cleaned_description']}'")
        
        # Get product name from LLM
        product_name = ask_llm_for_product_name(description)
        results['product_name'] = product_name
        
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
        
        # Summary
        if results['product_name']:
            print(f"\n✅ Successfully extracted product name: {results['product_name']}")
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