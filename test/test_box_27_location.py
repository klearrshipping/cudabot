#!/usr/bin/env python3
"""
Test Script for Box Field 27: Place of Loading/Unloading
Tests the restructured esad_location.py script
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'modules', 'secondary_processing'))

from esad_location import process_loading_unloading_location, get_box_27_value

def test_box_27_location():
    """Test Box Field 27 location processing"""
    
    print("🧪 Testing Box Field 27: Place of Loading/Unloading")
    print("=" * 70)
    
    # Sample BOL data for testing
    sample_bol_import = {
        "port_of_destination": "Kingston",
        "port_of_discharge": "Kingston Port", 
        "place_of_delivery": "Kingston Terminal",
        "final_destination": "Kingston, Jamaica",
        "vessel": "SEABOARD GEMINI",
        "voyage_number": "SGM19"
    }
    
    sample_bol_export = {
        "port_of_loading": "Montego Bay",
        "port_of_departure": "Montego Bay Port",
        "port_of_lading": "Montego Bay Terminal",
        "vessel": "CARIBBEAN STAR",
        "voyage_number": "CSB25"
    }
    
    # Test Import Scenario
    print("\n📥 TESTING IMPORT ESAD (Box Field 27)")
    print("=" * 50)
    print("BOL Data:", sample_bol_import)
    
    import_result = process_loading_unloading_location(sample_bol_import, "import")
    print(f"\nImport Result:")
    print(f"Success: {import_result['success']}")
    if import_result['success']:
        print(f"Box 27 Value: {import_result['box_27_value']}")
        print(f"Extracted Port: {import_result['extracted_port']}")
        print(f"LOCODE: {import_result['locode']}")
        print(f"Source Field: {import_result['source_field']}")
    else:
        print(f"Error: {import_result['error']}")
    
    print(f"Processing Notes: {import_result['processing_notes']}")
    
    # Test Export Scenario
    print("\n📤 TESTING EXPORT ESAD (Box Field 27)")
    print("=" * 50)
    print("BOL Data:", sample_bol_export)
    
    export_result = process_loading_unloading_location(sample_bol_export, "export")
    print(f"\nExport Result:")
    print(f"Success: {export_result['success']}")
    if export_result['success']:
        print(f"Box 27 Value: {export_result['box_27_value']}")
        print(f"Extracted Port: {export_result['extracted_port']}")
        print(f"LOCODE: {export_result['locode']}")
        print(f"Source Field: {export_result['source_field']}")
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
    
    # Test with real BOL data structure
    print("\n📋 TESTING WITH REAL BOL STRUCTURE")
    print("=" * 50)
    
    real_bol_data = {
        "port_of_origin": "Miami",
        "port_of_destination": "Kingston",
        "port_of_loading": "Miami Port",
        "port_of_discharge": "Kingston Port",
        "place_of_delivery": "Kingston Terminal",
        "final_destination": "Kingston, Jamaica",
        "vessel": "SEABOARD GEMINI",
        "voyage_number": "SGM19",
        "berth": "B1"
    }
    
    print("Real BOL Data:", real_bol_data)
    
    # Test import scenario
    real_import_result = process_loading_unloading_location(real_bol_data, "import")
    print(f"\nReal Import Result:")
    print(f"Success: {real_import_result['success']}")
    if real_import_result['success']:
        print(f"Box 27 Value: {real_import_result['box_27_value']}")
        print(f"Extracted Port: {real_import_result['extracted_port']}")
        print(f"LOCODE: {real_import_result['locode']}")
    
    # Test export scenario
    real_export_result = process_loading_unloading_location(real_bol_data, "export")
    print(f"\nReal Export Result:")
    print(f"Success: {real_export_result['success']}")
    if real_export_result['success']:
        print(f"Box 27 Value: {real_export_result['box_27_value']}")
        print(f"Extracted Port: {real_export_result['extracted_port']}")
        print(f"LOCODE: {real_export_result['locode']}")
    
    print("\n✅ Box Field 27 location processing test completed!")
    print("\n📝 Key Points:")
    print("   • Box Field 27: Place of Loading/Unloading")
    print("   • Import: Extracts destination ports (port_of_destination, port_of_discharge, etc.)")
    print("   • Export: Extracts loading ports (port_of_loading, port_of_departure, etc.)")
    print("   • Returns: Single LOCODE value for the field")
    print("   • Matches against locode_JM.csv database")
    print("   • One field, one value returned")

if __name__ == "__main__":
    test_box_27_location()
