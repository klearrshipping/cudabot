#!/usr/bin/env python3
"""
eSAD Country Processing Module
Handles country name matching and ISO2 code extraction
"""

import json
import re
import os
import sys
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
customs_api_dir = os.path.join(current_dir, '..', '..', '..', '..')
sys.path.insert(0, customs_api_dir)

from modules.core.llm_client import LLMClient
from modules.core.csv_data_client import fetch_countries

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Priority models for country processing
PRIORITY_MODELS = []
if "gpt_4o" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o"])
elif "gpt_5_nano" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_5_nano"])

if "kimi_standard" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["kimi_standard"])
elif "kimi" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["kimi"])

# Fallback to any available model
if not PRIORITY_MODELS and OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(list(OPENROUTER_GENERAL_MODELS.values())[0])


def string_similarity_fallback(country_name: str, countries: List[Dict]) -> Optional[str]:
    """Fallback method using string similarity matching."""
    
    if not country_name:
        return None
    
    best_match = None
    best_score = 0.0
    
    for country in countries:
        # Check exact match first
        if country_name.lower() == country['name'].lower():
            return country['iso2']
        
        # Check similarity
        similarity = SequenceMatcher(None, country_name.lower(), country['name'].lower()).ratio()
        if similarity > best_score and similarity > 0.6:  # Minimum threshold
            best_score = similarity
            best_match = country['iso2']
    
    return best_match


def ask_llm_for_country_iso2(country_name: str, countries: List[Dict]) -> Optional[str]:
    """Get the best ISO2 code using LLM with early termination."""
    
    if not country_name or country_name.lower() in ['not specified', 'none', '']:
        return None
    
    # Create country list for prompt (limit to avoid token limits)
    country_list = [f"{c['iso2']}: {c['name']}" for c in countries[:100]]  # Top 100 countries
    
    prompt = f"""
You are a customs documentation expert. Given the country name from a customs document: '{country_name}', and the following list of valid countries with their ISO2 codes:

{country_list}

Return ONLY a valid JSON object with a single field 'iso2', e.g. {{"iso2": "PT"}}, where the value is the ISO2 code of the country that best matches the given country name. If no good match, return the closest ISO2 code. Do not return any explanation or extra text.
"""
    
    # Try priority models with early termination
    for model in PRIORITY_MODELS:
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            iso2 = parse_llm_response(raw_response)
            
            if iso2:
                return iso2
                
        except Exception as e:
            continue
    
    # If both models fail, try fallback
    return string_similarity_fallback(country_name, countries)


def parse_llm_response(response) -> Optional[str]:
    """Parse LLM response to extract ISO2 code."""
    try:
        # Handle different response types
        if isinstance(response, tuple):
            response = response[0] if response else ""
        elif not isinstance(response, str):
            response = str(response)
        
        response = response.strip()
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Find JSON object anywhere in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
        
        # Parse JSON
        result = json.loads(response)
        iso2 = result.get('iso2')
        
        # Validate ISO2 code (should be 2 letters)
        if iso2 and isinstance(iso2, str) and len(iso2) == 2:
            return iso2.upper()
        
        return None
        
    except Exception as e:
        print(f"❌ Failed to parse LLM response: {e}")
        return None


def process_country_fields(country_fields: Dict[str, str], countries: List[Dict]) -> Dict[str, str]:
    """Process multiple country fields and return ISO2 codes."""
    
    results = {}
    
    for field_name, country_name in country_fields.items():
        if country_name and country_name.lower() not in ['not specified', 'none', '']:
            iso2 = ask_llm_for_country_iso2(country_name, countries)
            results[field_name] = iso2 if iso2 else None
        else:
            results[field_name] = None
    
    return results


def process_country_iso2_codes(bol_data: Dict[str, Any], invoice_data: Dict[str, Any] = None, verbose: bool = False) -> Dict[str, Any]:
    """Process country fields and return ISO2 codes."""
    
    if verbose:
        print("🌍 Processing country ISO2 codes...")
    
    try:
        # Get countries data
        countries = fetch_countries()
        if not countries:
            return {
                'success': False,
                'error': 'Failed to load countries data',
                'iso2_codes': {}
            }
        
        # Extract country fields from BOL
        country_fields = {
            'country_of_origin': bol_data.get('origin_country', ''),
            'country_of_export': bol_data.get('export_country', ''),
            'country_of_last_departure': bol_data.get('last_departure_country', '')
        }
        
        # Extract from shipper/consignee addresses
        shipper_address = bol_data.get('shipper', {}).get('address', '')
        consignee_address = bol_data.get('consignee', {}).get('address', '')
        
        # Simple country extraction from addresses (basic implementation)
        if 'china' in shipper_address.lower():
            country_fields['country_of_export'] = 'China'
        if 'jamaica' in consignee_address.lower():
            country_fields['country_of_origin'] = 'Jamaica'
        
        # Process all country fields
        iso2_codes = process_country_fields(country_fields, countries)
        
        if verbose:
            print(f"📊 Country fields processed: {iso2_codes}")
        
        return {
            'success': True,
            'iso2_codes': iso2_codes,
            'processing_method': 'llm_extraction'
        }
        
    except Exception as e:
        if verbose:
            print(f"❌ Error processing country codes: {e}")
        
        return {
            'success': False,
            'error': str(e),
            'iso2_codes': {}
        }


def main():
    """Test function for the country module."""
    # Test data
    test_bol = {
        'origin_country': 'China',
        'export_country': 'China',
        'last_departure_country': 'Hong Kong',
        'shipper': {
            'address': 'Shenzhen, Guangdong, China'
        },
        'consignee': {
            'address': '4 Duke Street, Kingston, Jamaica'
        }
    }
    
    print("🧪 Testing Country Module...")
    result = process_country_iso2_codes(test_bol, verbose=True)
    print(f"📋 Result: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()