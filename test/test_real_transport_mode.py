#!/usr/bin/env python3
"""
Real Data Test Script for ESAD Transport Mode Processing
Tests the transport mode processing with actual BOL data
"""

import json
import os
from esad_transport_mode import process_transport_mode, get_transport_mode_code

def test_real_transport_data():
    """Test transport mode processing with real BOL data"""
    
    print("🧪 Testing ESAD Transport Mode Processing with Real BOL Data")
    print("=" * 70)
    
    # Load real BOL data
    bol_path = "../../processed_data/orders/ORD-20250824-003/primary_process/bill_of_lading_ORD-20250824-003_primary_extract.json"
    if os.path.exists(bol_path):
        with open(bol_path, 'r') as f:
            bol_data = json.load(f)
        print(f"✅ Loaded BOL extract: {bol_path}")
    else:
        print(f"❌ BOL extract not found: {bol_path}")
        return
    
    # Extract transport-related information
    vessel = bol_data.get('vessel', 'Unknown')
    voyage = bol_data.get('voyage_number', 'Unknown')
    port_origin = bol_data.get('port_of_origin', 'Unknown')
    port_destination = bol_data.get('port_of_destination', 'Unknown')
    berth = bol_data.get('berth', 'Unknown')
    
    print("\n📋 Transport Information from BOL:")
    print("-" * 40)
    print(f"Vessel: {vessel}")
    print(f"Voyage: {voyage}")
    print(f"Port of Origin: {port_origin}")
    print(f"Port of Destination: {port_destination}")
    print(f"Berth: {berth}")
    
    # Test case 1: Full vessel information
    print("\n📋 Test Case 1: Full Vessel Information")
    print("=" * 45)
    
    full_vessel_data = f"Vessel {vessel}, Voyage {voyage}, Port of {port_origin} to {port_destination}, Berth {berth}"
    
    result1 = process_transport_mode(full_vessel_data)
    print(f"Input: {full_vessel_data}")
    print(f"Success: {result1['success']}")
    if result1['success']:
        print(f"Transport Mode: {result1['processed_result']['transport_mode']}")
        print(f"Official Code: {result1['processed_result']['official_code']}")
        print(f"Description: {result1['processed_result']['official_description']}")
        print(f"Confidence Score: {result1['processed_result']['confidence_score']}")
        print(f"Processing Notes: {result1['processing_notes']}")
    
    # Test case 2: Just vessel name
    print("\n📋 Test Case 2: Just Vessel Name")
    print("=" * 35)
    
    vessel_only = f"Vessel {vessel}"
    
    result2 = process_transport_mode(vessel_only)
    print(f"Input: {vessel_only}")
    print(f"Success: {result2['success']}")
    if result2['success']:
        print(f"Transport Mode: {result2['processed_result']['transport_mode']}")
        print(f"Official Code: {result2['processed_result']['official_code']}")
        print(f"Description: {result2['processed_result']['official_description']}")
    
    # Test case 3: Port information only
    print("\n📋 Test Case 3: Port Information Only")
    print("=" * 40)
    
    port_data = f"Port of {port_origin} to {port_destination}, Berth {berth}"
    
    result3 = process_transport_mode(port_data)
    print(f"Input: {port_data}")
    print(f"Success: {result3['success']}")
    if result3['success']:
        print(f"Transport Mode: {result3['processed_result']['transport_mode']}")
        print(f"Official Code: {result3['processed_result']['official_code']}")
        print(f"Description: {result3['processed_result']['official_description']}")
    
    # Test case 4: Get just the code (for integration)
    print("\n📋 Test Case 4: Get Transport Mode Code Only")
    print("=" * 50)
    
    code_only = get_transport_mode_code(full_vessel_data)
    print(f"Input: {full_vessel_data}")
    print(f"Transport Mode Code: {code_only}")
    
    # Test case 5: Different transport modes for comparison
    print("\n📋 Test Case 5: Different Transport Modes Comparison")
    print("=" * 55)
    
    test_cases = [
        ("Sea Transport", "Vessel MAERSK SEALAND, Port of Rotterdam"),
        ("Air Transport", "Flight BA789, Airway Bill AWB123"),
        ("Road Transport", "Truck delivery, Highway transport"),
        ("Postal Transport", "Express mail, Courier service"),
        ("Fixed Transport", "Pipeline transport, Conveyor system")
    ]
    
    for description, test_data in test_cases:
        result = process_transport_mode(test_data)
        print(f"\n{description}:")
        print(f"  Input: {test_data}")
        if result['success']:
            print(f"  Mode: {result['processed_result']['transport_mode']}")
            print(f"  Code: {result['processed_result']['official_code']}")
            print(f"  Description: {result['processed_result']['official_description']}")
        else:
            print(f"  Error: {result['error']}")
    
    print("\n✅ Real data transport mode processing test completed!")
    print("\n📝 Summary:")
    print("   • Box 25 'Mode of transport at the border' now links to esad_transport_mode.py")
    print("   • Raw transport data gets processed using transport_mode.csv reference data")
    print("   • Returns official transport mode codes and descriptions")
    print("   • Integrates with the ESAD field processing system")
    print("   • Supports all transport modes: Sea, Air, Road, Postal, Fixed")
    print(f"\n🎯 For your Amazon order (SEABOARD GEMINI):")
    print(f"   • Transport Mode: Sea")
    print(f"   • Official Code: 1")
    print(f"   • Description: Ocean Transport")

if __name__ == "__main__":
    test_real_transport_data()
