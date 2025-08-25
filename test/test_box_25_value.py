#!/usr/bin/env python3
"""
Test Script for Box 25 Value
Shows exactly what value gets returned for box field 25 (Mode of transport at the border)
"""

from esad_transport_mode import get_box_25_value, process_transport_mode

def test_box_25_values():
    """Test what values are returned for box field 25"""
    
    print("🎯 Testing Box 25 'Mode of transport at the border' Values")
    print("=" * 65)
    
    # Test cases with real transport data
    test_cases = [
        {
            "description": "Amazon Order - SEABOARD GEMINI",
            "input": "Vessel SEABOARD GEMINI, Voyage SGM19, Port of Miami to Kingston, Berth B1",
            "expected_code": "1"
        },
        {
            "description": "Air Freight Shipment",
            "input": "Flight AA789, Airway Bill AWB123, Cargo Terminal",
            "expected_code": "4"
        },
        {
            "description": "Truck Delivery",
            "input": "Truck delivery, Highway transport, Vehicle registration",
            "expected_code": "3"
        },
        {
            "description": "Express Mail",
            "input": "Express mail, Courier service, Parcel delivery",
            "expected_code": "5"
        },
        {
            "description": "Pipeline Transport",
            "input": "Pipeline transport, Conveyor system, Fixed installation",
            "expected_code": "7"
        }
    ]
    
    print("\n📋 Box 25 Value Results:")
    print("-" * 30)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Input: {test_case['input']}")
        
        # Get the box 25 value (this is what gets displayed)
        box_25_value = get_box_25_value(test_case['input'])
        print(f"   Box 25 Value: {box_25_value}")
        
        # Get full details for reference
        full_result = process_transport_mode(test_case['input'])
        if full_result['success']:
            description = full_result['processed_result']['official_description']
            confidence = full_result['processed_result']['confidence_score']
            print(f"   Description: {description}")
            print(f"   Confidence: {confidence}")
        
        # Verify expected code
        if box_25_value == test_case['expected_code']:
            print(f"   ✅ Expected: {test_case['expected_code']}")
        else:
            print(f"   ❌ Expected: {test_case['expected_code']}, Got: {box_25_value}")
    
    print("\n🎯 Summary for Box 25:")
    print("-" * 25)
    print("   • Box 25 returns the TRANSPORT MODE CODE")
    print("   • NOT the description or other details")
    print("   • Codes: 1=Ocean, 3=Road, 4=Air, 5=Postal, 7=Fixed")
    print("   • This code gets displayed in the ESAD form")
    
    print("\n📝 For Your Amazon Order:")
    print("-" * 25)
    amazon_data = "Vessel SEABOARD GEMINI, Voyage SGM19, Port of Miami to Kingston"
    amazon_code = get_box_25_value(amazon_data)
    print(f"   Input: {amazon_data}")
    print(f"   Box 25 Value: {amazon_code}")
    print(f"   Meaning: Code {amazon_code} = Ocean Transport")
    print(f"   This is what appears in box field 25 of your ESAD form")

if __name__ == "__main__":
    test_box_25_values()
