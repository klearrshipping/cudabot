#!/usr/bin/env python3
"""
ESAD Locode Processor
Processes the "Place of Loading/Unloading" field using locode_JM.csv
"""

import pandas as pd
from typing import Dict, Any, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class LocodeProcessor:
    """
    Processes loading/unloading locations using Jamaican locode data
    """
    
    def __init__(self):
        """Initialize the locode processor"""
        self.locode_data = None
        self._load_reference_data()
    
    def _load_reference_data(self):
        """Load Jamaican locode data from CSV file"""
        try:
            # Load locode data (Jamaican locations) - for loading/unloading locations
            self.locode_data = pd.read_csv("data/locode_JM.csv")
            print(f"✅ Loaded {len(self.locode_data)} Jamaican locodes for loading/unloading locations")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not load locode data: {e}")
            self.locode_data = pd.DataFrame()
    
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


def process_loading_location(location_text: str) -> Dict[str, Any]:
    """
    Convenience function to process loading location
    
    Args:
        location_text: Location text from esad_fields
        
    Returns:
        Dict with processed location information
    """
    processor = LocodeProcessor()
    return processor.process_loading_location(location_text)


def main():
    """Test the locode processor"""
    
    processor = LocodeProcessor()
    
    print("Testing Locode Processor")
    print("=" * 50)
    
    # Test Loading/Unloading Locations (using locode_JM.csv)
    print("\n🔍 TESTING LOADING/UNLOADING LOCATIONS (locode_JM.csv)")
    print("=" * 60)
    
    test_locations = [
        "Kingston, Jamaica",
        "Miami, United States", 
        "Black River, Jamaica",
        "Montego Bay, Jamaica"
    ]
    
    for location in test_locations:
        print(f"\nInput: {location}")
        result = processor.process_loading_location(location)
        print(f"Result: {result}")
        print("-" * 40)


if __name__ == "__main__":
    main()
