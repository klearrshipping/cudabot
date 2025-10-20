#!/usr/bin/env python3
"""
eSAD Regime Type Processor
Determines appropriate regime type using contextual analysis and LLM reasoning
"""

import json
import re
import time
import logging
import traceback
import os
import sys
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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

# Priority models for regime processing
PRIORITY_MODELS = []
if "gpt_4o_mini" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o_mini"])
elif "gpt_4o" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o"])
elif "gpt_5_nano" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_5_nano"])

# Fallback to any available model
if not PRIORITY_MODELS and OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(list(OPENROUTER_GENERAL_MODELS.values())[0])

# Import product classification module
try:
    from .esad_product_classification import classify_product_commercial_vs_personal
except ImportError:
    from esad_product_classification import classify_product_commercial_vs_personal

# Import port extraction function from esad_ports
try:
    from .esad_ports import extract_ports_from_bol
except ImportError:
    from esad_ports import extract_ports_from_bol

# Import CSV data client for regime types
try:
    from modules.core.csv_data_client import fetch_regime_types
except ImportError:
    from modules.core.csv_data_client import fetch_regime_types

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def determine_trade_lane(port_data: Dict[str, Any]) -> str:
    """Determine trade lane based on port information."""
    
    # Extract port names from the new dictionary structure
    origin_port = port_data.get('origin_port', {})
    destination_port = port_data.get('destination_port', {})
    
    # Get port names, handling both string and dict formats
    if isinstance(origin_port, dict):
        origin = origin_port.get('port_name', '').lower()
    else:
        origin = str(origin_port).lower()
    
    if isinstance(destination_port, dict):
        destination = destination_port.get('port_name', '').lower()
    else:
        destination = str(destination_port).lower()
    
    # Common trade lane patterns
    if any(port in origin for port in ['hong kong', 'shanghai', 'shenzhen', 'guangzhou']):
        if 'kingston' in destination or 'jamaica' in destination:
            return 'Asia-Caribbean'
        elif any(port in destination for port in ['miami', 'new york', 'los angeles']):
            return 'Asia-Americas'
    
    if any(port in origin for port in ['rotterdam', 'hamburg', 'antwerp']):
        if 'kingston' in destination or 'jamaica' in destination:
            return 'Europe-Caribbean'
        elif any(port in destination for port in ['miami', 'new york']):
            return 'Europe-Americas'
    
    if any(port in origin for port in ['miami', 'new york', 'los angeles']):
        if 'kingston' in destination or 'jamaica' in destination:
            return 'Americas-Caribbean'
    
    return 'Unknown'


def is_motor_vehicle(description: str) -> bool:
    """Check if product description indicates a motor vehicle using LLM."""
    
    if not description:
        return False
    
    # Simple keyword check first (faster)
    vehicle_keywords = [
        'car', 'truck', 'vehicle', 'automobile', 'motor', 'engine',
        'sedan', 'suv', 'pickup', 'van', 'bus', 'motorcycle', 'bike'
    ]
    
    description_lower = description.lower()
    if not any(keyword in description_lower for keyword in vehicle_keywords):
        return False
    
    # Use LLM for more sophisticated analysis
    prompt = f"""
Analyze this product description to determine if it's a motor vehicle:

Description: "{description}"

Return ONLY a JSON object:
{{
  "is_motor_vehicle": true or false,
  "confidence": "high" | "medium" | "low",
  "reasoning": "Brief explanation"
}}
"""
    
    for model in PRIORITY_MODELS:
        try:
            response_text, success, error_type = llm.send_prompt(prompt, model=model)
            
            if not success:
                logger.warning(f"LLM motor vehicle detection failed with {model}: {error_type}")
                continue
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get('is_motor_vehicle', False)
                
        except Exception as e:
            logger.warning(f"LLM motor vehicle detection failed with {model}: {e}")
            continue
    
    # Fallback to keyword matching
    return True


def extract_invoice_value(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract invoice value information."""
    
    totals = invoice_data.get('totals', {})
    currency = invoice_data.get('currency', 'USD')
    
    return {
        'total_amount': totals.get('total_amount', 0),
        'subtotal': totals.get('subtotal', 0),
        'shipping': totals.get('shipping_handling', 0),
        'currency': currency
    }


class RegimeTypeProcessor:
    """Processor for determining eSAD regime type using contextual analysis."""
    
    def __init__(self):
        self.contextual_factors = {}
        self.processing_time = 0
        self.model = "unknown"
    
    def process_regime_type(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process regime type determination."""
        
        start_time = time.time()
        
        try:
            # Extract data components
            invoice_data = extracted_data.get('invoice_data', {})
            bol_data = extracted_data.get('bol_data', {})
            
            # Step 1: Product classification
            product_classification = classify_product_commercial_vs_personal(invoice_data, bol_data)
            
            # Step 2: Port extraction (suppress output)
            import io
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                port_data_result = extract_ports_from_bol(bol_data, invoice_data)
                port_data = port_data_result.get('port_data', {})
            
            # Step 3: Trade lane determination
            trade_lane = determine_trade_lane(port_data)
            
            # Step 4: Invoice value analysis
            invoice_value = extract_invoice_value(invoice_data)
            
            # Step 5: Motor vehicle check
            description = ""
            if invoice_data.get('items'):
                description = invoice_data['items'][0].get('description', '')
            
            is_vehicle = is_motor_vehicle(description)
            
            # Step 6: Regime determination logic
            regime_result = self._determine_regime_type(
                product_classification, trade_lane, invoice_value, is_vehicle
            )
            
            processing_time = time.time() - start_time
            
            # Extract country information from port data
            country_info = self._extract_country_info(port_data)
            
            # Extract regime type data
            regime_type_data = self._extract_regime_type_data(regime_result['regime_type'])
            
            result_obj = {
                'success': True,
                'regime_type': regime_result['regime_type'],
                'description': regime_result['description'],
                'confidence': regime_result['confidence'],
                'reasoning': regime_result['reasoning'],
                'contextual_factors': {
                    'product_classification': product_classification,
                    'trade_lane': trade_lane,
                    'invoice_value': invoice_value,
                    'is_motor_vehicle': is_vehicle
                },
                'country_info': country_info,
                'regime_type_data': regime_type_data,
                'processing_time': processing_time,
                'model': self.model
            }
            # Emit only country_info and regime_type_data to server log
            try:
                log_data = {
                    "country_info": country_info,
                    "regime_type_data": regime_type_data
                }
                print(json.dumps(log_data, indent=2, ensure_ascii=False))
            except Exception:
                pass
            return result_obj
            
        except Exception as e:
            logger.error(f"Error in regime type processing: {e}")
            error_obj = {
                'success': False,
                'error': str(e),
                'regime_type': 'Unknown',
                'description': 'Processing failed',
                'confidence': 'low',
                'reasoning': f'Error: {str(e)}',
                'processing_time': time.time() - start_time
            }
            # Emit empty country_info and regime_type_data for errors
            try:
                error_log_data = {
                    "country_info": {
                        "Export": {
                            "Export_country_code": "Unknown",
                            "Export_country_name": "Unknown",
                            "Export_country_region": None
                        },
                        "Destination": {
                            "Destination_country_code": "Unknown", 
                            "Destination_country_name": "Unknown",
                            "Destination_country_region": None
                        },
                        "Country": {
                            "Country_of_origin_name": "Unknown"
                        }
                    },
                    "regime_type_data": {
                        "Type_of_declaration": "Unknown",
                        "Declaration_gen_procedure_code": "0"
                    }
                }
                print(json.dumps(error_log_data, indent=2, ensure_ascii=False))
            except Exception:
                pass
            return error_obj
    
    def _extract_country_info(self, port_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract country information from port data."""
        
        # Default values
        export_country_code = "CN"
        export_country_name = "China"
        destination_country_code = "JM"
        destination_country_name = "Jamaica"
        country_of_origin_name = "China"
        
        # Extract origin port information
        origin_port = port_data.get('origin_port', {})
        if isinstance(origin_port, dict):
            origin_country = origin_port.get('country_code', export_country_code)
            origin_name = origin_port.get('country_name', export_country_name)
            if origin_country and origin_name:
                export_country_code = origin_country
                export_country_name = origin_name
                country_of_origin_name = origin_name
        
        # Extract destination port information
        destination_port = port_data.get('destination_port', {})
        if isinstance(destination_port, dict):
            dest_country = destination_port.get('country_code', destination_country_code)
            dest_name = destination_port.get('country_name', destination_country_name)
            if dest_country and dest_name:
                destination_country_code = dest_country
                destination_country_name = dest_name
        
        return {
            "Export": {
                "Export_country_code": export_country_code,
                "Export_country_name": export_country_name,
                "Export_country_region": None
            },
            "Destination": {
                "Destination_country_code": destination_country_code,
                "Destination_country_name": destination_country_name,
                "Destination_country_region": None
            },
            "Country": {
                "Country_of_origin_name": country_of_origin_name
            }
        }

    def _extract_regime_type_data(self, regime_type: str) -> Dict[str, Any]:
        """Extract regime type data in the specified format."""
        
        # Parse regime type (e.g., "IMS4" -> "IMS" and "4")
        if len(regime_type) >= 3:
            type_of_declaration = regime_type[:-1]  # Everything except last character
            declaration_gen_procedure_code = regime_type[-1]  # Last character
        else:
            # Fallback for unexpected format
            type_of_declaration = regime_type
            declaration_gen_procedure_code = "0"
        
        return {
            "Type_of_declaration": type_of_declaration,
            "Declaration_gen_procedure_code": declaration_gen_procedure_code
        }

    def _determine_regime_type(self, product_classification: Dict, trade_lane: str, 
                              invoice_value: Dict, is_vehicle: bool) -> Dict[str, Any]:
        """Determine the appropriate regime type based on contextual factors."""
        
        # Extract classification results
        classification_type = product_classification.get('product_classification', 'unknown')
        is_commercial = classification_type == 'commercial'
        
        # Load regime types from CSV
        regime_types = fetch_regime_types()
        
        # Find the appropriate regime type based on classification
        if is_vehicle:
            # Motor vehicles use IM4 (Commercial Import)
            regime = next((rt for rt in regime_types if rt.get('regime_type') == 'IM4'), None)
            if regime:
                return {
                    'regime_type': regime['regime_type'],
                    'description': regime['description'],
                    'confidence': 'high',
                    'reasoning': 'Product identified as motor vehicle',
                    'regime_details': regime['details']
                }
        
        if is_commercial:
            # Commercial goods use IM4
            regime = next((rt for rt in regime_types if rt.get('regime_type') == 'IM4'), None)
            if regime:
                return {
                    'regime_type': regime['regime_type'],
                    'description': regime['description'],
                    'confidence': 'high',
                    'reasoning': 'Product classified as commercial use',
                    'regime_details': regime['details']
                }
        
        # Personal goods use IMS4 (Simplified Declaration)
        regime = next((rt for rt in regime_types if rt.get('regime_type') == 'IMS4'), None)
        if regime:
            return {
                'regime_type': regime['regime_type'],
                'description': regime['description'],
                'confidence': 'medium',
                'reasoning': 'Product classified as personal use',
                'regime_details': regime['details']
            }
        
        # Fallback if regime types not found
        return {
            'regime_type': 'IMS4',
            'description': 'Personal Import (Simplified Declaration)',
            'confidence': 'low',
            'reasoning': 'Product classified as personal use (fallback)',
            'regime_details': 'Fallback regime type'
        }


def select_cpc_for_regime_type(regime_type: str, invoice_data: Dict[str, Any], 
                              bol_data: Dict[str, Any], arrival_notice: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Select appropriate CPC based on regime type using LLM analysis.
    
    Args:
        regime_type: The selected regime type (e.g., "IMS4")
        invoice_data: Invoice data for context
        bol_data: Bill of Lading data for context
        arrival_notice: Arrival notice data (optional)
    
    Returns:
        Dict containing selected CPC and reasoning
    """
    
    try:
        # Step 1: Load CPC data and filter by regime_type_model
        cpc_data = _load_cpc_data()
        regime_type_model = _extract_regime_type_model(regime_type)
        
        if not regime_type_model:
            return {
                'success': False,
                'error': f'Could not extract regime_type_model from {regime_type}',
                'selected_cpc': None,
                'reasoning': 'Invalid regime type format'
            }
        
        # Filter CPC data by regime_type_model
        matching_cpcs = [cpc for cpc in cpc_data if cpc.get('regime_type_model') == regime_type_model]
        
        if not matching_cpcs:
            return {
                'success': False,
                'error': f'No CPCs found for regime_type_model: {regime_type_model}',
                'selected_cpc': None,
                'reasoning': 'No matching CPCs available'
            }
        
        # Step 2: Call esad_product_classification to determine transaction type
        transaction_classification = classify_product_commercial_vs_personal(invoice_data, bol_data)
        
        # Step 3: Use LLM to select appropriate CPC
        selected_cpc = _select_cpc_with_llm(
            matching_cpcs, 
            invoice_data, 
            bol_data, 
            arrival_notice, 
            transaction_classification
        )
        
        return {
            'success': True,
            'selected_cpc': selected_cpc,
            'regime_type_model': regime_type_model,
            'transaction_classification': transaction_classification,
            'available_cpcs': len(matching_cpcs),
            'reasoning': selected_cpc.get('reasoning', 'CPC selected based on context analysis')
        }
        
    except Exception as e:
        logger.error(f"Error in CPC selection: {e}")
        return {
            'success': False,
            'error': str(e),
            'selected_cpc': None,
            'reasoning': f'Error during CPC selection: {str(e)}'
        }


def _load_cpc_data() -> List[Dict[str, Any]]:
    """Load CPC data from JSON file."""
    
    try:
        # Get the path to the CPC JSON file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        cpc_file_path = os.path.join(current_dir, '..', '..', '..', '..', 'data', 'cpc.json')
        
        with open(cpc_file_path, 'r', encoding='utf-8') as f:
            cpc_data = json.load(f)
        
        return cpc_data
        
    except Exception as e:
        logger.error(f"Error loading CPC data: {e}")
        return []


def _extract_regime_type_model(regime_type: str) -> str:
    """Extract regime_type_model from regime_type."""
    
    # Map regime types to their models
    regime_mapping = {
        'IMS4': 'IMS4',
        'IM4': 'IM4', 
        'BG4': 'BG4',
        'EX10': 'EX10',
        'EX11': 'EX11',
        # Add more mappings as needed
    }
    
    return regime_mapping.get(regime_type, regime_type)


def _select_cpc_with_llm(matching_cpcs: List[Dict[str, Any]], 
                        invoice_data: Dict[str, Any], 
                        bol_data: Dict[str, Any], 
                        arrival_notice: Dict[str, Any], 
                        transaction_classification: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM to select the most appropriate CPC from matching options."""
    
    # Prepare context data
    context_data = _prepare_context_for_cpc_selection(
        invoice_data, bol_data, arrival_notice, transaction_classification
    )
    
    # Format CPC options for LLM
    cpc_options = []
    for i, cpc in enumerate(matching_cpcs, 1):
        cpc_options.append(f"{i}. CPC: {cpc['cpc']} - {cpc['description']}")
        cpc_options.append(f"   Detail: {cpc['detail']}")
        cpc_options.append("")
    
    cpc_options_text = "\n".join(cpc_options)
    
    # Create LLM prompt
    prompt = f"""
You are a customs expert analyzing shipment data to select the most appropriate CPC (Customs Procedure Code).

CONTEXT DATA:
{context_data}

AVAILABLE CPC OPTIONS:
{cpc_options_text}

TRANSACTION CLASSIFICATION:
- Type: {transaction_classification.get('product_classification', 'unknown')}
- Reasoning: {transaction_classification.get('reasoning', 'No reasoning provided')}

INSTRUCTIONS:
1. Analyze the context data (invoice, BOL, arrival notice)
2. Consider the transaction classification (commercial vs personal)
3. Select the most appropriate CPC from the available options
4. Provide detailed reasoning for your selection

Return ONLY a JSON object:
{{
  "selected_cpc_number": <option_number_1_to_{len(matching_cpcs)}>,
  "confidence": "high" | "medium" | "low",
  "reasoning": "Detailed explanation of why this CPC was selected",
  "key_factors": ["factor1", "factor2", "factor3"]
}}

CRITICAL: selected_cpc_number must be the OPTION NUMBER (1, 2, 3, or {len(matching_cpcs)}), NOT the CPC code (4000, 4500, etc.)
"""
    
    # Try each priority model
    for model in PRIORITY_MODELS:
        try:
            response_text, success, error_type = llm.send_prompt(prompt, model=model)
            
            if not success:
                logger.warning(f"LLM CPC selection failed with {model}: {error_type}")
                continue
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate the selected CPC number
                selected_number = result.get('selected_cpc_number', 0)
                
                # Debug logging
                logger.debug(f"LLM returned selected_cpc_number: {selected_number}, expected range: 1-{len(matching_cpcs)}")
                
                # Check if LLM returned CPC code instead of option number
                if isinstance(selected_number, int) and selected_number > len(matching_cpcs):
                    # Try to find the CPC code in matching_cpcs and convert to option number
                    for i, cpc in enumerate(matching_cpcs):
                        if cpc.get('cpc') == selected_number:
                            selected_number = i + 1
                            logger.info(f"Converted CPC code {cpc.get('cpc')} to option number {selected_number}")
                            break
                
                if 1 <= selected_number <= len(matching_cpcs):
                    selected_cpc = matching_cpcs[selected_number - 1]
                    result['selected_cpc'] = selected_cpc
                    result['model_used'] = model
                    return result
                else:
                    logger.warning(f"Invalid CPC number selected: {selected_number} (expected 1-{len(matching_cpcs)})")
                    logger.debug(f"LLM response: {response_text}")
                    continue
                    
        except Exception as e:
            logger.warning(f"LLM CPC selection failed with {model}: {e}")
            continue
    
    # Fallback: return first CPC with low confidence
    logger.warning("LLM CPC selection failed, using fallback")
    return {
        'selected_cpc': matching_cpcs[0],
        'confidence': 'low',
        'reasoning': 'Fallback selection - LLM analysis failed',
        'key_factors': ['fallback'],
        'model_used': 'fallback'
    }


def _prepare_context_for_cpc_selection(invoice_data: Dict[str, Any], 
                                     bol_data: Dict[str, Any], 
                                     arrival_notice: Dict[str, Any], 
                                     transaction_classification: Dict[str, Any]) -> str:
    """Prepare context data for CPC selection."""
    
    context_parts = []
    
    # Invoice context
    if invoice_data:
        context_parts.append("INVOICE DATA:")
        if invoice_data.get('items'):
            for item in invoice_data['items']:
                context_parts.append(f"- Product: {item.get('description', 'N/A')}")
                context_parts.append(f"  Quantity: {item.get('quantity', 'N/A')}")
                context_parts.append(f"  Unit Price: ${item.get('unit_price', 'N/A')}")
                context_parts.append(f"  Total Price: ${item.get('total_price', 'N/A')}")
        
        totals = invoice_data.get('totals', {})
        if totals:
            context_parts.append(f"- Total Amount: ${totals.get('total_amount', 'N/A')}")
            context_parts.append(f"- Currency: {invoice_data.get('currency', 'N/A')}")
    
    # BOL context
    if bol_data:
        context_parts.append("\nBOL DATA:")
        vessel_info = bol_data.get('vessel_info', {})
        if vessel_info:
            context_parts.append(f"- Port of Loading: {vessel_info.get('port_of_loading', 'N/A')}")
            context_parts.append(f"- Port of Destination: {vessel_info.get('port_of_destination', 'N/A')}")
        
        cargo_info = bol_data.get('cargo_summary_table', {})
        if cargo_info:
            context_parts.append(f"- Cargo Description: {cargo_info.get('description', 'N/A')}")
            context_parts.append(f"- Cargo Weight: {cargo_info.get('weight', 'N/A')}")
    
    # Arrival notice context
    if arrival_notice:
        context_parts.append("\nARRIVAL NOTICE DATA:")
        context_parts.append(f"- Arrival Date: {arrival_notice.get('arrival_date', 'N/A')}")
        context_parts.append(f"- Vessel: {arrival_notice.get('vessel_name', 'N/A')}")
    
    return "\n".join(context_parts)


def main():
    """Main function for testing with real data."""
    # Load real data from the same files as test_esad_modules.py
    try:
        invoice_file = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\invoices\invoice_ORD-20251015-001_invoice_1_extract.json"
        bol_file = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\bills_of_lading\bill_of_lading_ORD-20251015-001_primary_extract.json"
        
        with open(invoice_file, 'r', encoding='utf-8') as f:
            test_invoice = json.load(f)
        
        with open(bol_file, 'r', encoding='utf-8') as f:
            test_bol = json.load(f)
            
        print("📋 Testing esad_regime.py with REAL DATA")
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ Error loading real data: {e}")
        print("Using fallback test data...")
        # Fallback to test data
        test_invoice = {
            "items": [{"description": "Lithium battery pack for commercial use", "total_price": 1000}],
            "totals": {"total_amount": 1200, "subtotal": 1000, "shipping_handling": 200},
            "currency": "USD"
        }
        
        test_bol = {
            "vessel_info": {
                "port_of_loading": "Hong Kong",
                "port_of_destination": "Kingston"
            }
        }
    
    print("🧪 Testing Regime Module...")
    processor = RegimeTypeProcessor()
    result = processor.process_regime_type({
        'invoice_data': test_invoice,
        'bol_data': test_bol
    })
    # Server log data is already printed by process_regime_type method
    
    # Test CPC selection
    if result.get('success') and result.get('regime_type'):
        print(f"\n🧪 Testing CPC Selection for regime: {result['regime_type']}")
        cpc_result = select_cpc_for_regime_type(
            result['regime_type'], 
            test_invoice, 
            test_bol
        )
        # Print CPC result in JSON format
        if cpc_result.get('success'):
            selected_cpc = cpc_result.get('selected_cpc', {}).get('selected_cpc', {})
            cpc_summary = {
                "regime_type_model": cpc_result.get('regime_type_model', 'Unknown'),
                "cpc": selected_cpc.get('cpc', 'N/A'),
                "description": selected_cpc.get('description', 'N/A'),
                "reasoning": cpc_result.get('selected_cpc', {}).get('reasoning', 'No reasoning provided')
            }
            print(f"📋 CPC Result: {json.dumps(cpc_summary, indent=2, ensure_ascii=False)}")
        else:
            print(f"📋 CPC Result: {cpc_result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()