#!/usr/bin/env python3
"""
eSAD Ports Processing Module
Extracts port and country information from shipping documents
"""

import json
import re
import os
import sys
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from modules.core.llm_client import LLMClient
from modules.core.csv_data_client import fetch_locodes

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Priority models for port processing
PRIORITY_MODELS = []
if "claude_haiku" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["claude_haiku"])
elif "claude_sonnet" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["claude_sonnet"])
elif "gpt_4o_mini" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o_mini"])
elif "gpt_4o" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o"])

# Fallback to any available model
if not PRIORITY_MODELS and OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(list(OPENROUTER_GENERAL_MODELS.values())[0])


def extract_ports_from_bol(bol_data: Dict[str, Any], invoice_data: Dict[str, Any] = None, verbose: bool = False) -> Dict[str, Any]:
    """Extract port and country information from BOL data."""
    
    # Prepare document summary for LLM
    document_summary = {
        "document_type": bol_data.get("document_type", ""),
        "vessel_info": bol_data.get("vessel_info", {}),
        "shipper": bol_data.get("shipper", {}),
        "consignee": bol_data.get("consignee", {}),
        "notify_party": bol_data.get("notify_party", {})
    }
    
    # Add invoice data if available
    if invoice_data:
        document_summary["invoice_info"] = {
            "supplier": invoice_data.get("supplier", {}),
            "buyer": invoice_data.get("buyer", {})
        }
    
    prompt = f"""
Extract port and country information from this shipping document:

Document: {json.dumps(document_summary, indent=2)}

Return ONLY a JSON object with:
{{
    "origin_port": {{
        "port_name": "The complete port of loading/origin name (e.g., 'Hong Kong', not 'Ho')",
        "port_code": "The port code if found"
    }},
    "destination_port": {{
        "port_name": "The complete port of destination name (e.g., 'Kingston')",
        "port_code": "The port code if found"
    }},
    "country_of_export": "The country of export",
    "country_of_last_departure": "The country of last departure", 
    "country_of_origin": "The country of origin"
}}

IMPORTANT:
- Extract COMPLETE port names, not abbreviations
- Look for port codes in the document
- If any information is not found, use "Not specified" as the value
- Focus on vessel_info section for port details
"""
    
    for model in PRIORITY_MODELS:
        try:
            if verbose:
                print(f"🔍 Extracting port information using {model}...")
            
            response_text, success, error_type = llm.send_prompt(prompt, model=model)
            
            if not success:
                if verbose:
                    print(f"❌ LLM request failed with {model}: {error_type}")
                continue
            
            if verbose:
                print(f"🔍 Raw LLM response: {response_text[:200]}...")
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Try to match with port data
                ports = fetch_locodes()
                if ports:
                    if verbose:
                        print(f"🔍 Attempting to enhance with {len(ports)} LOCODE entries...")
                    matched_ports = _match_ports(result, ports)
                    if verbose and matched_ports:
                        print(f"🔍 Enhanced ports: {matched_ports}")
                    result.update(matched_ports)
                
                if verbose:
                    print(f"✅ Port extraction successful")
                
                result_obj = {
                    'success': True,
                    'port_data': result,
                    'model_used': model.split('/')[-1].split(':')[0]
                }
                try:
                    print(json.dumps(result_obj, indent=2, ensure_ascii=False))
                except Exception:
                    pass
                return result_obj
                
        except Exception as e:
            if verbose:
                print(f"❌ Port extraction failed with {model}: {e}")
            continue
    
    # Return error if all models fail
    error_obj = {
        'success': False,
        'error': 'All models failed to extract port information',
        'port_data': {
            'origin_port': {'port_name': 'Not specified', 'port_code': ''},
            'destination_port': {'port_name': 'Not specified', 'port_code': ''},
            'country_of_export': 'Not specified',
            'country_of_last_departure': 'Not specified',
            'country_of_origin': 'Not specified'
        }
    }
    try:
        print(json.dumps(error_obj, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return error_obj


def _match_ports(port_data: Dict[str, Any], ports: List[Dict]) -> Dict[str, Any]:
    """Try to match extracted port information with LOCODE database."""
    
    matched_info = {}
    
    # Try to match origin port - only enhance if LLM didn't provide complete info
    origin_port = port_data.get('origin_port', {})
    origin_name = origin_port.get('port_name', '').lower()
    origin_code = origin_port.get('port_code', '')
    
    print(f"🔍 Debug origin: name='{origin_name}', code='{origin_code}'")
    
    if origin_name and origin_name != 'not specified':
        # Only try to enhance if we don't have a port code
        if not origin_code or origin_code == 'not specified' or origin_code == 'Not specified':
            print(f"🔍 Looking for origin port matches for '{origin_name}'...")
            # First try exact match
            for port in ports:
                port_name = str(port.get('name', '')).lower()
                if port_name == origin_name:
                    print(f"🔍 Found exact match: '{port_name}' -> {port.get('locode')}")
                    matched_info['origin_port'] = {
                        'port_name': origin_port.get('port_name'),  # Keep LLM's name
                        'port_code': str(port.get('locode', '')),  # Use locode column
                        'country': str(port.get('iso2', '')),  # Use iso2 column
                        'match_method': 'exact_locode_match'
                    }
                    break
            
            # If no exact match, try partial match
            if 'origin_port' not in matched_info:
                for port in ports:
                    port_name = str(port.get('name', '')).lower()
                    if origin_name in port_name and len(origin_name) > 3:  # Avoid short partial matches
                        print(f"🔍 Found partial match: '{port_name}' -> {port.get('locode')}")
                        matched_info['origin_port'] = {
                            'port_name': origin_port.get('port_name'),  # Keep LLM's name
                            'port_code': str(port.get('locode', '')),  # Use locode column
                            'country': str(port.get('iso2', '')),  # Use iso2 column
                            'match_method': 'partial_locode_match'
                        }
                        break
    
    # Try to match destination port - only enhance if LLM didn't provide complete info
    dest_port = port_data.get('destination_port', {})
    dest_name = dest_port.get('port_name', '').lower()
    dest_code = dest_port.get('port_code', '')
    
    if dest_name and dest_name != 'not specified':
        # Only try to enhance if we don't have a port code
        if not dest_code or dest_code == 'not specified' or dest_code == 'Not specified':
            for port in ports:
                port_name = str(port.get('name', '')).lower()
                # Match by name similarity
                if dest_name in port_name or port_name in dest_name:
                    matched_info['destination_port'] = {
                        'port_name': dest_port.get('port_name'),  # Keep LLM's name
                        'port_code': str(port.get('locode', '')),  # Use locode column
                        'country': str(port.get('iso2', '')),  # Use iso2 column
                        'match_method': 'enhanced_from_locode'
                    }
                    break
    
    return matched_info


def main():
    """Test function for the ports module."""
    # Test data
    test_bol = {
        "document_type": "NOTICE OF ARRIVAL",
        "vessel_info": {
            "port_of_loading": "Hong Kong",
            "port_of_destination": "Kingston",
            "vessel_name": "COSCO HELLAS"
        },
        "shipper": {
            "name": "SHENZHEN ANYUN INTERNATIONAL LOGISTICS CO LTD",
            "address": "RM2404, BLK 3A, ZHIHUI JIAYUAN, NO. 76, BAOHE AVENUE"
        },
        "consignee": {
            "name": "RAFER JOHNSON",
            "address": "4 DUKE STREET,KINGSTON CSO,JAMAICA"
        }
    }
    
    test_invoice = {
        "supplier": {
            "name": "AVE Power CO., LTD",
            "address": "Shenzhen, Guangdong, China"
        },
        "buyer": {
            "name": "Ray Johnson",
            "address": "4 Duke Street, Kingston port of Jamaica"
        }
    }
    
    print("🧪 Testing Ports Module...")
    result = extract_ports_from_bol(test_bol, test_invoice, verbose=True)
    print(f"📋 Result: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()