#!/usr/bin/env python3
"""
ESAD Location Processor - Box Field 27: Place of Loading/Unloading
Processes port information from Bill of Lading to return appropriate LOCODE values
Handles both import and export scenarios
"""

import pandas as pd
import re
from typing import Dict, Any, Optional, List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from modules.core.csv_data_client import fetch_locodes
except ImportError:
    # Fallback for direct execution
    def fetch_locodes():
        try:
            return pd.read_csv("data/locode_JM.csv")
        except:
            return pd.DataFrame()

# Override to use Jamaican LOCODEs specifically
def fetch_jamaican_locodes():
    """Fetch only Jamaican LOCODEs from locode_JM.csv"""
    try:
        # Try multiple possible paths
        possible_paths = [
            "data/locode_JM.csv",
            "../data/locode_JM.csv",
            "../../data/locode_JM.csv"
        ]
        
        for path in possible_paths:
            try:
                return pd.read_csv(path)
            except:
                continue
        
        # If all paths fail, try to find the file
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        final_path = os.path.join(project_root, "data", "locode_JM.csv")
        
        return pd.read_csv(final_path)
        
    except Exception as e:
        print(f"Error loading Jamaican LOCODEs: {e}")
        return pd.DataFrame()

class LocationProcessor:
    """
    Processes port information for Box Field 27: Place of Loading/Unloading
    Returns LOCODE values based on import/export scenarios
    """
    
    def __init__(self):
        """Initialize the location processor"""
        self.locode_data = None
        self._load_reference_data()
    
    def _load_reference_data(self):
        """Load LOCODE data from CSV file"""
        try:
            # Load LOCODE data for Jamaican ports specifically
            self.locode_data = fetch_jamaican_locodes()
            
            print(f"✅ Loaded {len(self.locode_data)} LOCODE records for Jamaican ports")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not load LOCODE data: {e}")
            self.locode_data = pd.DataFrame()
    
    def process_loading_unloading_location(self, bol_data: Dict[str, Any], esad_type: str = "import") -> Dict[str, Any]:
        """
        Process place of loading/unloading for Box Field 27
        
        Args:
            bol_data: Bill of Lading data containing port information
            esad_type: "import" or "export" to determine which ports to extract
            
        Returns:
            Dict with processed location information and LOCODE value
        """
        if not bol_data or not isinstance(bol_data, dict):
            return {
                "success": False,
                "error": "No BOL data provided",
                "box_27_value": None,
                "extracted_port": None,
                "locode": None,
                "processing_notes": ["No BOL data available"]
            }
        
        if esad_type not in ["import", "export"]:
            return {
                "success": False,
                "error": "Invalid ESAD type. Must be 'import' or 'export'",
                "box_27_value": None,
                "extracted_port": None,
                "locode": None,
                "processing_notes": ["Invalid ESAD type specified"]
            }
        
        try:
            if esad_type == "import":
                return self._process_import_location(bol_data)
            else:
                return self._process_export_location(bol_data)
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Processing error: {str(e)}",
                "box_27_value": None,
                "extracted_port": None,
                "locode": None,
                "processing_notes": [f"Exception during processing: {str(e)}"]
            }
    
    def _process_import_location(self, bol_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process import location - extract destination ports from BOL
        """
        # For imports, we need the destination port (where goods arrive in Jamaica)
        port_fields = [
            'port_of_destination',
            'port_of_discharge', 
            'place_of_delivery',
            'final_destination',
            'destination_port',
            'discharge_port'
        ]
        
        extracted_port = None
        source_field = None
        
        # Try to extract port from available fields
        for field in port_fields:
            if field in bol_data and bol_data[field]:
                extracted_port = str(bol_data[field]).strip()
                source_field = field
                break
        
        if not extracted_port:
            return {
                "success": False,
                "error": "No destination port found in BOL data",
                "box_27_value": None,
                "extracted_port": None,
                "locode": None,
                "processing_notes": ["Could not find destination port in BOL fields: " + ", ".join(port_fields)]
            }
        
        # Find matching LOCODE
        locode_result = self._find_matching_locode(extracted_port)
        
        if locode_result["found"]:
            return {
                "success": True,
                "error": None,
                "box_27_value": locode_result["locode"],
                "extracted_port": extracted_port,
                "locode": locode_result["locode"],
                "source_field": source_field,
                "processing_notes": [
                    f"Import ESAD: Extracted destination port '{extracted_port}' from BOL field '{source_field}'",
                    f"Matched to LOCODE: {locode_result['locode']} ({locode_result['description']})",
                    f"Box 27 value: {locode_result['locode']}"
                ]
            }
        else:
            return {
                "success": False,
                "error": f"Destination port '{extracted_port}' not found in LOCODE database",
                "box_27_value": None,
                "extracted_port": extracted_port,
                "locode": None,
                "source_field": source_field,
                "processing_notes": [
                    f"Import ESAD: Extracted destination port '{extracted_port}' from BOL field '{source_field}'",
                    f"Port not found in LOCODE database - manual lookup required"
                ]
            }
    
    def _process_export_location(self, bol_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process export location - extract loading ports from BOL
        """
        # For exports, we need the loading port (where goods depart from Jamaica)
        port_fields = [
            'port_of_loading',
            'port_of_departure',
            'port_of_lading',
            'place_of_receipt',
            'loading_port',
            'origin_port'
        ]
        
        extracted_port = None
        source_field = None
        
        # Try to extract port from available fields
        for field in port_fields:
            if field in bol_data and bol_data[field]:
                extracted_port = str(bol_data[field]).strip()
                source_field = field
                break
        
        if not extracted_port:
            return {
                "success": False,
                "error": "No loading port found in BOL data",
                "box_27_value": None,
                "extracted_port": None,
                "locode": None,
                "processing_notes": ["Could not find loading port in BOL fields: " + ", ".join(port_fields)]
            }
        
        # Find matching LOCODE
        locode_result = self._find_matching_locode(extracted_port)
        
        if locode_result["found"]:
            return {
                "success": True,
                "error": None,
                "box_27_value": locode_result["locode"],
                "extracted_port": extracted_port,
                "locode": locode_result["locode"],
                "source_field": source_field,
                "processing_notes": [
                    f"Export ESAD: Extracted loading port '{extracted_port}' from BOL field '{source_field}'",
                    f"Matched to LOCODE: {locode_result['locode']} ({locode_result['description']})",
                    f"Box 27 value: {locode_result['locode']}"
                ]
            }
        else:
            return {
                "success": False,
                "error": f"Loading port '{extracted_port}' not found in LOCODE database",
                "box_27_value": None,
                "extracted_port": extracted_port,
                "locode": None,
                "source_field": source_field,
                "processing_notes": [
                    f"Export ESAD: Extracted loading port '{extracted_port}' from BOL field '{source_field}'",
                    f"Port not found in LOCODE database - manual lookup required"
                ]
            }
    
    def _find_matching_locode(self, port_name: str) -> Dict[str, Any]:
        """
        Find matching LOCODE for a given port name
        
        Args:
            port_name: Port name to search for
            
        Returns:
            Dict with LOCODE match information
        """
        if self.locode_data.empty:
            return {
                "found": False,
                "locode": None,
                "description": None,
                "error": "No LOCODE data available"
            }
        
        try:
            port_name_clean = self._clean_port_name(port_name)
            
            # Try exact match first
            exact_match = self.locode_data[
                self.locode_data['name'].str.contains(port_name_clean, case=False, na=False)
            ]
            
            if not exact_match.empty:
                match = exact_match.iloc[0]
                return {
                    "found": True,
                    "locode": match['locode'],
                    "description": match['name'],
                    "error": None
                }
            
            # Try partial match
            partial_match = self.locode_data[
                self.locode_data['name'].str.contains(port_name_clean, case=False, na=False, regex=False)
            ]
            
            if not partial_match.empty:
                match = partial_match.iloc[0]
                return {
                    "found": True,
                    "locode": match['locode'],
                    "description": match['name'],
                    "error": None
                }
            
            # Try city name match (remove common port terms and match city)
            city_name = self._extract_city_name(port_name_clean)
            if city_name:
                city_match = self.locode_data[
                    self.locode_data['name'].str.contains(city_name, case=False, na=False, regex=False)
                ]
                
                if not city_match.empty:
                    match = city_match.iloc[0]
                    return {
                        "found": True,
                        "locode": match['locode'],
                        "description": match['name'],
                        "error": None
                    }
            
            return {
                "found": False,
                "locode": None,
                "description": None,
                "error": f"Port '{port_name}' not found in LOCODE database"
            }
            
        except Exception as e:
            return {
                "found": False,
                "locode": None,
                "description": None,
                "error": f"Error searching LOCODE database: {str(e)}"
            }
    
    def _clean_port_name(self, port_name: str) -> str:
        """
        Clean port name for better matching
        
        Args:
            port_name: Raw port name
            
        Returns:
            Cleaned port name
        """
        if not port_name:
            return ""
        
        # Remove common prefixes/suffixes
        port_name = re.sub(r'\b(port of|port|harbor|harbour|terminal|berth|dock|pier|wharf)\b', '', port_name, flags=re.IGNORECASE)
        
        # Remove extra whitespace and punctuation
        port_name = re.sub(r'[^\w\s]', ' ', port_name)
        port_name = re.sub(r'\s+', ' ', port_name).strip()
        
        return port_name
    
    def _extract_city_name(self, port_name: str) -> str:
        """
        Extract city name from port name by removing common port-related terms
        
        Args:
            port_name: Port name to extract city from
            
        Returns:
            Extracted city name
        """
        if not port_name:
            return ""
        
        # Remove common port-related terms
        city_name = re.sub(r'\b(port|harbor|harbour|terminal|berth|dock|pier|wharf|airport|seaport)\b', '', port_name, flags=re.IGNORECASE)
        
        # Remove extra whitespace and punctuation
        city_name = re.sub(r'[^\w\s]', ' ', city_name)
        city_name = re.sub(r'\s+', ' ', city_name).strip()
        
        return city_name
    
    def _get_common_variations(self, port_name: str) -> List[str]:
        """
        Get common variations of a port name for better matching
        
        Args:
            port_name: Base port name
            
        Returns:
            List of common variations
        """
        variations = [port_name]
        
        # Add common abbreviations
        if 'kingston' in port_name.lower():
            variations.extend(['kingston', 'kgn', 'kingston port'])
        elif 'montego' in port_name.lower():
            variations.extend(['montego bay', 'mobay', 'montego bay port'])
        elif 'ocho rios' in port_name.lower():
            variations.extend(['ocho rios', 'ochi', 'ocho rios port'])
        elif 'falmouth' in port_name.lower():
            variations.extend(['falmouth', 'falmouth port'])
        elif 'port antonio' in port_name.lower():
            variations.extend(['port antonio', 'antonio'])
        elif 'lucea' in port_name.lower():
            variations.extend(['lucea', 'lucea port'])
        elif 'savanna' in port_name.lower():
            variations.extend(['savanna-la-mar', 'savanna la mar', 'savanna'])
        
        return variations
    
    def get_box_27_value(self, bol_data: Dict[str, Any], esad_type: str = "import") -> str:
        """
        Get the value for Box Field 27 (Place of Loading/Unloading)
        
        Args:
            bol_data: Bill of Lading data
            esad_type: "import" or "export"
            
        Returns:
            LOCODE value for Box Field 27 (or empty string if not found)
        """
        result = self.process_loading_unloading_location(bol_data, esad_type)
        if result["success"]:
            return result["box_27_value"]
        return ""


def process_loading_unloading_location(bol_data: Dict[str, Any], esad_type: str = "import") -> Dict[str, Any]:
    """
    Convenience function to process loading/unloading location
    
    Args:
        bol_data: Bill of Lading data
        esad_type: "import" or "export"
        
    Returns:
        Dict with processed location information
    """
    processor = LocationProcessor()
    return processor.process_loading_unloading_location(bol_data, esad_type)


def get_box_27_value(bol_data: Dict[str, Any], esad_type: str = "import") -> str:
    """
    Convenience function to get Box Field 27 value
    
    Args:
        bol_data: Bill of Lading data
        esad_type: "import" or "export"
        
    Returns:
        LOCODE value for Box Field 27
    """
    processor = LocationProcessor()
    return processor.get_box_27_value(bol_data, esad_type)


def main():
    """Test the restructured location processor"""
    
    processor = LocationProcessor()
    
    print("🧪 Testing ESAD Location Processor - Box Field 27: Place of Loading/Unloading")
    print("=" * 80)
    
    # Sample BOL data for testing
    sample_bol_import = {
        "port_of_destination": "Kingston",
        "port_of_discharge": "Kingston Port",
        "place_of_delivery": "Kingston Terminal",
        "final_destination": "Kingston, Jamaica"
    }
    
    sample_bol_export = {
        "port_of_loading": "Montego Bay",
        "port_of_departure": "Montego Bay Port",
        "port_of_lading": "Montego Bay Terminal"
    }
    
    # Test Import Scenario
    print("\n📥 TESTING IMPORT ESAD (Box Field 27)")
    print("=" * 50)
    print("BOL Data:", sample_bol_import)
    
    import_result = processor.process_loading_unloading_location(sample_bol_import, "import")
    print(f"\nImport Result:")
    print(f"Success: {import_result['success']}")
    if import_result['success']:
        print(f"Box 27 Value: {import_result['box_27_value']}")
        print(f"Extracted Port: {import_result['extracted_port']}")
        print(f"LOCODE: {import_result['locode']}")
    else:
        print(f"Error: {import_result['error']}")
    
    print(f"Processing Notes: {import_result['processing_notes']}")
    
    # Test Export Scenario
    print("\n📤 TESTING EXPORT ESAD (Box Field 27)")
    print("=" * 50)
    print("BOL Data:", sample_bol_export)
    
    export_result = processor.process_loading_unloading_location(sample_bol_export, "export")
    print(f"\nExport Result:")
    print(f"Success: {export_result['success']}")
    if export_result['success']:
        print(f"Box 27 Value: {export_result['box_27_value']}")
        print(f"Extracted Port: {export_result['extracted_port']}")
        print(f"LOCODE: {export_result['locode']}")
    else:
        print(f"Error: {export_result['error']}")
    
    print(f"Processing Notes: {export_result['processing_notes']}")
    
    # Test Box 27 Value Function
    print("\n🎯 TESTING BOX 27 VALUE FUNCTION")
    print("=" * 40)
    
    import_box_27 = get_box_27_value(sample_bol_import, "import")
    export_box_27 = get_box_27_value(sample_bol_export, "export")
    
    print(f"Import Box 27 Value: {import_box_27}")
    print(f"Export Box 27 Value: {export_box_27}")
    
    print("\n✅ Location processor test completed!")
    print("\n📝 Key Points:")
    print("   • Box Field 27: Place of Loading/Unloading")
    print("   • Import: Extracts destination ports from BOL")
    print("   • Export: Extracts loading ports from BOL")
    print("   • Returns: Single LOCODE value for the field")


if __name__ == "__main__":
    main()
