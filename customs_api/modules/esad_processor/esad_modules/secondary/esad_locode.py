#!/usr/bin/env python3
"""
ESAD Locode Processor
Extracts Jamaican port locations from BOL/Arrival Notice and matches them to locode_JM.csv
"""

import json
import os
import re
import csv
import requests
import pandas as pd
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import OpenRouter configuration
try:
    from config import OPENROUTER_API_KEY, OPENROUTER_URL, OPENROUTER_HEADERS
except ImportError:
    # Fallback configuration if config import fails
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_URL = os.getenv('OPENROUTER_URL', 'https://openrouter.ai/api/v1/chat/completions')
    OPENROUTER_HEADERS = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost:3000',
        'X-Title': 'eSAD LOCODE Extractor'
    }

class LocodeProcessor:
    """
    Extracts Jamaican port locations from BOL/Arrival Notice and matches them to locode_JM.csv
    """
    
    def __init__(self):
        """Initialize the locode processor"""
        self.locode_data = None
        self._load_reference_data()
    
    def _load_reference_data(self):
        """Load Jamaican locode data from CSV file"""
        try:
            csv_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "locode_JM.csv"
            self.locode_data = pd.read_csv(csv_path)
            
        except Exception as e:
            print(f"⚠️ Warning: Could not load locode data: {e}")
            self.locode_data = pd.DataFrame()
    
    def extract_jamaican_port(self, bol_data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
        """Extract Jamaican port location from BOL/Arrival Notice using LLM
        
        Args:
            bol_data: Bill of Lading or Arrival Notice data
            verbose: If True, print extraction results to console (default: False)
        
        Returns:
            Dictionary containing extracted port name and matched LOCODE information
        """
        
        # Safely serialize BOL data
        def safe_json_dumps(obj, max_depth=3, current_depth=0):
            if current_depth >= max_depth:
                return "[Max depth reached]"
            
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    try:
                        result[key] = safe_json_dumps(value, max_depth, current_depth + 1)
                    except:
                        result[key] = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                return result
            elif isinstance(obj, list):
                result = []
                for item in obj:
                    try:
                        result.append(safe_json_dumps(item, max_depth, current_depth + 1))
                    except:
                        result.append(str(item)[:100] + "..." if len(str(item)) > 100 else str(item))
                return result
            else:
                return obj
        
        safe_bol_data = safe_json_dumps(bol_data)
        
        prompt = f"""
You are analyzing a Bill of Lading (BOL) or Arrival Notice for goods being shipped to/from Jamaica.

Extract and identify the JAMAICAN PORT location mentioned in the document.

Look for the Jamaican port in these fields:
- Port of Discharge (POD) - if shipping TO Jamaica
- Port of Destination - if shipping TO Jamaica
- Port of Loading - if shipping FROM Jamaica
- Place of Delivery
- Destination Port
- Jamaica port names

Common Jamaican ports include:
- Kingston (most common)
- Montego Bay
- Norman Manley International Airport
- Sangster International Airport
- Ocho Rios
- Falmouth
- Port Antonio
- Black River
- Port Esquivel
- Port Kaiser
- Rocky Point

BOL/ARRIVAL NOTICE DATA:
{json.dumps(safe_bol_data, indent=2)}

Return your response in the following JSON format:
{{
  "jamaican_port": "port name"
}}

Return ONLY the Jamaican port name (e.g., "Kingston", "Montego Bay", "Norman Manley International").
If no Jamaican port is found, use "Not specified" as the value.
"""
        
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 200
        }
        
        try:
            if verbose:
                print("\n🔍 Extracting Jamaican port from BOL/Arrival Notice...")
            
            response = requests.post(OPENROUTER_URL, headers=OPENROUTER_HEADERS, json=payload, timeout=30)
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            result = json.loads(json_match.group())
            
            jamaican_port = result.get('jamaican_port', 'Not specified')
            
            # Match against locode_JM.csv
            locode_match = self._find_matching_locode(jamaican_port)
            
            if verbose and jamaican_port != 'Not specified':
                print(f"\n🚢 JAMAICAN PORT EXTRACTION:")
                print("=" * 60)
                print(f"Extracted Port: {jamaican_port}")
                if locode_match:
                    print(f"Matched LOCODE: {locode_match['locode']}")
                    print(f"Location Name: {locode_match['name']}")
                    print(f"Subdivision: {locode_match.get('subdivision', 'N/A')}")
                else:
                    print(f"⚠️  No LOCODE match found for '{jamaican_port}'")
                print("=" * 60)
            
            return {
                'success': True if jamaican_port != 'Not specified' else False,
                'jamaican_port': jamaican_port,
                'locode': locode_match['locode'] if locode_match else None,
                'location_name': locode_match['name'] if locode_match else None,
                'subdivision': locode_match.get('subdivision') if locode_match else None,
                'extraction_metadata': {
                    'status': 'success',
                    'message': 'Jamaican port extracted and matched',
                    'locode_matched': locode_match is not None
                }
            }
            
        except Exception as e:
            if verbose:
                print(f"\n❌ Port extraction failed: {e}")
            
            return {
                'success': False,
                'jamaican_port': 'Not specified',
                'locode': None,
                'location_name': None,
                'subdivision': None,
                'extraction_metadata': {
                    'status': 'error',
                    'message': f"Port extraction failed: {str(e)}",
                    'locode_matched': False
                }
            }
    
    def _find_matching_locode(self, port_name: str) -> Optional[Dict[str, Any]]:
        """Find matching LOCODE for a Jamaican port name
        
        Args:
            port_name: Port name to search for
            
        Returns:
            Dict with LOCODE information or None if not found
        """
        if self.locode_data.empty or not port_name or port_name == 'Not specified':
            return None
        
        try:
            port_name_clean = port_name.strip().lower()
            
            # Try exact match first
            exact_match = self.locode_data[
                self.locode_data['name'].str.lower() == port_name_clean
            ]
            
            if not exact_match.empty:
                match = exact_match.iloc[0]
                return {
                    'locode': match['locode'],
                    'name': match['name'],
                    'subdivision': match['subdiv'] if pd.notna(match['subdiv']) else None
                }
            
            # Try partial match
            partial_match = self.locode_data[
                self.locode_data['name'].str.contains(port_name_clean, case=False, na=False, regex=False)
            ]
            
            if not partial_match.empty:
                match = partial_match.iloc[0]
                return {
                    'locode': match['locode'],
                    'name': match['name'],
                    'subdivision': match['subdiv'] if pd.notna(match['subdiv']) else None
                }
            
            # Try cleaning port name (remove "port", "airport", etc.)
            port_name_cleaned = re.sub(r'\b(port|airport|international|pier|terminal|harbor|harbour)\b', '', port_name_clean, flags=re.IGNORECASE)
            port_name_cleaned = re.sub(r'\s+', ' ', port_name_cleaned).strip()
            
            if port_name_cleaned:
                cleaned_match = self.locode_data[
                    self.locode_data['name'].str.contains(port_name_cleaned, case=False, na=False, regex=False)
                ]
                
                if not cleaned_match.empty:
                    match = cleaned_match.iloc[0]
                    return {
                        'locode': match['locode'],
                        'name': match['name'],
                        'subdivision': match['subdiv'] if pd.notna(match['subdiv']) else None
                    }
            
            return None
            
        except Exception as e:
            print(f"Error in LOCODE lookup: {e}")
            return None
    
    def process_loading_location(self, location_text: str) -> Dict[str, Any]:
        """
        Process place of loading/unloading location (ports, cities, airports)
        Uses locode_JM.csv for Jamaican locations
        
        Args:
            location_text: Location text from esad_fields (e.g., "Kingston, Jamaica")
            
        Returns:
            Dict with processed location information
        """
        if not location_text or not isinstance(location_text, str):
            return {
                "processed": False,
                "error": "Invalid location text",
                "standardized_name": None,
                "locode": None,
                "city_name": None,
                "country_code": None,
                "country_name": None,
                "subdivision": None
            }
        
        try:
            # Clean and parse location text
            location_text = location_text.strip()
            
            # Extract city and country
            parts = [part.strip() for part in location_text.split(',')]
            city = parts[0] if parts else ""
            country = parts[1] if len(parts) > 1 else ""
            
            # Look up in locode data
            locode_info = self._lookup_locode(city, country)
            
            if locode_info:
                return {
                    "processed": True,
                    "error": None,
                    "standardized_name": f"{locode_info['city_name']}, {locode_info['country_name']}",
                    "locode": locode_info['locode'],
                    "city_name": locode_info['city_name'],
                    "country_code": locode_info['country_code'],
                    "country_name": locode_info['country_name'],
                    "subdivision": locode_info['subdivision']
                }
            else:
                # Fallback: return parsed but unprocessed data
                return {
                    "processed": False,
                    "error": "Location not found in locode database",
                    "standardized_name": location_text,
                    "locode": None,
                    "city_name": city,
                    "country_code": self._get_country_code(country),
                    "country_name": country,
                    "subdivision": None
                }
                
        except Exception as e:
            return {
                "processed": False,
                "error": f"Processing error: {str(e)}",
                "standardized_name": location_text,
                "locode": None,
                "city_name": None,
                "country_code": None,
                "country_name": None,
                "subdivision": None
            }
    
    def _lookup_locode(self, city: str, country: str) -> Optional[Dict[str, Any]]:
        """
        Look up location in locode database
        
        Args:
            city: City name
            country: Country name
            
        Returns:
            Dict with locode information or None if not found
        """
        if self.locode_data.empty:
            return None
        
        try:
            # Search by exact city name match (case-insensitive)
            city_mask = self.locode_data['name'].str.match(f"^{city}$", case=False, na=False)
            
            if city_mask.any():
                # Found exact matching city
                match = self.locode_data[city_mask].iloc[0]
                
                return {
                    'locode': match['locode'],
                    'city_name': match['name'],
                    'country_code': match['iso2'].upper(),
                    'country_name': 'Jamaica',
                    'subdivision': match['subdiv'] if pd.notna(match['subdiv']) else None
                }
            
            return None
            
        except Exception as e:
            print(f"Error in locode lookup: {e}")
            return None
    
    def _get_country_code(self, country_name: str) -> Optional[str]:
        """
        Get country code from country name
        
        Args:
            country_name: Country name
            
        Returns:
            Country code or None
        """
        country_mapping = {
            'jamaica': 'JM',
            'jamaica,': 'JM',
            'united states': 'US',
            'usa': 'US',
            'united states of america': 'US',
            'canada': 'CA',
            'united kingdom': 'GB',
            'uk': 'GB',
            'great britain': 'GB'
        }
        
        return country_mapping.get(country_name.lower().strip(), None)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to extract Jamaican port and match to LOCODE.
        
        Args:
            input_data: Dictionary containing bol_data
            
        Returns:
            Dictionary with processing results including LOCODE and location information
        """
        try:
            bol_data = input_data.get('bol_data', {})
            
            if not bol_data:
                return {
                    'success': False,
                    'error': 'No BOL data found',
                    'locode': None,
                    'jamaican_port': None,
                    'location_name': None
                }
            
            # Extract Jamaican port and match to LOCODE
            result = self.extract_jamaican_port(bol_data, verbose=False)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'locode': None,
                'jamaican_port': None,
                'location_name': None
            }


def main():
    """Test the locode processor with real BOL data"""
    import json
    
    processor = LocodeProcessor()
    
    print("🧪 Testing LOCODE Processor")
    print("=" * 80)
    
    # Load test BOL data
    try:
        bol_path = "../../processed_orders/ORD-20251009-002/bills_of_lading/bill_of_lading_ORD-20251009-002_primary_extract.json"
        with open(bol_path, 'r', encoding='utf-8') as f:
            bol_data = json.load(f)
        
        print(f"\n📁 Loaded test BOL: {bol_data.get('bill_of_lading', 'N/A')}")
        print(f"Document Type: {bol_data.get('document_type', 'N/A')}")
        
        # Extract Jamaican port and match to LOCODE
        result = processor.extract_jamaican_port(bol_data, verbose=True)
        
        print("\n📊 Final Result:")
        print(json.dumps(result, indent=2))
        
    except FileNotFoundError:
        print("\n❌ Test BOL file not found, testing with sample data...")
        
        sample_bol = {
            "port_of_destination": "Kingston",
            "port_of_discharge": "Kingston Port"
        }
        
        result = processor.extract_jamaican_port(sample_bol, verbose=True)
        print("\n📊 Sample Result:")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
