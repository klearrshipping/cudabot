#!/usr/bin/env python3
"""
esad_country.py
────────────────
Converts country names from eSAD results to ISO2 codes using LLM classification.

Usage:
    python -m modules.esad_country <esad_json_path>

This script:
1. Extracts country fields from eSAD results (trading_country, country_last_consignment, country_origin_code)
2. Fetches country data from CSV
3. Uses LLM to match country names to ISO2 codes
4. Returns the best matching ISO2 codes
"""

import sys
import json
import csv
import difflib
from typing import Optional, Dict, List
from pathlib import Path
from modules.core.llm_client import LLMClient

# Cache for country data to avoid repeated file reads
_country_data_cache = None

def get_country_data() -> List[Dict]:
    """Get country data with caching to avoid repeated file reads."""
    global _country_data_cache
    if _country_data_cache is None:
        csv_path = Path(__file__).parent.parent.parent / "data" / "country.csv"
        countries = []
        
        # Try different encodings to handle potential encoding issues
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        countries.append({
                            'iso2': row['iso2'],
                            'iso3': row['iso3'],
                            'name_upper': row['name_upper'],
                            'name': row['name']
                        })
                print(f"✅ Successfully loaded country data using {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"❌ Error reading country data with {encoding}: {e}")
                continue
        
        if not countries:
            raise RuntimeError("Failed to load country data with any encoding")
        
        _country_data_cache = countries
    
    return _country_data_cache

def get_country_fields_from_json(json_path: str) -> Dict[str, str]:
    """Extract country-related fields from eSAD results JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    extracted_fields = data['result']['extracted_fields']
    
    return {
        'trading_country': extracted_fields.get('trading_country', ''),
        'country_last_consignment': extracted_fields.get('country_last_consignment', ''),
        'country_origin_code': extracted_fields.get('country_origin_code', '')
    }

def parse_llm_response(raw_response: str) -> Optional[str]:
    """Parse LLM response and extract ISO2 code."""
    if not raw_response:
        return None
    
    try:
        # Try to parse as JSON
        code_obj = json.loads(raw_response.strip())
        iso2 = code_obj.get('iso2', '').strip()
        return iso2 if iso2 else None
    except (json.JSONDecodeError, AttributeError):
        # If JSON parsing fails, try to extract ISO2 pattern
        import re
        iso2_match = re.search(r'"iso2"\s*:\s*"([A-Z]{2})"', raw_response)
        if iso2_match:
            return iso2_match.group(1).strip()
        return None

def string_similarity_fallback(country_name: str, countries: List[Dict]) -> Optional[str]:
    """Fallback method using string similarity matching."""
    if not country_name:
        return None
    
    country_name_clean = country_name.strip().lower()
    
    # Try matching against different name fields
    name_fields = ['name', 'name_upper']
    
    for field in name_fields:
        choices = [c[field].lower() for c in countries]
        best = difflib.get_close_matches(country_name_clean, choices, n=1, cutoff=0.6)
        if best:
            # Find the corresponding country
            for country in countries:
                if country[field].lower() == best[0]:
                    return country['iso2']
    
    return None

def ask_llm_for_country_iso2(country_name: str, countries: List[Dict]) -> Optional[str]:
    """Get the best ISO2 code using LLM with early termination."""
    if not country_name or country_name.lower() in ['not specified', 'none', '']:
        return None
    
    llm = LLMClient()
    
    # Create country list for prompt (limit to avoid token limits)
    country_list = [f"{c['iso2']}: {c['name']}" for c in countries[:100]]  # Top 100 countries
    
    prompt = f"""
You are a customs documentation expert. Given the country name from a customs document: '{country_name}', and the following list of valid countries with their ISO2 codes:

{country_list}

Return ONLY a valid JSON object with a single field 'iso2', e.g. {{"iso2": "PT"}}, where the value is the ISO2 code of the country that best matches the given country name. If no good match, return the closest ISO2 code. Do not return any explanation or extra text.
"""
    
    # Optimized model selection: Mistral primary, Kimi backup
    priority_models = [
        "mistralai/mistral-small-3.1-24b-instruct:free",  # Primary - 100% success rate, free
        "moonshotai/kimi-k2:free"                          # Backup - 100% success rate, free
    ]
    
    # Try priority models with early termination
    for model in priority_models:
        print(f"Testing model: {model.split('/')[-1].split(':')[0]}")
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            iso2 = parse_llm_response(raw_response)
            
            if iso2:
                print(f"✅ Model returned ISO2: {iso2}")
                return iso2
            else:
                print(f"❌ Model did not return a valid ISO2 code.")
                
        except Exception as e:
            print(f"❌ Exception for model: {e}")
    
    # If both models fail, try fallback
    print("🔄 Both models failed, using string similarity fallback.")
    return string_similarity_fallback(country_name, countries)

def process_country_fields(country_fields: Dict[str, str], countries: List[Dict]) -> Dict[str, str]:
    """Process all country fields and return ISO2 codes."""
    results = {}
    
    for field_name, country_name in country_fields.items():
        if country_name and country_name.lower() not in ['not specified', 'none', '']:
            print(f"\n🌍 Processing {field_name}: '{country_name}'")
            iso2 = ask_llm_for_country_iso2(country_name, countries)
            results[field_name] = iso2 if iso2 else None
        else:
            results[field_name] = None
    
    return results

def main():
    """Main function with improved error handling."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_country <esad_json_path>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        # Get country fields from eSAD results
        country_fields = get_country_fields_from_json(json_path)
        print(f"📋 Extracted country fields:")
        for field, value in country_fields.items():
            print(f"   {field}: {value}")
        
        # Get country data
        countries = get_country_data()
        print(f"📊 Loaded {len(countries)} countries from database")
        
        # Process country fields
        results = process_country_fields(country_fields, countries)
        
        # Display results
        print(f"\n🏆 Country Classification Results:")
        print("=" * 50)
        for field_name, iso2 in results.items():
            original_name = country_fields[field_name]
            status = "✅" if iso2 else "❌"
            print(f"   {field_name}: {original_name} → {iso2 if iso2 else 'FAILED'} {status}")
        
        # Summary
        successful = sum(1 for iso2 in results.values() if iso2)
        total = len(results)
        print(f"\n📊 Summary: {successful}/{total} countries successfully classified")
        
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