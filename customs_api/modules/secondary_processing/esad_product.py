#!/usr/bin/env python3
"""
esad_product.py
────────────────
Extracts and standardizes product names from commercial descriptions in eSAD results.

Usage:
    python -m modules.esad_product <esad_json_path>

This script:
1. Extracts commercial_description from eSAD results
2. Uses LLM (Mistral, Kimi) to identify and standardize the product name
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
    print(f"\n🔍 DEBUG: ask_llm_for_product_name called")
    print(f"   Description: {description}")
    print(f"   Verbose: {verbose}")
    
    if not description or description.lower() in ['not specified', 'none', '']:
        print(f"❌ DEBUG: Description is invalid or empty, returning None")
        return None
    
    print(f"🔍 DEBUG: Initializing LLM client...")
    llm = LLMClient()
    
    # Clean the description first
    cleaned_description = clean_commercial_description(description)
    print(f"🔍 DEBUG: Cleaned description: {cleaned_description}")
    
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
        print(f"🔍 DEBUG: Testing model: {model_name}")
        if verbose:
            print(f"\n🧪 Testing model: {model_name}")
        try:
            print(f"🔍 DEBUG: Sending prompt to LLM...")
            raw_response = llm.send_prompt(prompt, model=model)
            print(f"🔍 DEBUG: LLM raw response: {raw_response}")
            product_name = parse_llm_response(raw_response)
            print(f"🔍 DEBUG: Parsed product name: {product_name}")
            
            if product_name:
                print(f"✅ DEBUG: {model_name} successfully returned: {product_name}")
                if verbose:
                    print(f"✅ {model_name} returned: {product_name}")
                return product_name
            else:
                print(f"❌ DEBUG: {model_name} did not return a valid product name")
                if verbose:
                    print(f"❌ {model_name} did not return a valid product name.")
                
        except Exception as e:
            print(f"❌ DEBUG: {model_name} failed with error: {e}")
            if verbose:
                print(f"❌ {model_name} exception: {e}")
    
    print(f"❌ DEBUG: All models failed to extract product name")
    if verbose:
        print("🔥 All models failed to extract product name.")
    return None

def classify_with_hs_api(product_name: str, verbose: bool = False, order_id: str = None, 
                        contextual_data: Dict[str, Any] = None) -> Optional[Dict[str, str]]:
    """Classify product using HS Code API with optional rich contextual data."""
    print(f"\n🔍 DEBUG: classify_with_hs_api called")
    print(f"   Product name: {product_name}")
    print(f"   Verbose: {verbose}")
    print(f"   Order ID: {order_id}")
    print(f"   Has contextual data: {bool(contextual_data)}")
    
    if not product_name:
        print(f"❌ DEBUG: No product name provided, returning None")
        return None
    
    API_BASE_URL = "http://localhost:5000"
    print(f"🔍 DEBUG: Using API URL: {API_BASE_URL}")
    
    if verbose:
        print(f"\n🔍 Classifying with HS Code API: {product_name}")
        if order_id:
            print(f"   Order ID: {order_id}")
        if contextual_data:
            print(f"   Contextual data keys: {list(contextual_data.keys())}")
    
    try:
        payload = {"product_name": product_name, "verbose": verbose}
        if order_id:
            payload["order_id"] = order_id
        if contextual_data:
            payload["contextual_data"] = contextual_data
        
        print(f"🔍 DEBUG: Sending payload to HSCode API: {payload}")
            
        response = requests.post(
            f"{API_BASE_URL}/classify",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        print(f"🔍 DEBUG: HSCode API response status: {response.status_code}")
        print(f"🔍 DEBUG: HSCode API response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"🔍 DEBUG: HSCode API response body: {result}")
            if verbose:
                print(f"✅ HS Code API returned:")
                print(f"   HS Code: {result.get('hs_code', 'N/A')}")
                print(f"   Commodity Code: {result.get('commodity_code', 'N/A')}")
                print(f"   Description: {result.get('description', 'N/A')}")
            return result
        else:
            print(f"❌ DEBUG: HSCode API error response: {response.text}")
            if verbose:
                print(f"❌ HS Code API error: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ DEBUG: Connection error to HSCode API: {e}")
        if verbose:
            print("❌ HS Code API connection failed. Make sure the API is running on http://localhost:5000")
        return None
    except requests.exceptions.Timeout as e:
        print(f"❌ DEBUG: Timeout error to HSCode API: {e}")
        if verbose:
            print("❌ HS Code API request timed out")
        return None
    except Exception as e:
        print(f"❌ DEBUG: Unexpected error calling HSCode API: {e}")
        import traceback
        traceback.print_exc()
        if verbose:
            print(f"❌ HS Code API error: {str(e)}")
        return None

def _build_contextual_data_from_primary(primary_data: Dict[str, Any], product_name: str) -> Optional[Dict[str, Any]]:
    """
    Build contextual data from primary processing results for enhanced HS Code API calls.
    
    Args:
        primary_data: Data from primary processing (invoice, BOL, etc.)
        product_name: Cleaned product name
        
    Returns:
        Contextual data dictionary for HS Code API
    """
    try:
        # Extract data from primary processing results
        extracted_fields = primary_data.get('result', {}).get('extracted_fields', {})
        
        # Build contextual data structure
        contextual_data = {}
        
        # Buyer information
        buyer_name = extracted_fields.get('buyer_name', '')
        buyer_address = extracted_fields.get('buyer_address', '')
        if buyer_name or buyer_address:
            contextual_data['buyer_info'] = {
                'name': buyer_name,
                'address': buyer_address
            }
        
        # Supplier information
        supplier_name = extracted_fields.get('supplier_name', '')
        supplier_address = extracted_fields.get('supplier_address', '')
        if supplier_name or supplier_address:
            contextual_data['supplier_info'] = {
                'name': supplier_name,
                'address': supplier_address
            }
        
        # Product details
        commercial_description = extracted_fields.get('commercial_description', '')
        if commercial_description:
            contextual_data['product_details'] = {
                'description': product_name,
                'original_description': commercial_description
            }
        
        # Shipping information
        port_of_loading = extracted_fields.get('port_of_loading', '')
        port_of_destination = extracted_fields.get('port_of_destination', '')
        weight = extracted_fields.get('weight', '')
        package_type = extracted_fields.get('package_type', '')
        
        if any([port_of_loading, port_of_destination, weight, package_type]):
            contextual_data['shipping_info'] = {
                'port_of_origin': port_of_loading,
                'port_of_destination': port_of_destination,
                'weight': weight,
                'package_type': package_type
            }
        
        # Document metadata
        contextual_data['document_metadata'] = {
            'extraction_confidence': primary_data.get('extraction_confidence', 'unknown'),
            'processing_method': primary_data.get('_metadata', {}).get('processing_method', 'unknown')
        }
        
        print(f"🔍 DEBUG: Built contextual data with {len(contextual_data)} sections")
        return contextual_data if contextual_data else None
        
    except Exception as e:
        print(f"❌ DEBUG: Error building contextual data: {e}")
        return None

def process_commercial_description(description: str, verbose: bool = False, get_hs_code: bool = True, 
                                 order_id: str = None, primary_data: Dict[str, Any] = None) -> Dict[str, str]:
    """Process commercial description and return standardized product information with optional HS code classification."""
    print(f"\n🔍 DEBUG: process_commercial_description called")
    print(f"   Description: {description}")
    print(f"   Verbose: {verbose}")
    print(f"   Get HS Code: {get_hs_code}")
    print(f"   Order ID: {order_id}")
    print(f"   Has primary data: {bool(primary_data)}")
    
    results = {
        'original_description': description,
        'cleaned_description': clean_commercial_description(description),
        'product_name': None,
        'hs_code': None,
        'commodity_code': None,
        'hs_description': None
    }
    
    print(f"🔍 DEBUG: Initial results: {results}")
    
    if description and description.lower() not in ['not specified', 'none', '']:
        print(f"🔍 DEBUG: Description is valid, proceeding with processing")
        
        # Get product name from LLM
        print(f"🔍 DEBUG: Calling ask_llm_for_product_name...")
        product_name = ask_llm_for_product_name(description, verbose=verbose)
        print(f"🔍 DEBUG: ask_llm_for_product_name returned: {product_name}")
        results['product_name'] = product_name
        
        # Optionally get HS code classification
        if get_hs_code and product_name:
            print(f"🔍 DEBUG: get_hs_code=True and product_name exists, calling classify_with_hs_api...")
            
            # Build contextual data from primary processing results if available
            contextual_data = None
            if primary_data:
                contextual_data = _build_contextual_data_from_primary(primary_data, product_name)
                print(f"🔍 DEBUG: Built contextual data: {list(contextual_data.keys()) if contextual_data else 'None'}")
            
            hs_result = classify_with_hs_api(
                product_name, 
                verbose=verbose, 
                order_id=order_id,
                contextual_data=contextual_data
            )
            print(f"🔍 DEBUG: classify_with_hs_api returned: {hs_result}")
            if hs_result:
                results['hs_code'] = hs_result.get('hs_code')
                results['commodity_code'] = hs_result.get('commodity_code')
                results['hs_description'] = hs_result.get('description')
                print(f"🔍 DEBUG: Updated results with HS code data: {results}")
            else:
                print(f"❌ DEBUG: classify_with_hs_api returned None or empty result")
        else:
            print(f"🔍 DEBUG: Skipping HS code classification - get_hs_code={get_hs_code}, product_name={product_name}")
    else:
        print(f"❌ DEBUG: Description is invalid or empty, skipping processing")
        
    print(f"🔍 DEBUG: Final results: {results}")
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