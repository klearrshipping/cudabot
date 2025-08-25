#!/usr/bin/env python3
"""
esad_marks.py
────────────────
Creates structured address descriptions from commercial description and marks/numbers.

Usage:
    python -m modules.esad_marks <esad_json_path>

This script:
1. Extracts commercial_description and marks_and_numbers_of_packages from eSAD results
2. Uses LLM to create structured address format: "AS ADDRESSED: [Product Name/Category] - [Container Number]"
3. Returns a clean, standardized address description
4. Handles various input formats and edge cases
"""

import sys
import json
import re
from typing import Optional, Dict, List
from modules.core.llm_client import LLMClient

def get_marks_data_from_json(json_path: str) -> Dict[str, str]:
    """Extract commercial_description and marks_and_numbers_of_packages from eSAD results JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    extracted_fields = data['result']['extracted_fields']
    
    return {
        'commercial_description': extracted_fields.get('commercial_description', ''),
        'marks_and_numbers_of_packages': extracted_fields.get('marks_and_numbers_of_packages', '')
    }

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

def extract_container_number(marks: str) -> Optional[str]:
    """Extract container number from marks and numbers."""
    if not marks:
        return None
    
    # Common container number patterns
    container_patterns = [
        r'[A-Z]{4}\d{6,7}',  # Standard container format (e.g., CMAU1234567)
        r'[A-Z]{3}[UZ]\d{6,7}',  # Alternative format
        r'[A-Z]{4}\d{3}[A-Z]\d{3}',  # Another common format
        r'[A-Z]{4}\d{7}',  # 7-digit format
        r'[A-Z]{4}\d{6}',  # 6-digit format
    ]
    
    for pattern in container_patterns:
        match = re.search(pattern, marks.upper())
        if match:
            return match.group(0)
    
    return None

def parse_llm_response(raw_response: str) -> Optional[str]:
    """Parse LLM response and extract structured address."""
    if not raw_response:
        return None
    
    try:
        # Try to parse as JSON
        code_obj = json.loads(raw_response.strip())
        address = code_obj.get('structured_address', '').strip()
        return address if address else None
    except (json.JSONDecodeError, AttributeError):
        # If JSON parsing fails, try to extract address pattern
        import re
        address_match = re.search(r'"structured_address"\s*:\s*"([^"]+)"', raw_response)
        if address_match:
            return address_match.group(1).strip()
        return None

def ask_llm_for_structured_address(commercial_description: str, marks: str) -> Optional[str]:
    """Get the structured address using LLM."""
    if not commercial_description or commercial_description.lower() in ['not specified', 'none', '']:
        return None
    
    llm = LLMClient()
    
    # Clean the commercial description
    cleaned_description = clean_commercial_description(commercial_description)
    
    # Extract container number
    container_number = extract_container_number(marks)
    
    prompt = f"""
You are a customs documentation expert. Given the following information from a customs document:

Commercial Description: '{commercial_description}'
Cleaned Description: '{cleaned_description}'
Marks and Numbers: '{marks}'
Container Number: '{container_number if container_number else "Not found"}'

Your task is to create a structured address description in the format:
"AS ADDRESSED: [Product Name/Category] - [Container Number]"

Rules:
1. Extract the main product name/category from the commercial description
2. Use the container number if available, otherwise use a relevant identifier from marks
3. Keep it concise and professional
4. Use proper capitalization
5. If no container number is found, use "NO CONTAINER" or a relevant alternative

Return ONLY a valid JSON object with a single field 'structured_address', e.g. {{"structured_address": "AS ADDRESSED: Footwear - CMAU1234567"}}, where the value is the structured address. Do not return any explanation or extra text.
"""
    
    # Use Kimi as primary, Mistral as backup
    models = [
        "moonshotai/kimi-k2:free",                         # Primary - Kimi
        "mistralai/mistral-small-3.1-24b-instruct:free"   # Backup - Mistral
    ]
    
    results = {}
    
    # Test models with early termination
    for model in models:
        model_name = model.split('/')[-1].split(':')[0]
        print(f"\n🧪 Testing model: {model_name}")
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            structured_address = parse_llm_response(raw_response)
            
            if structured_address:
                print(f"✅ {model_name} returned: {structured_address}")
                results[model_name] = structured_address
                # Early termination after first success
                break
            else:
                print(f"❌ {model_name} did not return a valid structured address.")
                results[model_name] = None
                
        except Exception as e:
            print(f"❌ {model_name} exception: {e}")
            results[model_name] = None
    
    # Show results from tested models
    print(f"\n📊 Model Results:")
    print("=" * 50)
    for model_name, address in results.items():
        status = "✅ SUCCESS" if address else "❌ FAILED"
        print(f"   {model_name}: {address if address else 'No response'} ({status})")
    
    # Return the first successful result, or None if all failed
    for model_name, address in results.items():
        if address:
            return address
    
    print("🔄 All models failed to create structured address.")
    return None

def process_marks_data(commercial_description: str, marks: str) -> Dict[str, str]:
    """Process commercial description and marks to create structured address."""
    results = {
        'commercial_description': commercial_description,
        'marks_and_numbers': marks,
        'cleaned_description': clean_commercial_description(commercial_description),
        'container_number': extract_container_number(marks),
        'structured_address': None
    }
    
    if commercial_description and commercial_description.lower() not in ['not specified', 'none', '']:
        print(f"\n📦 Processing marks data:")
        print(f"   Commercial Description: '{commercial_description}'")
        print(f"   Marks and Numbers: '{marks}'")
        print(f"   Cleaned Description: '{results['cleaned_description']}'")
        print(f"   Container Number: '{results['container_number'] if results['container_number'] else 'Not found'}'")
        
        # Get structured address from LLM
        structured_address = ask_llm_for_structured_address(commercial_description, marks)
        results['structured_address'] = structured_address
        
    return results

def main():
    """Main function with improved error handling."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_marks <esad_json_path>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        # Get marks data from eSAD results
        marks_data = get_marks_data_from_json(json_path)
        print(f"📋 Extracted marks data:")
        print(f"   Commercial Description: {marks_data['commercial_description']}")
        print(f"   Marks and Numbers: {marks_data['marks_and_numbers_of_packages']}")
        
        # Process marks data
        results = process_marks_data(
            marks_data['commercial_description'], 
            marks_data['marks_and_numbers_of_packages']
        )
        
        # Display results
        print(f"\n🏆 Structured Address Results:")
        print("=" * 60)
        print(f"   Commercial Description: {results['commercial_description']}")
        print(f"   Marks and Numbers: {results['marks_and_numbers']}")
        print(f"   Cleaned Description: {results['cleaned_description']}")
        print(f"   Container Number: {results['container_number'] if results['container_number'] else 'Not found'}")
        print(f"   Structured Address: {results['structured_address'] if results['structured_address'] else 'FAILED'}")
        
        # Summary
        if results['structured_address']:
            print(f"\n✅ Successfully created structured address: {results['structured_address']}")
        else:
            print(f"\n❌ Failed to create structured address")
        
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