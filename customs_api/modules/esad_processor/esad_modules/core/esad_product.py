#!/usr/bin/env python3
"""
eSAD Product Processing Module
Extracts and standardizes product names from commercial descriptions
"""

import sys
import json
import re
import time
import requests
from typing import Optional, Dict, List, Any
import os

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from modules.core.llm_client import LLMClient

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Priority models for product processing
PRIORITY_MODELS = []
if "gpt_5" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_5"])
elif "gpt_4o" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o"])
elif "gpt_5_nano" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_5_nano"])

# Fallback to any available model
if not PRIORITY_MODELS and OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(list(OPENROUTER_GENERAL_MODELS.values())[0])


def get_commercial_description_from_json(json_path: str) -> Optional[str]:
    """Extract commercial_description from eSAD results JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        extracted_fields = data['result']['extracted_fields']
        return extracted_fields.get('commercial_description', '')
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return None


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


def ask_llm_for_product_name(description: str, verbose: bool = False) -> Optional[str]:
    """Get the specific product name using LLM."""
    
    if not description or description.lower() in ['not specified', 'none', '']:
        return None
    
    # Clean the description first
    cleaned_description = clean_commercial_description(description)
    if not cleaned_description:
        return None
    
    prompt = f"""
Extract the main product name from this commercial description:

Description: "{cleaned_description}"

Return ONLY a JSON object with:
{{
    "product_name": "The main product name (e.g., 'Lithium Battery Pack', 'Smartphone', 'Coffee Beans')",
    "confidence": "high" | "medium" | "low"
}}

Rules:
- Extract only the main product type/name
- Remove technical specifications, quantities, and shipping details
- Use generic product names (e.g., "Battery Pack" not "DCZ-51.2V280Ah-LY-3.0-JJ03")
- Return null if no clear product can be identified
"""

    for model in PRIORITY_MODELS:
        try:
            raw_response, success, error_type = llm.send_prompt(prompt, model=model)
            
            if not success:
                if verbose:
                    print(f"❌ LLM call failed: {error_type}")
                continue
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                product_name = result.get('product_name')
                
                if product_name and product_name.lower() not in ['null', 'none', '']:
                    if verbose:
                        print(f"✅ Extracted product name: {product_name}")
                    return product_name
                    
        except Exception as e:
            if verbose:
                print(f"❌ Error with model {model}: {e}")
            continue
    
    # Fallback: return first few words if LLM fails
    words = cleaned_description.split()[:3]
    if words:
        return ' '.join(words)
    
    return None


def extract_commercial_description(invoice_data: Dict[str, Any], bol_data: Dict[str, Any]) -> str:
    """Extract commercial description from invoice or BOL data."""
    
    # Check invoice data first - look in items array
    if invoice_data:
        # Check top-level fields first
        for field in ['commercial_description', 'description', 'goods_description', 'product_description']:
            if field in invoice_data and invoice_data[field]:
                return str(invoice_data[field])
        
        # Check items array for product descriptions
        if 'items' in invoice_data and isinstance(invoice_data['items'], list) and len(invoice_data['items']) > 0:
            item = invoice_data['items'][0]
            for field in ['description', 'commercial_description', 'goods_description', 'product_description']:
                if field in item and item[field]:
                    return str(item[field])
    
    # Check BOL data - look in containers_packages array
    if bol_data:
        # Check top-level fields first
        for field in ['cargo_description', 'goods_description', 'description', 'commercial_description']:
            if field in bol_data and bol_data[field]:
                return str(bol_data[field])
        
        # Check containers_packages array for commodity descriptions
        if 'containers_packages' in bol_data and isinstance(bol_data['containers_packages'], list) and len(bol_data['containers_packages']) > 0:
            container = bol_data['containers_packages'][0]
            for field in ['commodity', 'cargo_description', 'description', 'goods_description']:
                if field in container and container[field]:
                    return str(container[field])
    
    return ""


def process_product_data(invoice_data: Dict[str, Any], bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """
    Complete product data processing workflow.
    
    Args:
        invoice_data: Invoice data dictionary
        bol_data: BOL data dictionary
        verbose: Whether to show verbose output
        
    Returns:
        Dictionary with processed product data ready for HS code API
    """
    try:
        # Step 1: Extract commercial description
        commercial_description = extract_commercial_description(invoice_data, bol_data)
        
        if not commercial_description:
            return {
                'success': False,
                'error': 'No commercial description found in invoice or BOL data',
                'commercial_description': '',
                'product_name': '',
                'contextual_data': {},
                'processing_notes': 'No product description available for classification'
            }
        
        # Step 2: Clean the description
        cleaned_description = clean_commercial_description(commercial_description)
        
        # Step 3: Extract product name using LLM
        product_name = ask_llm_for_product_name(cleaned_description, verbose=verbose)
        if not product_name:
            product_name = cleaned_description
        
        # Step 4: Extract contextual data using LLM
        contextual_data = extract_contextual_data_with_llm(invoice_data, bol_data, verbose=verbose)
        
        return {
            'success': True,
            'commercial_description': cleaned_description,
            'original_description': commercial_description,
            'product_name': product_name,
            'contextual_data': contextual_data,
            'processing_notes': 'Product data processing completed successfully'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Product data processing failed: {str(e)}',
            'commercial_description': '',
            'product_name': '',
            'contextual_data': {},
            'processing_notes': f'Exception during processing: {str(e)}'
        }
    

def extract_contextual_data_with_llm(invoice_data: Dict[str, Any], bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Extract and structure contextual data using LLM from invoice and BOL data."""
    
    try:
        # Extract BOL contextual data using LLM
        bol_context = extract_bol_context_with_llm(bol_data, verbose)
        
        # Extract invoice contextual data using LLM
        invoice_context = extract_invoice_context_with_llm(invoice_data, verbose)
        
        # Structure the data with only classification-relevant fields
        contextual_data = {
            # Product details (essential for classification)
            'product_details': {
                'description': invoice_context.get('product_description', ''),
                'quantity': invoice_context.get('quantity', 0),
                'unit_of_measure': invoice_context.get('unit_of_measure', ''),
                'country_of_origin': invoice_context.get('country_of_origin', ''),
                'value': invoice_context.get('total_value', 0),
                'currency': invoice_context.get('currency', '')
            },
            
            # Shipping information (relevant for classification context)
            'shipping_info': {
                'port_of_loading': bol_context.get('port_of_loading', ''),
                'port_of_discharge': bol_data.get('vessel_info', {}).get('port_of_destination', ''),
                'weight': f"{bol_context.get('gross_weight', 0)} {bol_context.get('weight_unit', '')}",
                'delivery_terms': invoice_data.get('shipping', {}).get('delivery_terms', '')
            },
            
            # Cargo information (relevant for classification)
            'cargo_info': {
                'description': bol_context.get('cargo_description', ''),
                'gross_weight': bol_context.get('gross_weight', 0),
                'weight_unit': bol_context.get('weight_unit', ''),
                'number_of_packages': bol_context.get('number_of_packages', 0),
                'package_type': bol_context.get('package_type', '')
            }
        }
        
        if verbose:
            print(f"🔍 Extracted contextual data: {json.dumps(contextual_data, indent=2)}")
        
        return contextual_data
        
    except Exception as e:
        if verbose:
            print(f"❌ Error extracting contextual data: {e}")
        return {}
    

def extract_bol_context_with_llm(bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
        """Extract BOL contextual data using LLM."""
        
        prompt = f"""
Extract the following fields from the BOL data and return ONLY a JSON object with these exact keys:

Required fields:
- cargo_description: string (main cargo/goods description)
- gross_weight: number (total weight as number, not string)
- weight_unit: string (unit like "KG", "KGM", "LB", etc.)
- port_of_loading: string (port where cargo was loaded)
- shipper_country: string (country of the shipper)
- number_of_packages: number (total number of packages as number)
- package_type: string (type of packaging like "BOX", "CARTON", "PALLET", etc.)

BOL Data:
{json.dumps(bol_data, indent=2)}

Return ONLY the JSON object with these 7 fields. If a field cannot be determined, use empty string "" for strings or 0 for numbers.
"""

        try:
            for model in PRIORITY_MODELS:
                if verbose:
                    print(f"🔍 Extracting BOL context using {model}...")
                
                response_text, success, error_type = llm.send_prompt(prompt, model=model)
                
                if not success:
                    if verbose:
                        print(f"❌ LLM request failed with {model}: {error_type}")
                    continue
                
                # Parse JSON response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    if verbose:
                        print(f"✅ BOL context extracted successfully")
                    return result
                    
        except Exception as e:
            if verbose:
                print(f"❌ Error extracting BOL context: {e}")
        
        # Return empty structure if LLM fails
        return {
            "cargo_description": "",
            "gross_weight": 0,
            "weight_unit": "",
            "port_of_loading": "",
            "shipper_country": "",
            "number_of_packages": 0,
            "package_type": ""
        }
    

def extract_invoice_context_with_llm(invoice_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
        """Extract invoice contextual data using LLM."""
        
        prompt = f"""
Extract the following fields from the invoice data and return ONLY a JSON object with these exact keys:

Required fields:
- product_description: string (main product/goods description)
- country_of_origin: string (country where the goods were manufactured/produced)
- quantity: number (quantity as number, not string)
- unit_of_measure: string (unit like "PCS", "KG", "SET", "PAIR", etc.)
- unit_price: number (price per unit as number)
- total_value: number (total value/amount as number)
- currency: string (currency code like "USD", "EUR", "GBP", etc.)

Invoice Data:
{json.dumps(invoice_data, indent=2)}

Return ONLY the JSON object with these 7 fields. If a field cannot be determined, use empty string "" for strings or 0 for numbers.
"""

        try:
            for model in PRIORITY_MODELS:
                if verbose:
                    print(f"🔍 Extracting invoice context using {model}...")
                
                response_text, success, error_type = llm.send_prompt(prompt, model=model)
                
                if not success:
                    if verbose:
                        print(f"❌ LLM request failed with {model}: {error_type}")
                    continue
                
                # Parse JSON response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    if verbose:
                        print(f"✅ Invoice context extracted successfully")
                    return result
                    
        except Exception as e:
            if verbose:
                print(f"❌ Error extracting invoice context: {e}")
        
        # Return empty structure if LLM fails
        return {
            "product_description": "",
            "country_of_origin": "",
            "quantity": 0,
            "unit_of_measure": "",
            "unit_price": 0,
            "total_value": 0,
            "currency": ""
        }
    

class ProductProcessor:
    """API client for HS code classification - accepts pre-processed data."""
    
    def __init__(self):
        self.hscode_api_url = "http://localhost:5000/classify"
        self.stream_url = "http://localhost:5000/classify/stream"
        self.timeout = 300  # 5 minute timeout for HS code API calls
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process product information (backward compatibility method).
        
        Args:
            input_data: Dictionary containing invoice_data and bol_data
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract invoice and BOL data
            invoice_data = input_data.get('invoice_data', {})
            bol_data = input_data.get('bol_data', {})
            
            # Use the new workflow function
            processed_data = process_product_data(invoice_data, bol_data, verbose=False)
            
            if not processed_data['success']:
                return processed_data
            
            # Submit to HS code API for classification
            api_result = self.classify_product(
                product_name=processed_data['product_name'],
                contextual_data=processed_data['contextual_data'],
                use_streaming=True
            )
            
            if api_result.get('success'):
                return {
                    'success': True,
                    'product_name': processed_data['product_name'],
                    'commercial_description': processed_data['commercial_description'],
                    'original_description': processed_data['original_description'],
                    'hs_code': api_result.get('hs_code', ''),
                    'commodity_code': api_result.get('commodity_code', ''),
                    'hs_description': api_result.get('hs_description', ''),
                    'contextual_data': processed_data['contextual_data'],
                    'api_response': api_result.get('raw_response', {}),
                    'processing_notes': 'Successfully classified using HS code API with contextual data'
                }
            else:
                return {
                    'success': False,
                    'error': api_result.get('error', 'HS code classification failed'),
                    'product_name': processed_data['product_name'],
                    'commercial_description': processed_data['commercial_description'],
                    'original_description': processed_data['original_description'],
                    'hs_code': '',
                    'commodity_code': '',
                    'hs_description': '',
                    'contextual_data': processed_data['contextual_data'],
                    'processing_notes': f'HS code API failed: {api_result.get("error", "Unknown error")}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Product processing failed: {str(e)}',
                'commercial_description': '',
                'hs_code': '',
                'commodity_code': '',
                'hs_description': '',
                'original_description': '',
                'processing_notes': f'Exception during processing: {str(e)}'
            }
    
    def classify_product(self, product_name: str, contextual_data: Dict[str, Any], use_streaming: bool = True) -> Dict[str, Any]:
        """
        Submit pre-processed product data to HS code API for classification.
        
        Args:
            product_name: The product name to classify
            contextual_data: Pre-extracted contextual data
            use_streaming: Whether to use streaming API (default: True)
            
        Returns:
            Dictionary with classification results including hs_code, commodity_code, etc.
        """
        try:
            if use_streaming:
                return self._call_hscode_api_streaming(product_name, contextual_data)
            else:
                return self._call_hscode_api_with_context(product_name, contextual_data)
                
        except Exception as e:
            return {
                'success': False,
                'error': f'HS code classification failed: {str(e)}',
                'hs_code': '',
                'commodity_code': '',
                'hs_description': '',
                'processing_notes': f'Exception during API call: {str(e)}'
            }
    
    
    def _call_hscode_api_streaming(self, product_name: str, contextual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call the HS code API with streaming to show progress."""
        
        try:
            # Prepare request payload with extracted contextual data
            payload = {
                "product_name": product_name,
                "verbose": False,
                "contextual_data": contextual_data
            }
            
            print(f"🔄 Starting HS code classification for: {product_name}")
            print("📡 Connecting to HS code API with streaming...")
            
            # Make streaming API request
            response = requests.post(
                self.stream_url,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'},
                stream=True
            )
            
            if response.status_code == 200:
                print("✅ Connected to HS code API. Processing classification...")
                
                # Process streaming response
                final_result = None
                for line in response.iter_lines(decode_unicode=True):
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            
                            # Debug: print the structure we're receiving
                            if data.get('object'):
                                print(f"🔍 Received object: {data.get('object')}")
                            
                            # Handle different types of streaming data
                            if data.get('object') == 'classification.thinking':
                                step = data.get('choices', [{}])[0].get('delta', {}).get('step', '')
                                message = data.get('choices', [{}])[0].get('delta', {}).get('message', '')
                                if step and message:
                                    print(f"🔄 {message}")
                            
                            elif data.get('object') == 'classification.chunk':
                                # Text chunks - might contain results
                                content = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                if content and ('hs_code' in content.lower() or 'commodity_code' in content.lower()):
                                    print(f"🔍 Found potential results in chunk: {content[:100]}...")
                            
                            elif data.get('object') == 'classification.complete':
                                # Stream completed - try to extract results from the response
                                print("✅ Stream completed, extracting results...")
                                # For now, let's fall back to non-streaming API
                                return self._call_hscode_api_with_context(product_name, contextual_data)
                            
                            elif data.get('object') == 'classification.results':
                                # This is the final result
                                final_result = data.get('data', {})
                                print(f"✅ Received final results: {final_result}")
                                break
                                
                        except json.JSONDecodeError:
                            continue
                
                if final_result:
                    return {
                        'success': True,
                        'hs_code': final_result.get('hs_code'),
                        'commodity_code': final_result.get('commodity_code'),
                        'description': final_result.get('description'),
                        'raw_response': final_result
                    }
                else:
                    return {
                        'success': False,
                        'error': 'No final result received from streaming API'
                    }
            else:
                return {
                    'success': False,
                    'error': f'HS code API returned status {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f'HS code API request timed out after {self.timeout} seconds'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Could not connect to HS code API. Is it running on localhost:5000?'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'HS code API request failed: {str(e)}'
            }
    
    def _call_hscode_api_with_context(self, product_name: str, contextual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call the HS code API with extracted contextual data."""
        
        try:
            # Prepare request payload with extracted contextual data
            payload = {
                "product_name": product_name,
                "verbose": False,
                "contextual_data": contextual_data
            }
            
            # Make API request
            response = requests.post(
                self.hscode_api_url,
                json=payload,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'hs_code': result.get('hs_code'),
                    'commodity_code': result.get('commodity_code'),
                    'description': result.get('description'),
                    'raw_response': result
                }
            else:
                return {
                    'success': False,
                    'error': f'HS code API returned status {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f'HS code API request timed out after {self.timeout} seconds'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Could not connect to HS code API. Is it running on localhost:5000?'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'HS code API request failed: {str(e)}'
            }
    
    


def main():
    """Main function for standalone testing of the product module."""
    print("🧪 Product Module - HS Code Classification Integration")
    print("=" * 60)
    print("This module provides:")
    print("• ProductProcessor class for HS code API integration")
    print("• Product name extraction and cleaning functions")
    print("• Commercial description processing")
    print()
    print("Usage:")
    print("• Import ProductProcessor in eSAD processing workflows")
    print("• Call processor.process(input_data) with invoice_data and bol_data")
    print("• Returns structured results with hs_code, commodity_code, etc.")
    print()
    print("For testing, use the test scripts in the test/ directory.")


if __name__ == "__main__":
    main()