#!/usr/bin/env python3
"""
eSAD Office Code Processing Module
Extracts office codes and manifest information from shipping documents
"""

import json
import re
import os
import sys
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from modules.core.llm_client import LLMClient
from modules.core.csv_data_client import fetch_warehouses

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Priority models for office code processing
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


def extract_office_code(bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Extract office code and manifest information from BOL data."""
    
    # Prepare document summary for LLM
    document_summary = {
        "document_type": bol_data.get("document_type", ""),
        "vessel_info": bol_data.get("vessel_info", {}),
        "issuing_agent": bol_data.get("issuing_agent", {}),
        "wharfinger": bol_data.get("vessel_info", {}).get("wharfinger", ""),
        "asycuda_number": bol_data.get("vessel_info", {}).get("asycuda_number", "")
    }
    
    prompt = f"""
Extract office code and manifest information from this shipping document:

Document: {json.dumps(document_summary, indent=2)}

Return ONLY a JSON object with:
{{
    "asycuda_number": "The ASYCUDA number if found",
    "wharfinger": "The wharfinger name if found",
    "office_of_submission": "The office of submission if found",
    "bol_number": "The BOL number if found"
}}

If any information is not found, use "Not specified" as the value.
"""
    
    for model in PRIORITY_MODELS:
        try:
            if verbose:
                print(f"🔍 Extracting office code information using {model}...")
            
            response_tuple = llm.send_prompt(prompt, model=model)
            
            # Check if the response was successful
            if not isinstance(response_tuple, tuple) or len(response_tuple) < 2:
                if verbose:
                    print(f"❌ Invalid response format from {model}")
                continue
                
            response, success, error_type = response_tuple
            
            if not success:
                if verbose:
                    print(f"❌ LLM request failed with {model}: {error_type}")
                continue
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Try to match with warehouse data
                warehouses = fetch_warehouses()
                if warehouses:
                    matched_office = _match_office_code(result, warehouses)
                    if matched_office:
                        result['matched_office'] = matched_office
                
                if verbose:
                    print(f"✅ Office code extraction successful")
                
                # Extract model name safely
                model_name = str(model)
                if '/' in model_name:
                    model_name = model_name.split('/')[-1]
                if ':' in model_name:
                    model_name = model_name.split(':')[0]
                
                result_obj = {
                    'success': True,
                    'office_data': result,
                    'model_used': model_name
                }
                try:
                    print(json.dumps(result_obj, indent=2, ensure_ascii=False))
                except Exception:
                    pass
                return result_obj
                
        except Exception as e:
            if verbose:
                print(f"❌ Office code extraction failed with {model}: {e}")
            continue
    
    # Return error if all models fail
    error_obj = {
        'success': False,
        'error': 'All models failed to extract office code information',
        'office_data': {
            'asycuda_number': 'Not specified',
            'wharfinger': 'Not specified',
            'office_of_submission': 'Not specified',
            'bol_number': 'Not specified'
        }
    }
    try:
        print(json.dumps(error_obj, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return error_obj


def _match_office_code(office_data: Dict[str, Any], warehouses: List[Dict]) -> Optional[Dict[str, Any]]:
    """Try to match extracted office information with warehouse data."""
    
    # Safely convert to strings
    wharfinger = str(office_data.get('wharfinger', '')).lower()
    asycuda_number = str(office_data.get('asycuda_number', '')).upper()
    
    # Try to match by wharfinger name
    for warehouse in warehouses:
        warehouse_name = str(warehouse.get('name', '')).lower()
        if wharfinger and warehouse_name and wharfinger in warehouse_name:
            return {
                'warehouse_id': warehouse.get('id'),
                'warehouse_name': warehouse.get('name'),
                'office_code': warehouse.get('office_code'),
                'match_method': 'wharfinger_name'
            }
    
    # Try to match by ASYCUDA number pattern
    if asycuda_number and len(asycuda_number) >= 4:
        for warehouse in warehouses:
            office_code = str(warehouse.get('office_code', ''))
            if office_code and office_code in asycuda_number:
                return {
                    'warehouse_id': warehouse.get('id'),
                    'warehouse_name': warehouse.get('name'),
                    'office_code': office_code,
                    'match_method': 'asycuda_pattern'
                }
    
    return None


def main():
    """Test function for the office code module."""
    # Test data
    test_bol = {
        "document_type": "NOTICE OF ARRIVAL",
        "vessel_info": {
            "vessel_name": "COSCO HELLAS",
            "asycuda_number": "JMOSC-2025-574",
            "wharfinger": "ONE STOP/ Universal Freight Handlers",
            "office_of_submission": "JMOSC"
        },
        "issuing_agent": {
            "name": "Freight Handlers Limited"
        }
    }
    
    print("🧪 Testing Office Code Module...")
    result = extract_office_code(test_bol, verbose=True)
    print(f"📋 Result: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()