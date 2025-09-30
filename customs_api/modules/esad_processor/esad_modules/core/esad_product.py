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
import time
from typing import Optional, Dict, List, Any
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
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

Your task is to extract a clean, specific product name from the description. Include the brand name, primary product type, and ALL key model identifiers when present. For vehicles, preserve trim levels, engine specifications, and model variants as they are essential for accurate classification.

Examples:
- "2022 Tesla Model Y imported by an individual" → "2022 Tesla Model Y"
- "2023 Chevrolet Tahoe C1500 RST (Full-Size SUV)" → "2023 Chevrolet Tahoe C1500 RST"
- "Apple iPhone 14 Pro smartphones" → "Apple iPhone 14 Pro smartphone"
- "EF ECOFLOW Solar Generator DELTA 2 Max 2048Wh with 4X100W 12V Solar Panels, High Efficiency Monocrystalline PV Modules, 2400W LFP Portable Power Station, AC + Solar Fast Dual Charging For Camping RV" → "EF ECOFLOW Solar Generator DELTA 2 Max"
- "Nike Air Max 270 React Running Shoes Men's Size 10 Black/White Mesh Upper with Air Cushioning Technology" → "Nike Air Max 270 React Running Shoes"
- "Samsung 65-inch QLED 4K Smart TV Model QN65Q80A with HDR10+ and Alexa Built-in 2023 Model" → "Samsung 65-inch QLED Smart TV QN65Q80A"

Return ONLY a valid JSON object with a single field 'product_name', e.g. {{"product_name": "2023 Chevrolet Tahoe C1500 RST"}}. 
Keep brand names, essential product types, and ALL key model identifiers (especially trim levels, engine codes, model variants). Remove only marketing language and excessive technical specifications that don't identify the specific product.
Do NOT return generic categories like "Electric Vehicle" or "Electronics".
"""
    
    # Smart model selection - use GPT-5 for better performance
    models = [
        "openai/gpt-5"        # Primary - GPT-5, best performance and accuracy
        # "moonshotai/kimi-k2:free"                        # Disabled - Too many rate limits
    ]
    
    # Test models with early termination
    for i, model in enumerate(models):
        model_name = model.split('/')[-1].split(':')[0]
        if verbose:
            print(f"\n🧪 Testing model: {model_name}")
        
        # Add small delay between model attempts to prevent rate limiting
        if i > 0:
            time.sleep(1)
        
        try:
            raw_response, success, error_type = llm.send_prompt(prompt, model=model)
            
            if not success:
                if error_type == "rate_limit":
                    if verbose:
                        print(f"⏳ {model_name} rate limited, trying next model...")
                else:
                    if verbose:
                        print(f"❌ {model_name} failed: {error_type}")
                continue
            
            product_name = parse_llm_response(raw_response)
            
            if product_name:
                if verbose:
                    print(f"✅ {model_name} returned: {product_name}")
                return product_name
            else:
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
    if not product_name:
        return None
    
    API_BASE_URL = "http://localhost:5000"
    
    if verbose:
        print(f"\n🔍 Classifying with HS Code API: {product_name}")
        if order_id:
            print(f"   Order ID: {order_id}")
        if contextual_data:
            print(f"   Contextual data keys: {list(contextual_data.keys())}")
    
    try:
        # Use synchronous endpoint for more reliable operation
        payload = {"product_name": product_name, "verbose": verbose}
        if order_id:
            payload["order_id"] = order_id
        if contextual_data:
            payload["contextual_data"] = contextual_data
            
        # Use synchronous classification with longer timeout
        response = requests.post(
            f"{API_BASE_URL}/classify",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 minute timeout for full classification
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

def _build_contextual_data_from_primary(primary_data: Dict[str, Any], product_name: str, bol_data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Build contextual data from primary processing results for enhanced HS Code API calls.
    
    Args:
        primary_data: Data from primary processing (invoice, BOL, etc.)
        product_name: Cleaned product name
        
    Returns:
        Contextual data dictionary for HS Code API
    """
    try:
        # Build contextual data from primary data structure
        
        # Build contextual data structure
        contextual_data = {}
        
        # Supplier information (from invoice data)
        supplier_info = primary_data.get('supplier', {})
        if supplier_info:
            contextual_data['supplier_info'] = {
                'name': supplier_info.get('name', ''),
                'address': supplier_info.get('address', '')
            }
            # Also populate flat structure for HS Code API compatibility
            contextual_data['shipper'] = supplier_info.get('name', '')
            contextual_data['shipper_address'] = supplier_info.get('address', '')
        
        # Product details (from invoice items)
        items = primary_data.get('items', [])
        if items and len(items) > 0:
            first_item = items[0]
            contextual_data['product_details'] = {
                'description': product_name,
                'original_description': first_item.get('description', ''),
                'quantity': first_item.get('quantity', ''),
                'unit_price': first_item.get('unit_price', ''),
                'total_price': first_item.get('total_price', '')
            }
        
        # Invoice details
        invoice_details = primary_data.get('invoice_details', {})
        if invoice_details:
            contextual_data['invoice_info'] = {
                'invoice_number': invoice_details.get('invoice_number', ''),
                'date': invoice_details.get('date', ''),
                'terms_of_sale': invoice_details.get('terms_of_sale', ''),
                'currency': invoice_details.get('currency', '')
            }
        
        # Totals information
        totals = primary_data.get('totals', {})
        if totals:
            contextual_data['financial_info'] = {
                'total_amount': totals.get('total_amount', ''),
                'shipping_handling': totals.get('shipping_handling', ''),
                'currency': primary_data.get('currency', '')
            }
        
        # Shipping information (from invoice)
        shipping = primary_data.get('shipping', {})
        if shipping:
            contextual_data['shipping_info'] = {
                'delivery_terms': shipping.get('delivery_terms', '')
            }
        
        # BOL information (if available)
        if bol_data:
            # Consignee information (buyer)
            consignee = bol_data.get('consignee', {})
            if consignee:
                contextual_data['buyer_info'] = {
                    'name': consignee.get('name', ''),
                    'address': f"{consignee.get('address_line1', '')} {consignee.get('city', '')} {consignee.get('country', '')}".strip(),
                    'phone': consignee.get('phone', ''),
                    'email': consignee.get('email', '')
                }
                # Also populate flat structure for HS Code API compatibility
                contextual_data['consignee_name'] = consignee.get('name', '')
                contextual_data['consignee_address'] = f"{consignee.get('address_line1', '')} {consignee.get('city', '')} {consignee.get('country', '')}".strip()
            
            # Shipper information (supplier - may override invoice data)
            shipper = bol_data.get('shipper', {})
            if shipper:
                contextual_data['supplier_info'] = {
                    'name': shipper.get('name', ''),
                    'address': f"{shipper.get('address_line1', '')} {shipper.get('city', '')} {shipper.get('state_province', '')} {shipper.get('postal_code', '')} {shipper.get('country', '')}".strip()
                }
                # Also populate flat structure for HS Code API compatibility
                contextual_data['shipper'] = shipper.get('name', '')
                contextual_data['shipper_address'] = f"{shipper.get('address_line1', '')} {shipper.get('city', '')} {shipper.get('state_province', '')} {shipper.get('postal_code', '')} {shipper.get('country', '')}".strip()
            
            # Enhanced shipping information from BOL
            if 'shipping_info' not in contextual_data:
                contextual_data['shipping_info'] = {}
            
            contextual_data['shipping_info'].update({
                'port_of_loading': bol_data.get('port_of_loading', ''),
                'port_of_discharge': bol_data.get('port_of_discharge', ''),
                'vessel_name': bol_data.get('vessel_name', ''),
                'voyage_number': bol_data.get('voyage_number', ''),
                'sea_waybill_no': bol_data.get('sea_waybill_no', ''),
                'carrier': bol_data.get('carrier', '')
            })
            
            # Also populate flat structure for HS Code API compatibility
            contextual_data['port_of_origin'] = bol_data.get('port_of_loading', '')
            contextual_data['port_of_destination'] = bol_data.get('port_of_discharge', '')
            contextual_data['vessel'] = bol_data.get('vessel_name', '')
            contextual_data['bill_of_lading'] = bol_data.get('sea_waybill_no', '')
            
            # Cargo details from BOL
            cargo = bol_data.get('cargo', {})
            if cargo:
                # Handle both list and dict structures for cargo
                if isinstance(cargo, list) and len(cargo) > 0:
                    # If cargo is a list, use the first item
                    cargo_item = cargo[0]
                    contextual_data['cargo_info'] = {
                        'package_count': cargo_item.get('no_of_pieces', ''),
                        'type': cargo_item.get('nature_and_quantity_of_goods', ''),
                        'year_of_manufacture': cargo_item.get('year_of_manufacture', ''),
                        'vin': cargo_item.get('vin', ''),
                        'color': cargo_item.get('color', ''),
                        'gross_weight': cargo_item.get('gross_weight_kg', ''),
                        'measurement': cargo_item.get('measurement', ''),
                        'commodity_description': cargo_item.get('nature_and_quantity_of_goods', '')
                    }
                    # Also populate flat structure for HS Code API compatibility
                    contextual_data['weight'] = cargo_item.get('gross_weight_kg', '')
                    contextual_data['commodity'] = cargo_item.get('nature_and_quantity_of_goods', '')
                elif isinstance(cargo, dict):
                    # If cargo is a dict, use the original logic
                    contextual_data['cargo_info'] = {
                        'package_count': cargo.get('package_count_and_description', ''),
                        'type': cargo.get('type', ''),
                        'year_of_manufacture': cargo.get('year_of_manufacture', ''),
                        'vin': cargo.get('vin', ''),
                        'color': cargo.get('color', ''),
                        'gross_weight': cargo.get('gross_weight', ''),
                        'measurement': cargo.get('measurement', ''),
                        'commodity_description': cargo.get('commodity_description', '')
                    }
                    # Also populate flat structure for HS Code API compatibility
                    contextual_data['weight'] = cargo.get('gross_weight', '')
                    contextual_data['commodity'] = cargo.get('commodity_description', '')
        
        # Document metadata
        contextual_data['document_metadata'] = {
            'extraction_confidence': primary_data.get('extraction_confidence', 'unknown'),
            'processing_method': primary_data.get('_metadata', {}).get('processing_method', 'unknown'),
            'extraction_timestamp': primary_data.get('_metadata', {}).get('extraction_timestamp', 'unknown')
        }
        # Also populate flat structure for HS Code API compatibility
        contextual_data['extraction_confidence'] = primary_data.get('extraction_confidence', 'unknown')
        
        # Contextual data built successfully
        # Contextual data keys available
        return contextual_data if contextual_data else None
        
    except Exception as e:
        print(f"❌ DEBUG: Error building contextual data: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_commercial_description(description: str, verbose: bool = False, get_hs_code: bool = True, 
                                 order_id: str = None, primary_data: Dict[str, Any] = None, bol_data: Dict[str, Any] = None) -> Dict[str, str]:
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
            
            # Build contextual data from primary processing results if available
            contextual_data = None
            if primary_data:
                contextual_data = _build_contextual_data_from_primary(primary_data, product_name, bol_data)
                # Contextual data built
            
            hs_result = classify_with_hs_api(
                product_name, 
                verbose=verbose, 
                order_id=order_id,
                contextual_data=contextual_data
            )
            if hs_result:
                results['hs_code'] = hs_result.get('hs_code')
                results['commodity_code'] = hs_result.get('commodity_code')
                results['hs_description'] = hs_result.get('description')
                # Results updated with HS code data
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

class ProductProcessor:
    """Processor class for eSAD product standardization and HS code classification."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the product processor."""
        self.config = config or {}
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process product information from input data."""
        try:
            # Extract data from input
            invoice_data = input_data.get('invoice_data', {})
            bol_data = input_data.get('bol_data', {})
            fields = input_data.get('fields', [])
            existing_fields = input_data.get('existing_fields', {})
            
            # Find commercial description from various sources
            commercial_description = self._extract_commercial_description(invoice_data, bol_data, existing_fields)
            
            if not commercial_description:
                return {
                    'success': False,
                    'error': 'No commercial description found',
                    'commercial_description': '',
                    'commodity_code': ''
                }
            
            # Process the commercial description
            result = process_commercial_description(
                description=commercial_description,
                verbose=False,
                get_hs_code=True,
                order_id=existing_fields.get('order_number'),
                primary_data=invoice_data,
                bol_data=bol_data
            )
            
            if result.get('product_name') or result.get('hs_code'):
                return {
                    'success': True,
                    'commercial_description': result.get('product_name', commercial_description),
                    'commodity_code': result.get('commodity_code', ''),
                    'hs_code': result.get('hs_code', ''),
                    'hs_description': result.get('hs_description', ''),
                    'original_description': commercial_description,
                    'processing_notes': f"Processed: {result.get('product_name', 'N/A')} -> HS: {result.get('hs_code', 'N/A')}"
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'commercial_description': commercial_description,
                    'commodity_code': ''
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'commercial_description': '',
                'commodity_code': ''
            }
    
    def _extract_commercial_description(self, invoice_data: Dict, bol_data: Dict, existing_fields: Dict) -> str:
        """Extract commercial description from various data sources."""
        # Try invoice items first
        if 'items' in invoice_data and invoice_data['items']:
            first_item = invoice_data['items'][0]
            if 'description' in first_item:
                return first_item['description']
        
        # Try BOL particulars
        if 'particulars_furnished_by_shipper_said_to_contain' in bol_data:
            particulars = bol_data['particulars_furnished_by_shipper_said_to_contain']
            if 'package/type' in particulars:
                return particulars['package/type']
        
        # Try existing fields
        if '31_commercial_description' in existing_fields:
            return existing_fields['31_commercial_description']
        
        return ""

if __name__ == "__main__":
    main() 