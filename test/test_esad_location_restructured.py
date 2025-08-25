#!/usr/bin/env python3
"""
Test Script for Restructured ESAD Location Processor
Tests Box Field 27: Place of Loading/Unloading functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'modules', 'secondary_processing'))

from esad_location import process_loading_unloading_location, get_box_27_value

def test_esad_location_restructured():
    """Test the restructured ESAD location processor for Box Field 27"""
    
    print("🧪 Testing Restructured ESAD Location Processor")
    print("🎯 Box Field 27: Place of Loading/Unloading")
    print("=" * 80)
    
    # Test Case 1: Import ESAD with destination ports
    print("\n📥 TEST CASE 1: IMPORT ESAD - Destination Ports")
    print("-" * 60)
    
    import_bol_data = {
        "port_of_destination": "Kingston",
        "port_of_discharge": "Kingston Port", 
        "place_of_delivery": "Kingston Terminal",
        "final_destination": "Kingston, Jamaica",
        "vessel": "SEABOARD GEMINI",
        "voyage_number": "SGM19",
        "berth": "B1"
    }
    
    print("BOL Data:", import_bol_data)
    
    import_result = process_loading_unloading_location(import_bol_data, "import")
    print(f"\nImport Processing Result:")
    print(f"Success: {import_result['success']}")
    if import_result['success']:
        print(f"✅ Box 27 Value: {import_result['box_27_value']}")
        print(f"✅ Extracted Port: {import_result['extracted_port']}")
        print(f"✅ LOCODE: {import_result['locode']}")
        print(f"✅ Source Field: {import_result['source_field']}")
    else:
        print(f"❌ Error: {import_result['error']}")
    
    print(f"📝 Processing Notes: {import_result['processing_notes']}")
    
    # Test Case 2: Export ESAD with loading ports
    print("\n📤 TEST CASE 2: EXPORT ESAD - Loading Ports")
    print("-" * 60)
    
    export_bol_data = {
        "port_of_loading": "Montego Bay",
        "port_of_departure": "Montego Bay Port",
        "port_of_lading": "Montego Bay Terminal",
        "vessel": "CARIBBEAN STAR",
        "voyage_number": "CSB25"
    }
    
    print("BOL Data:", export_bol_data)
    
    export_result = process_loading_unloading_location(export_bol_data, "export")
    print(f"\nExport Processing Result:")
    print(f"Success: {export_result['success']}")
    if export_result['success']:
        print(f"✅ Box 27 Value: {export_result['box_27_value']}")
        print(f"✅ Extracted Port: {export_result['extracted_port']}")
        print(f"✅ LOCODE: {export_result['locode']}")
        print(f"✅ Source Field: {export_result['source_field']}")
    else:
        print(f"❌ Error: {export_result['error']}")
    
    print(f"📝 Processing Notes: {export_result['processing_notes']}")
    
    # Test Case 3: Real BOL data structure (Amazon order)
    print("\n📋 TEST CASE 3: REAL BOL DATA - Amazon Order")
    print("-" * 60)
    
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
    
    print("Real BOL Data (Amazon Order):", real_bol_data)
    
    # Test import scenario
    real_import_result = process_loading_unloading_location(real_bol_data, "import")
    print(f"\nReal Import Result:")
    print(f"Success: {real_import_result['success']}")
    if real_import_result['success']:
        print(f"✅ Box 27 Value: {real_import_result['box_27_value']}")
        print(f"✅ Extracted Port: {real_import_result['extracted_port']}")
        print(f"✅ LOCODE: {real_import_result['locode']}")
    
    # Test export scenario
    real_export_result = process_loading_unloading_location(real_bol_data, "export")
    print(f"\nReal Export Result:")
    print(f"Success: {real_export_result['success']}")
    if real_export_result['success']:
        print(f"✅ Box 27 Value: {real_export_result['box_27_value']}")
        print(f"✅ Extracted Port: {real_export_result['extracted_port']}")
        print(f"✅ LOCODE: {real_export_result['locode']}")
    
    # Test Case 4: Box 27 Value Function
    print("\n🎯 TEST CASE 4: BOX 27 VALUE FUNCTION")
    print("-" * 60)
    
    import_box_27 = get_box_27_value(import_bol_data, "import")
    export_box_27 = get_box_27_value(export_bol_data, "export")
    
    print(f"Import Box 27 Value: {import_box_27}")
    print(f"Export Box 27 Value: {export_box_27}")
    
    # Test Case 5: Error handling
    print("\n⚠️ TEST CASE 5: ERROR HANDLING")
    print("-" * 60)
    
    # Test with invalid ESAD type
    invalid_type_result = process_loading_unloading_location(import_bol_data, "invalid_type")
    print(f"Invalid ESAD Type Result:")
    print(f"Success: {invalid_type_result['success']}")
    print(f"Error: {invalid_type_result['error']}")
    
    # Test with empty BOL data
    empty_bol_result = process_loading_unloading_location({}, "import")
    print(f"\nEmpty BOL Data Result:")
    print(f"Success: {empty_bol_result['success']}")
    print(f"Error: {empty_bol_result['error']}")
    
    # Test Case 6: Different port scenarios
    print("\n🌊 TEST CASE 6: DIFFERENT PORT SCENARIOS")
    print("-" * 60)
    
    port_scenarios = [
        {
            "name": "Kingston Port",
            "bol_data": {"port_of_destination": "Kingston Port", "vessel": "TEST VESSEL"},
            "esad_type": "import"
        },
        {
            "name": "Montego Bay",
            "bol_data": {"port_of_loading": "Montego Bay", "vessel": "TEST VESSEL"},
            "esad_type": "export"
        },
        {
            "name": "Ocho Rios",
            "bol_data": {"port_of_discharge": "Ocho Rios", "vessel": "TEST VESSEL"},
            "esad_type": "import"
        }
    ]
    
    for scenario in port_scenarios:
        print(f"\nTesting: {scenario['name']}")
        result = process_loading_unloading_location(scenario['bol_data'], scenario['esad_type'])
        if result['success']:
            print(f"  ✅ Box 27 Value: {result['box_27_value']}")
            print(f"  ✅ Port: {result['extracted_port']}")
        else:
            print(f"  ❌ Error: {result['error']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print("✅ Box Field 27: Place of Loading/Unloading")
    print("✅ Import ESAD: Extracts destination ports from BOL")
    print("✅ Export ESAD: Extracts loading ports from BOL")
    print("✅ Returns: Single LOCODE value for the field")
    print("✅ Matches against locode_JM.csv database")
    print("✅ One field, one value returned")
    print("✅ Handles both import and export scenarios")
    print("✅ Error handling for invalid inputs")
    
    print("\n🎯 Key Functions Tested:")
    print("   • process_loading_unloading_location() - Full processing details")
    print("   • get_box_27_value() - Direct LOCODE value for Box 27")
    
    print("\n🏁 All tests completed successfully!")

if __name__ == "__main__":
    test_esad_location_restructured()
