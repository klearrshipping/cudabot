#!/usr/bin/env python3
"""
esad_marks.py
────────────────
Creates field 31 "Marks and numbers of packages" by concatenating 
"AS ADDRESSED" with the commercial description.

Usage:
    python -m modules.esad_marks <esad_json_path>

This script:
1. Extracts commercial_description from eSAD results
2. Concatenates "AS ADDRESSED" + commercial_description for field 31
3. Returns the formatted marks and numbers field
4. Handles various input formats and edge cases
"""

import sys
import json
import re
from typing import Optional, Dict, List
from modules.core.llm_client import LLMClient

def get_commercial_description_from_json(json_path: str) -> str:
    """Extract commercial_description from eSAD results JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        extracted_fields = data['result']['extracted_fields']
        return extracted_fields.get('commercial_description', '')
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error reading JSON file: {e}")
        return ""

def clean_commercial_description(description: str) -> str:
    """Clean and preprocess commercial description for field 31."""
    if not description:
        return ""
    
    # Remove common shipping terms and container info that shouldn't be in field 31
    shipping_terms = [
        r'\d+\s*(?:FT|FOOT)\s*(?:STD|STANDARD)\s*CONTAINER',
        r'SAID\s+TO\s+CONTAIN',
        r'SHIPPERS\s+LOAD\s+STOW\s*&?\s*COU',
        r'SHIPPERS\s+LOAD\s+AND\s+COUNT',
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

def create_field_31_marks(commercial_description: str) -> str:
    """Create field 31 marks by concatenating 'AS ADDRESSED' with commercial description."""
    if not commercial_description or commercial_description.lower() in ['not specified', 'none', '']:
        return "AS ADDRESSED: NO DESCRIPTION AVAILABLE"
    
    # Clean the commercial description
    cleaned_description = clean_commercial_description(commercial_description)
    
    if not cleaned_description:
        return "AS ADDRESSED: NO DESCRIPTION AVAILABLE"
    
    # Create the field 31 format
    field_31_marks = f"AS ADDRESSED: {cleaned_description}"
    
    return field_31_marks

def process_commercial_description(commercial_description: str) -> Dict[str, str]:
    """Process commercial description to create field 31 marks."""
    results = {
        'original_description': commercial_description,
        'cleaned_description': clean_commercial_description(commercial_description),
        'field_31_marks': create_field_31_marks(commercial_description)
    }
    
    return results

def main():
    """Main function to process commercial description and create field 31 marks."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_marks <esad_json_path>")
        print("Example: python -m modules.esad_marks path/to/esad_results.json")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        print(f"📋 Processing eSAD results from: {json_path}")
        
        # Get commercial description from eSAD results
        commercial_description = get_commercial_description_from_json(json_path)
        
        if not commercial_description:
            print("❌ No commercial description found in the JSON file.")
            sys.exit(1)
        
        print(f"📦 Found commercial description: '{commercial_description}'")
        
        # Process the commercial description
        results = process_commercial_description(commercial_description)
        
        # Display results
        print(f"\n🏆 Field 31 Marks Results:")
        print("=" * 60)
        print(f"   Original Description: {results['original_description']}")
        print(f"   Cleaned Description: {results['cleaned_description']}")
        print(f"   Field 31 Marks: {results['field_31_marks']}")
        
        # Summary
        print(f"\n✅ Successfully created field 31 marks:")
        print(f"   {results['field_31_marks']}")
        
        # Return the result for potential use in other scripts
        return results['field_31_marks']
        
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