#!/usr/bin/env python3
"""
ESAD CIF Processing Script
Uses LLM to analyze invoice and BOL data to extract CIF components (Cost, Insurance, Freight)
"""

import json
import re
import sys
from typing import Dict, Any, Optional
from modules.core.llm_client import LLMClient

def ask_llm_for_cif_components(invoice_data: Dict, bol_data: Dict) -> Dict[str, Any]:
    """Get CIF components using LLM analysis."""
    # Optimized model selection: Use general models for financial analysis
    from config import OPENROUTER_GENERAL_MODELS
    priority_models = [
        OPENROUTER_GENERAL_MODELS["gpt_5"],        # Primary - Best for financial analysis
        OPENROUTER_GENERAL_MODELS["kimi_standard"]       # Backup - Reliable fallback
    ]
    
    llm = LLMClient()
    
    # Format the data for the prompt
    invoice_summary = {
        "items": invoice_data.get("items", []),
        "totals": invoice_data.get("totals", {}),
        "currency": invoice_data.get("currency", "USD"),
        "terms": invoice_data.get("invoice_details", {}).get("terms_of_sale", "")
    }
    
    bol_summary = {
        "freight_and_charges": bol_data.get("freight_and_charges", ""),
        "charges_table": bol_data.get("charges_table", []),
        "vessel_and_voyage": bol_data.get("vessel_and_voyage", ""),
        "freight_charge_amount": bol_data.get("freight_charge_amount", ""),
        "cargo_summary_table": bol_data.get("cargo_summary_table", {})
    }
    
    prompt = f"""
You are a customs documentation expert. Analyze the following invoice and bill of lading data to EXTRACT raw CIF-related values:

INVOICE DATA:
{json.dumps(invoice_summary, indent=2)}

BILL OF LADING DATA:
{json.dumps(bol_summary, indent=2)}

EXTRACTION REQUIREMENTS:

FOR INVOICE:
1. Extract total invoice amount (total amount of the invoice)
2. Extract goods value only (excluding freight, insurance, other charges)
3. Extract freight cost if any (separate from goods value)
4. Extract insurance cost if any (separate from goods value)
5. Extract other costs if any (separate from goods value)
6. Extract currency of the invoice document

FOR SHIPPING DOCUMENT (BOL/Air Waybill/etc.):
1. Extract ANY freight/shipping/transport cost mentioned in FOREIGN currency (search entire document for freight, shipping, transport, carriage charges - exclude any JMD/local currency amounts)
2. Extract ANY insurance cost mentioned in FOREIGN currency (search entire document for insurance, premium charges - exclude any JMD/local currency amounts)
3. Extract ANY other costs mentioned in FOREIGN currency (search entire document for handling, documentation, customs fees - exclude any JMD/local currency amounts)
4. Extract currency of the foreign currency amounts in shipping document

Return format:
{{
    "val_note_invoice_total_including_freight": <total_invoice_amount_or_null>,
    "val_note_invoice_value_goods_only": <goods_value_only_or_null>,
    "val_note_freight_charges_invoice": <freight_from_invoice_or_null>,
    "val_note_insurance_charges_invoice": <insurance_from_invoice_or_null>,
    "val_note_other_charges_invoice": <other_costs_from_invoice_or_null>,
    "val_note_freight_charges_bol": <freight_from_bol_foreign_currency_or_null>,
    "val_note_insurance_charges_bol": <insurance_from_bol_foreign_currency_or_null>,
    "val_note_other_charges_bol": <other_costs_from_bol_foreign_currency_or_null>,
    "invoice_currency": "<invoice_document_currency>",
    "bol_foreign_currency": "<bol_foreign_currency>",
    "incoterms": "<extracted_incoterms_terms>"
}}

IMPORTANT: 
- Only extract values that are explicitly stated in the documents
- For shipping documents, search the ENTIRE document for freight/shipping/transport costs (not just specific fields)
- ONLY extract foreign currency amounts (exclude JMD/local currency)
- Use null for missing values
- Do not calculate or estimate anything
- Look for freight costs anywhere in the document - tables, text blocks, charge summaries, etc.
"""

    # Try priority models with early termination
    for model in priority_models:
        model_name = model.split('/')[-1].split(':')[0]
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            cif_data = parse_llm_cif_response(raw_response)
            
            if cif_data:
                cif_data['_model_used'] = model_name
                cif_data['_debug_info'] = {
                    'model_tested': model_name,
                    'raw_response': raw_response,
                    'parsed_data': cif_data
                }
                return cif_data
            else:
                print(f"❌ Model {model_name} did not return valid CIF data.")
                
        except Exception as e:
            print(f"❌ Exception for model {model_name}: {e}")
    
    # If both models fail, return error
    print("🔄 Both models failed to process CIF data.")
    return {
        'success': False,
        'error': 'LLM processing failed',
        'val_note_invoice_total_including_freight': None,
        'val_note_invoice_value_goods_only': None,
        'val_note_freight_charges_invoice': None,
        'val_note_insurance_charges_invoice': None,
        'val_note_other_charges_invoice': None,
        'val_note_freight_charges_bol': None,
        'val_note_insurance_charges_bol': None,
        'val_note_other_charges_bol': None
    }

def parse_llm_cif_response(response) -> Optional[Dict[str, Any]]:
    """Parse LLM response to extract CIF components."""
    try:
        # Handle different response types (string, tuple, etc.)
        if isinstance(response, tuple):
            # If it's a tuple, take the first element (usually the content)
            response = response[0] if response else ""
        elif not isinstance(response, str):
            # Convert to string if it's not already
            response = str(response)
        
        # Clean the response
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith('```json'):
            response = response[7:]
        if response.endswith('```'):
            response = response[:-3]
        if response.startswith('```'):
            response = response[3:]
            
        # Parse JSON
        cif_data = json.loads(response)
        
        # Validate required fields (now focused on extraction)
        required_fields = ['val_note_invoice_total_including_freight', 'invoice_currency']
        for field in required_fields:
            if field not in cif_data:
                return None
                
        return cif_data
        
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        print(f"❌ Failed to parse LLM response: {e}")
        print(f"Raw response type: {type(response)}")
        print(f"Raw response: {response}")
        return None

def compute_insurance_if_none(extracted_data: Dict[str, Any], transport_mode: str = None) -> Dict[str, Any]:
    """Compute insurance charges if not found in extracted data."""
    # Check if insurance is already found in either invoice or BOL
    invoice_insurance = extracted_data.get('val_note_insurance_charges_invoice')
    bol_insurance = extracted_data.get('val_note_insurance_charges_bol')
    
    if invoice_insurance is not None or bol_insurance is not None:
        # Insurance already found, return as-is
        return extracted_data
    
    # Calculate insurance based on transport mode - include all charges
    goods_value = extracted_data.get('val_note_invoice_value_goods_only', 0) or 0
    freight_invoice = extracted_data.get('val_note_freight_charges_invoice', 0) or 0
    freight_bol = extracted_data.get('val_note_freight_charges_bol', 0) or 0
    other_charges_invoice = extracted_data.get('val_note_other_charges_invoice', 0) or 0
    other_charges_bol = extracted_data.get('val_note_other_charges_bol', 0) or 0
    
    # Use the higher freight amount or sum if both exist
    total_freight = max(freight_invoice, freight_bol) if freight_invoice and freight_bol else (freight_invoice or freight_bol)
    
    # Sum other charges from both invoice and BOL
    total_other_charges = (other_charges_invoice or 0) + (other_charges_bol or 0)
    
    if goods_value <= 0:
        extracted_data['val_note_insurance_charges_invoice'] = 0.0
        extracted_data['_insurance_debug'] = "⚠️ No goods value available - insurance set to $0.00"
        return extracted_data
    
    # Calculate insurance based on transport mode - use total CF value
    total_value = goods_value + total_freight + total_other_charges
    
    if transport_mode in ['SEA', 'OCEAN', 'MARITIME', 'VESSEL', 'SHIP']:
        insurance_rate = 0.015  # 1.5% for sea transport
        calculated_insurance = round(total_value * insurance_rate, 2)
        extracted_data['val_note_insurance_charges_invoice'] = calculated_insurance
        extracted_data['_insurance_debug'] = f"🚢 Insurance calculated (SEA transport): ${total_value:,.2f} × 1.5% = ${calculated_insurance:,.2f}"
    elif transport_mode in ['AIR', 'AIRFREIGHT', 'AIRWAY', 'FLIGHT']:
        insurance_rate = 0.01   # 1.0% for air transport
        calculated_insurance = round(total_value * insurance_rate, 2)
        extracted_data['val_note_insurance_charges_invoice'] = calculated_insurance
        extracted_data['_insurance_debug'] = f"✈️ Insurance calculated (AIR transport): ${total_value:,.2f} × 1.0% = ${calculated_insurance:,.2f}"
    else:
        # Default to 1.0% for other transport modes
        insurance_rate = 0.01   # 1.0% default
        calculated_insurance = round(total_value * insurance_rate, 2)
        extracted_data['val_note_insurance_charges_invoice'] = calculated_insurance
        extracted_data['_insurance_debug'] = f"🚛 Insurance calculated ({transport_mode or 'Unknown'} transport): ${total_value:,.2f} × 1.0% = ${calculated_insurance:,.2f}"
    
    return extracted_data

def compute_cost_and_freight(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Cost and Freight (CF) value including all charges."""
    goods_value = extracted_data.get('val_note_invoice_value_goods_only', 0) or 0
    freight_invoice = extracted_data.get('val_note_freight_charges_invoice', 0) or 0
    freight_bol = extracted_data.get('val_note_freight_charges_bol', 0) or 0
    other_charges_invoice = extracted_data.get('val_note_other_charges_invoice', 0) or 0
    other_charges_bol = extracted_data.get('val_note_other_charges_bol', 0) or 0
    
    # Use the higher freight amount or sum if both exist
    total_freight = max(freight_invoice, freight_bol) if freight_invoice and freight_bol else (freight_invoice or freight_bol)
    
    # Sum other charges from both invoice and BOL
    total_other_charges = (other_charges_invoice or 0) + (other_charges_bol or 0)
    
    cost_and_freight = goods_value + total_freight + total_other_charges
    extracted_data['val_note_cost_and_freight'] = round(cost_and_freight, 2)
    
    # Build detailed debug message
    debug_parts = [f"Goods: ${goods_value:,.2f}"]
    if total_freight > 0:
        debug_parts.append(f"Freight: ${total_freight:,.2f}")
    if total_other_charges > 0:
        debug_parts.append(f"Other: ${total_other_charges:,.2f}")
    
    extracted_data['_cf_debug'] = f"💰 Cost & Freight calculation: {' + '.join(debug_parts)} = ${cost_and_freight:,.2f}"
    
    return extracted_data

def compute_cif(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute CIF value (Cost + Insurance + Freight)."""
    goods_value = extracted_data.get('val_note_invoice_value_goods_only', 0) or 0
    freight_invoice = extracted_data.get('val_note_freight_charges_invoice', 0) or 0
    freight_bol = extracted_data.get('val_note_freight_charges_bol', 0) or 0
    insurance_invoice = extracted_data.get('val_note_insurance_charges_invoice', 0) or 0
    insurance_bol = extracted_data.get('val_note_insurance_charges_bol', 0) or 0
    other_charges_invoice = extracted_data.get('val_note_other_charges_invoice', 0) or 0
    other_charges_bol = extracted_data.get('val_note_other_charges_bol', 0) or 0
    
    # Use the higher freight amount or sum if both exist
    total_freight = max(freight_invoice, freight_bol) if freight_invoice and freight_bol else (freight_invoice or freight_bol)
    
    # Use the higher insurance amount or sum if both exist
    total_insurance = max(insurance_invoice, insurance_bol) if insurance_invoice and insurance_bol else (insurance_invoice or insurance_bol)
    
    # Sum other charges from both invoice and BOL
    total_other_charges = (other_charges_invoice or 0) + (other_charges_bol or 0)
    
    # CIF = Cost (goods) + Insurance + Freight + Other charges
    cif_value = goods_value + total_insurance + total_freight + total_other_charges
    extracted_data['val_note_cif'] = round(cif_value, 2)
    
    # Build detailed debug message
    debug_parts = [f"Goods: ${goods_value:,.2f}"]
    if total_insurance > 0:
        debug_parts.append(f"Insurance: ${total_insurance:,.2f}")
    if total_freight > 0:
        debug_parts.append(f"Freight: ${total_freight:,.2f}")
    if total_other_charges > 0:
        debug_parts.append(f"Other: ${total_other_charges:,.2f}")
    
    extracted_data['_cif_debug'] = f"🌍 CIF calculation: {' + '.join(debug_parts)} = ${cif_value:,.2f}"
    
    return extracted_data

class CIFProcessor:
    """CIF processor that uses LLM to analyze documents and extract CIF components."""
    
    def __init__(self, config: Dict = None):
        """Initialize the CIFProcessor."""
        self.config = config or {}
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to determine CIF components using LLM analysis.
        
        Args:
            input_data: Dictionary containing invoice_data, bol_data, fields, and existing_fields
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract invoice and BOL data
            invoice_data = input_data.get('invoice_data', {})
            bol_data = input_data.get('bol_data', {})
            
            if not invoice_data and not bol_data:
                return {
                    'success': False,
                    'error': 'No invoice or BOL data provided',
                    'val_note_invoice_total_including_freight': None,
                    'val_note_invoice_value_goods_only': None,
                    'val_note_freight_charges_invoice': None,
                    'val_note_insurance_charges_invoice': None,
                    'val_note_other_charges_invoice': None,
                    'val_note_freight_charges_bol': None,
                    'val_note_insurance_charges_bol': None,
                    'val_note_other_charges_bol': None
                }
            
            # Processing with LLM (debug info captured in result)
            
            # Use LLM to analyze and extract CIF components
            cif_result = ask_llm_for_cif_components(invoice_data, bol_data)
            
            if cif_result and not cif_result.get('error'):
                # Extract transport mode for insurance calculation
                transport_mode = self._extract_transport_mode(input_data)
                
                # Apply computation functions
                extracted_data = cif_result.copy()
                extracted_data = compute_insurance_if_none(extracted_data, transport_mode)
                extracted_data = compute_cost_and_freight(extracted_data)
                extracted_data = compute_cif(extracted_data)
                
                return {
                    'success': True,
                    'val_note_invoice_total_including_freight': extracted_data.get('val_note_invoice_total_including_freight'),
                    'val_note_invoice_value_goods_only': extracted_data.get('val_note_invoice_value_goods_only'),
                    'val_note_freight_charges_invoice': extracted_data.get('val_note_freight_charges_invoice'),
                    'val_note_insurance_charges_invoice': extracted_data.get('val_note_insurance_charges_invoice'),
                    'val_note_other_charges_invoice': extracted_data.get('val_note_other_charges_invoice'),
                    'val_note_freight_charges_bol': extracted_data.get('val_note_freight_charges_bol'),
                    'val_note_insurance_charges_bol': extracted_data.get('val_note_insurance_charges_bol'),
                    'val_note_other_charges_bol': extracted_data.get('val_note_other_charges_bol'),
                    'val_note_cost_and_freight': extracted_data.get('val_note_cost_and_freight'),
                    'val_note_cif': extracted_data.get('val_note_cif'),
                    'invoice_currency': extracted_data.get('invoice_currency'),
                    'bol_foreign_currency': extracted_data.get('bol_foreign_currency'),
                    'incoterms': extracted_data.get('incoterms'),
                    'model_used': extracted_data.get('_model_used', 'Unknown'),
                    'extracted_data': extracted_data
                }
            else:
                return {
                    'success': False,
                    'error': cif_result.get('error', 'LLM processing failed'),
                    'val_note_invoice_total_including_freight': None,
                    'val_note_invoice_value_goods_only': None,
                    'val_note_freight_charges_invoice': None,
                    'val_note_insurance_charges_invoice': None,
                    'val_note_other_charges_invoice': None,
                    'val_note_freight_charges_bol': None,
                    'val_note_insurance_charges_bol': None,
                    'val_note_other_charges_bol': None,
                    'val_note_cif': None
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'val_note_invoice_total_including_freight': None,
                'val_note_invoice_value_goods_only': None,
                'val_note_freight_charges_invoice': None,
                'val_note_insurance_charges_invoice': None,
                'val_note_other_charges_invoice': None,
                'val_note_freight_charges_bol': None,
                'val_note_insurance_charges_bol': None,
                'val_note_other_charges_bol': None,
                'val_note_cif': None
            }
    
    def _extract_transport_mode(self, input_data: Dict[str, Any]) -> str:
        """Extract transport mode from input data."""
        # Try to get from existing fields first
        existing_fields = input_data.get('existing_fields', {})
        bol_data = input_data.get('bol_data', {})
        
        # Look for transport mode in various field keys
        transport_keys = [
            'transport_mode',
            'mode_of_transport',
            '25_mode_of_transport',
            'transport_method',
            'shipping_method'
        ]
        
        for key in transport_keys:
            if key in existing_fields and existing_fields[key]:
                transport_mode = str(existing_fields[key]).strip()
                if transport_mode and transport_mode.lower() not in ['null', 'none', 'n/a', '']:
                    return self._parse_transport_mode(transport_mode)
        
        # Check BOL data for vessel/flight indicators
        vessel_voyage = bol_data.get('vessel_and_voyage', '')
        if vessel_voyage:
            return self._parse_transport_mode(vessel_voyage)
        
        return ""
    
    def _parse_transport_mode(self, transport_text: str) -> str:
        """Parse transport mode from text that might contain vessel names or other details."""
        if not transport_text:
            return ""
        
        text_upper = transport_text.upper()
        
        # Check for explicit transport mode keywords
        if any(keyword in text_upper for keyword in ['SEA', 'OCEAN', 'MARITIME', 'VESSEL', 'SHIP']):
            return 'SEA'
        elif any(keyword in text_upper for keyword in ['AIR', 'AIRFREIGHT', 'AIRWAY', 'FLIGHT', 'PLANE']):
            return 'AIR'
        elif any(keyword in text_upper for keyword in ['ROAD', 'TRUCK', 'VEHICLE', 'HIGHWAY']):
            return 'ROAD'
        elif any(keyword in text_upper for keyword in ['RAIL', 'TRAIN', 'RAILWAY']):
            return 'RAIL'
        
        # Check for vessel name patterns (e.g., "MSC Patnaree III, Voyage JX351R")
        vessel_indicators = ['MSC', 'MAERSK', 'COSCO', 'EVERGREEN', 'HAPAG', 'VOYAGE', 'VESSEL', 'SHIP']
        if any(indicator in text_upper for indicator in vessel_indicators):
            return 'SEA'
        
        # Check for flight number patterns (e.g., "AA123", "BA456")
        flight_pattern = r'[A-Z]{2,3}\d{3,4}'
        if re.search(flight_pattern, text_upper):
            return 'AIR'
        
        # If we can't determine, return the original text (might be a valid mode)
        return transport_text.strip()
    
def get_cif_data_from_json(json_path: str) -> Dict[str, Any]:
    """Extract invoice and BOL data from eSAD results JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract data from the JSON structure
        invoice_data = data.get('invoice_data', {})
        bol_data = data.get('bol_data', {})
        
        return {
            'invoice_data': invoice_data,
            'bol_data': bol_data
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error reading JSON file: {e}")
        return {'invoice_data': {}, 'bol_data': {}}

def main():
    """Main function to process CIF components from JSON data."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_cif <json_path>")
        print("Example: python -m modules.esad_cif path/to/esad_results.json")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        print(f"📋 Processing CIF components from: {json_path}")
        
        # Get data from JSON file
        data = get_cif_data_from_json(json_path)
        invoice_data = data['invoice_data']
        bol_data = data['bol_data']
        
        if not invoice_data and not bol_data:
            print("❌ No invoice or BOL data found in the JSON file.")
            sys.exit(1)
        
        # Initialize processor
        processor = CIFProcessor()
        
        # Process CIF components
        input_data = {
            'invoice_data': invoice_data,
            'bol_data': bol_data,
            'existing_fields': {}
        }
        
        result = processor.process(input_data)
        
        # Display results
        if result.get('success'):
            print(f"\n🏆 Extracted Valuation Data:")
            print("=" * 60)
            print(f"   Invoice Total (Including Freight): ${result.get('val_note_invoice_total_including_freight', 0):,.2f}" if result.get('val_note_invoice_total_including_freight') else "   Invoice Total (Including Freight): Not found")
            print(f"   Invoice Value (Goods Only): ${result.get('val_note_invoice_value_goods_only', 0):,.2f}" if result.get('val_note_invoice_value_goods_only') else "   Invoice Value (Goods Only): Not found")
            print(f"   Freight Charges (Invoice): ${result.get('val_note_freight_charges_invoice', 0):,.2f}" if result.get('val_note_freight_charges_invoice') else "   Freight Charges (Invoice): Not found")
            print(f"   Insurance Charges (Invoice): ${result.get('val_note_insurance_charges_invoice', 0):,.2f}" if result.get('val_note_insurance_charges_invoice') else "   Insurance Charges (Invoice): Not found")
            print(f"   Other Charges (Invoice): ${result.get('val_note_other_charges_invoice', 0):,.2f}" if result.get('val_note_other_charges_invoice') else "   Other Charges (Invoice): Not found")
            print(f"   Freight Charges (BOL - Foreign Currency): ${result.get('val_note_freight_charges_bol', 0):,.2f}" if result.get('val_note_freight_charges_bol') else "   Freight Charges (BOL - Foreign Currency): Not found")
            print(f"   Insurance Charges (BOL - Foreign Currency): ${result.get('val_note_insurance_charges_bol', 0):,.2f}" if result.get('val_note_insurance_charges_bol') else "   Insurance Charges (BOL - Foreign Currency): Not found")
            print(f"   Other Charges (BOL - Foreign Currency): ${result.get('val_note_other_charges_bol', 0):,.2f}" if result.get('val_note_other_charges_bol') else "   Other Charges (BOL - Foreign Currency): Not found")
            print(f"   Cost & Freight: ${result.get('val_note_cost_and_freight', 0):,.2f}" if result.get('val_note_cost_and_freight') else "   Cost & Freight: Not calculated")
            print(f"   Invoice Currency: {result.get('invoice_currency', 'Not found')}")
            print(f"   BOL Foreign Currency: {result.get('bol_foreign_currency', 'Not found')}")
            print(f"   Incoterms: {result.get('incoterms', 'Not found')}")
            
            print(f"\n✅ Successfully extracted valuation data")
        else:
            print(f"❌ CIF processing failed: {result.get('error')}")
            sys.exit(1)
            
    except FileNotFoundError:
        print(f"❌ Error: File '{json_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON in file '{json_path}'.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()