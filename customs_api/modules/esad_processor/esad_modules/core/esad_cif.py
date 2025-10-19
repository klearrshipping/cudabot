#!/usr/bin/env python3
"""
ESAD CIF Processing Script
Uses LLM to analyze invoice and BOL data to extract CIF components (Cost, Insurance, Freight)
"""

import json
import re
import sys
import os
from typing import Dict, Any, Optional

# Add path for config import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from modules.core.llm_client import LLMClient

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Priority models for CIF extraction
PRIORITY_MODELS = []
if "claude_haiku" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["claude_haiku"])

if "claude_sonnet" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["claude_sonnet"])

# Fallback to any available model
if not PRIORITY_MODELS and OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(list(OPENROUTER_GENERAL_MODELS.values())[0])


def ask_llm_for_cif_components(invoice_data: Dict, bol_data: Dict) -> Dict[str, Any]:
    """Get CIF components using LLM analysis."""
    
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
        "charges": bol_data.get("charges", []),  # Individual charges array
        "charges_totals": bol_data.get("charges_totals", {}),  # Add charges totals
        "freight_charge_amount": bol_data.get("freight_charge_amount", ""),
        "cargo_summary_table": bol_data.get("cargo_summary_table", {}),
        "document_type": bol_data.get("document_type", ""),
        "vessel_info": bol_data.get("vessel_info", {})
    }
    
    # Enhanced prompt for prepayment detection
    prompt = f"""
Extract CIF values from these documents, distinguishing between prepaid and collect amounts:

INVOICE:
{json.dumps(invoice_summary, indent=2)}

BILL OF LADING:
{json.dumps(bol_summary, indent=2)}

Return JSON with:
{{
    "val_note_invoice_total_including_freight": <total_or_null>,
    "val_note_invoice_value_goods_only": <goods_value_or_null>,
    "val_note_freight_charges_invoice": <freight_or_null>,
    "val_note_insurance_charges_invoice": <insurance_or_null>,
    "val_note_other_charges_invoice": <other_costs_or_null>,
    "val_note_freight_charges_bol_prepaid": <prepaid_freight_or_null>,
    "val_note_freight_charges_bol_collect": <collect_freight_or_null>,
    "val_note_insurance_charges_bol_prepaid": <prepaid_insurance_or_null>,
    "val_note_insurance_charges_bol_collect": <collect_insurance_or_null>,
    "val_note_other_charges_bol_prepaid": <prepaid_other_or_null>,
    "val_note_other_charges_bol_collect": <collect_other_or_null>,
    "invoice_currency": "<currency>",
    "bol_foreign_currency": "<currency_or_null>",
    "incoterms": "<terms_or_null>"
}}

IMPORTANT: 
- Use charges_totals section to identify prepaid vs collect amounts
- Prepaid amounts are already paid (usually with invoice)
- Collect amounts are still owed (to be paid later)
- Extract foreign currency amounts only (exclude JMD)
- Use null for missing values
"""

    # Try models with early termination
    for model in PRIORITY_MODELS:
        model_name = model.split('/')[-1].split(':')[0]
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            cif_data = parse_llm_response(raw_response)
            
            if cif_data:
                cif_data['_model_used'] = model_name
                return cif_data
            else:
                print(f"❌ Model {model_name} did not return valid CIF data.")
                
        except Exception as e:
            print(f"❌ Exception for model {model_name}: {e}")
    
    # Return error if all models fail
    print("🔄 All models failed to process CIF data.")
    return {
        'success': False,
        'error': 'LLM processing failed',
        'val_note_invoice_total_including_freight': None,
        'val_note_invoice_value_goods_only': None,
        'val_note_freight_charges_invoice': None,
        'val_note_insurance_charges_invoice': None,
        'val_note_other_charges_invoice': None,
        'val_note_freight_charges_bol_prepaid': None,
        'val_note_freight_charges_bol_collect': None,
        'val_note_insurance_charges_bol_prepaid': None,
        'val_note_insurance_charges_bol_collect': None,
        'val_note_other_charges_bol_prepaid': None,
        'val_note_other_charges_bol_collect': None,
        'invoice_currency': None,
        'bol_foreign_currency': None,
        'incoterms': None
    }


def calculate_insurance_if_missing(cif_summary: Dict[str, Any], bol_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate insurance if missing based on transport mode and freight rates."""
    
    # Insurance rates by transport mode
    sea_freight_rate = 0.015  # 1.5%
    air_freight_rate = 0.01   # 1%
    
    # Check if insurance is missing or zero
    insurance_charges = cif_summary.get('insurance_charges')
    if insurance_charges is not None and insurance_charges > 0:
        # Insurance already exists, return as-is
        return cif_summary
    
    # Insurance is missing, determine transport mode
    transport_result = determine_transport_mode(bol_data)
    
    if transport_result.get('success') == False:
        print(f"❌ Could not determine transport mode: {transport_result.get('error')}")
        return cif_summary
    
    transport_mode = transport_result.get('transport_mode', '').lower()
    cost_of_goods = cif_summary.get('cost_of_goods', 0) or 0
    freight_charges = cif_summary.get('freight_charges', 0) or 0
    cost_and_freight = cif_summary.get('cost_and_freight')
    
    # Calculate insurance based on transport mode
    if transport_mode == 'sea':
        insurance_rate = sea_freight_rate
        rate_description = "1.5%"
    elif transport_mode == 'air':
        insurance_rate = air_freight_rate
        rate_description = "1%"
    else:
        print(f"❌ Unknown transport mode: {transport_mode}")
        return cif_summary
    
    # Calculate insurance: (cost + freight) * rate
    if cost_and_freight is None:
        total_value = cost_of_goods + freight_charges
    else:
        total_value = float(cost_and_freight or 0)
    calculated_insurance = total_value * insurance_rate
    
    # Update the CIF summary with calculated insurance
    updated_summary = cif_summary.copy()
    updated_summary['insurance_charges'] = round(calculated_insurance, 2)
    updated_summary['cost_and_freight'] = round(total_value, 2)
    updated_summary['total_cif_value'] = round(total_value + calculated_insurance, 2)
    updated_summary['_insurance_calculated'] = True
    updated_summary['_insurance_rate'] = rate_description
    updated_summary['_transport_mode'] = transport_mode
    updated_summary['_insurance_evidence'] = transport_result.get('evidence', '')
    
    print(f"✅ Calculated insurance: ${calculated_insurance:.2f} ({rate_description} of ${total_value:.2f}) for {transport_mode} transport")
    
    return updated_summary


def determine_transport_mode(bol_data: Dict[str, Any]) -> Dict[str, Any]:
    """Determine the mode of transport from bill of lading using LLM."""
    
    # Prepare data for transport mode analysis
    transport_prompt = f"""
Analyze this bill of lading to determine the mode of transport:

BILL OF LADING DATA:
{json.dumps(bol_data, indent=2)}

Return JSON with:
{{
    "transport_mode": "<sea_or_air>",
    "confidence": "<high_or_medium_or_low>",
    "evidence": "<specific_text_or_field_that_indicates_transport_mode>"
}}

RULES:
- Look for vessel information, flight numbers, port names, airport codes
- "sea" for ocean/ship transport (vessels, ports, maritime terms)
- "air" for aircraft transport (flights, airports, aviation terms)
- Provide specific evidence from the document
- Use "high" confidence if clear indicators, "medium" if some indicators, "low" if unclear
"""
    
    # Try models for transport mode determination
    for model in PRIORITY_MODELS:
        model_name = model.split('/')[-1].split(':')[0]
        try:
            raw_response = llm.send_prompt(transport_prompt, model=model)
            transport_data = parse_llm_response(raw_response)
            
            if transport_data:
                transport_data['_model_used'] = model_name
                return transport_data
            else:
                print(f"❌ Model {model_name} did not return valid transport mode data.")
                
        except Exception as e:
            print(f"❌ Exception for transport mode model {model_name}: {e}")
    
    # Return error if all models fail
    print("🔄 All models failed to determine transport mode.")
    return {
        'success': False,
        'error': 'LLM transport mode determination failed',
        'transport_mode': None,
        'confidence': None,
        'evidence': None
    }


def aggregate_cif_summary(cif_data: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate CIF data into clean summary format using LLM."""
    
    # Prepare data for aggregation prompt
    aggregation_prompt = f"""
Analyze this CIF extraction data and provide a clean summary:

CIF EXTRACTION DATA:
{json.dumps(cif_data, indent=2)}

Provide a summary JSON with ONLY these fields:
{{
    "cost_of_goods": <goods_value_only>,
    "freight_charges": <total_freight_amount>,
    "insurance_charges": <insurance_amount_or_null>,
    "total_cif_value": <total_including_freight_and_insurance>,
    "currency": "<currency>",
    "cost_and_freight": <cost_of_goods_plus_freight>
}}

RULES:
- freight_charges should reflect TOTAL freight (prepaid + collect amounts)
- Total freight = prepaid freight + collect freight + collect other charges
- Cost of goods is the goods value only (excluding freight/insurance)
- Total CIF includes goods + total freight + insurance
- IMPORTANT: Invoice freight and BOL prepaid freight are the SAME payment - do NOT double count
- Prepaid amount = BOL prepaid freight only (not invoice + BOL prepaid)
- Use null ONLY for insurance_charges if no insurance found
- DO NOT include any other fields - only the 5 fields listed above
- DO NOT include null values for non-insurance fields
"""
    
    # Try models for aggregation
    for model in PRIORITY_MODELS:
        model_name = model.split('/')[-1].split(':')[0]
        try:
            raw_response = llm.send_prompt(aggregation_prompt, model=model)
            summary_data = parse_llm_response(raw_response)
            
            if summary_data:
                # Compute cost_and_freight if missing
                try:
                    cof_val = float(summary_data.get("cost_of_goods") or 0)
                    frt_val = float(summary_data.get("freight_charges") or 0)
                except Exception:
                    cof_val, frt_val = 0.0, 0.0
                cof_plus_frt = summary_data.get("cost_and_freight")
                if cof_plus_frt is None:
                    cof_plus_frt = round(cof_val + frt_val, 2)

                # Build in exact required order
                filtered_summary = {
                    "cost_of_goods": summary_data.get("cost_of_goods"),
                    "freight_charges": summary_data.get("freight_charges"),
                    "cost_and_freight": cof_plus_frt,
                    "insurance_charges": summary_data.get("insurance_charges"),
                    "total_cif_value": summary_data.get("total_cif_value"),
                    "currency": summary_data.get("currency"),
                }
                filtered_summary['_aggregation_model_used'] = model_name
                return filtered_summary
            else:
                print(f"❌ Model {model_name} did not return valid aggregation data.")
                
        except Exception as e:
            print(f"❌ Exception for aggregation model {model_name}: {e}")
    
    # Return error if all models fail
    print("🔄 All models failed to process CIF aggregation.")
    return {
        'success': False,
        'error': 'LLM aggregation failed',
        'cost_of_goods': None,
        'freight_charges': None,
        'insurance_charges': None,
        'total_cif_value': None,
        'currency': None
    }


def parse_llm_response(response) -> Optional[Dict[str, Any]]:
    """Parse LLM response to extract CIF components."""
    try:
        # Handle different response types
        if isinstance(response, tuple):
            response = response[0] if response else ""
        elif not isinstance(response, str):
            response = str(response)
        
        response = response.strip()
        
        # Extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Find JSON object anywhere in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
            
        # Parse JSON
        cif_data = json.loads(response)
        
        # Validate required fields
        required_fields = [
            'val_note_invoice_total_including_freight',
            'val_note_invoice_value_goods_only',
            'val_note_freight_charges_invoice',
            'val_note_insurance_charges_invoice',
            'val_note_other_charges_invoice',
            'val_note_freight_charges_bol',
            'val_note_insurance_charges_bol',
            'val_note_other_charges_bol',
            'invoice_currency',
            'bol_foreign_currency',
            'incoterms'
        ]
        
        # Ensure all required fields exist
        for field in required_fields:
            if field not in cif_data:
                cif_data[field] = None
                
        return cif_data
        
    except Exception as e:
        print(f"❌ Failed to parse LLM response: {e}")
        return None


def process_cif_fields(invoice_data: Dict[str, Any], bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Process CIF fields from invoice and BOL data."""
    
    if verbose:
        print("🧮 Processing CIF components...")
    
    try:
        # Use LLM to analyze and extract CIF components
        cif_result = ask_llm_for_cif_components(invoice_data, bol_data)
        
        if cif_result and not cif_result.get('error'):
            if verbose:
                print(f"✅ CIF extraction successful using model: {cif_result.get('_model_used', 'Unknown')}")
            
            # Generate clean CIF summary
            summary = aggregate_cif_summary(cif_result)
            
            if summary.get('success') == False:
                if verbose:
                    print(f"❌ CIF aggregation failed: {summary.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': summary.get('error', 'Aggregation failed'),
                    'cif_data': cif_result
                }
            
            # Ensure cost_and_freight is present before insurance calc
            if summary.get('cost_and_freight') is None:
                try:
                    cof = float(summary.get('cost_of_goods') or 0)
                    frt = float(summary.get('freight_charges') or 0)
                    summary['cost_and_freight'] = round(cof + frt, 2)
                except Exception:
                    summary['cost_and_freight'] = None

            # If insurance missing, compute it using transport mode BEFORE final prints
            if summary.get('insurance_charges') in (None, 0):
                summary = calculate_insurance_if_missing(summary, bol_data)

            # Build final summary with ONLY required fields in exact order
            final_summary = {
                "cost_of_goods": summary.get("cost_of_goods"),
                "freight_charges": summary.get("freight_charges"),
                "cost_and_freight": summary.get("cost_and_freight"),
                "insurance_charges": summary.get("insurance_charges"),
                "total_cif_value": summary.get("total_cif_value"),
                "currency": summary.get("currency") or "USD",
            }

            # Only insurance_charges may be null; coerce others to numbers
            try:
                final_summary["cost_of_goods"] = float(final_summary["cost_of_goods"] or 0)
                final_summary["freight_charges"] = float(final_summary["freight_charges"] or 0)
                final_summary["cost_and_freight"] = float(final_summary["cost_and_freight"] or 0)
                final_summary["total_cif_value"] = float(final_summary["total_cif_value"] or 0)
            except Exception:
                pass

            if verbose:
                # Print a single concise JSON summary from the module
                print(json.dumps(final_summary, indent=2, ensure_ascii=False))
            
            return final_summary
        else:
            if verbose:
                print("❌ CIF extraction failed")
            
            return {
                'success': False,
                'error': cif_result.get('error', 'Unknown error'),
                'cif_data': cif_result
            }
        
    except Exception as e:
        if verbose:
            print(f"❌ Exception during CIF processing: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'cif_data': None
        }


def main():
    """Main function for testing CIF extraction."""
    print("🧪 Testing CIF Extraction Module...")
    
    # Sample test data
    test_invoice_data = {
        "items": [
            {
                "description": "14.3 KW 51.2V 280Ah Rack mounted type lithium battery pack",
                "quantity": 2,
                "unit_price": 830.00,
                "total_price": 1660.00
            }
        ],
        "totals": {
            "subtotal": 1660.00,
            "total": 1660.00
        },
        "currency": "USD",
        "invoice_details": {
            "terms_of_sale": "FOB"
        }
    }
    
    test_bol_data = {
        "bill_of_lading": "PSHFHKIN25072146",
        "shipping_method": "Sea freight",
        "vessel_name": "EVER GIVEN",
        "voyage_number": "001W"
    }
    
    # Process CIF fields
    result = process_cif_fields(test_invoice_data, test_bol_data, verbose=True)
    
    # Display clean JSON result
    if result.get('success') != False:
        print(f"\n📋 Final Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()