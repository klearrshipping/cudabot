#!/usr/bin/env python3
"""
Test script for esad_office_code.py
Tests the office code and manifest extraction function with real BOL data
"""

import json
import sys
import os

# Add customs_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'customs_api'))

from modules.esad_processor.esad_modules.core.esad_office_code import extract_office_information

def load_test_data():
    """Load test BOL data from processed orders"""
    bol_path = "customs_api/processed_orders/ORD-20251009-002/bills_of_lading/bill_of_lading_ORD-20251009-002_primary_extract.json"
    
    with open(bol_path, 'r', encoding='utf-8') as f:
        bol_data = json.load(f)
    
    return bol_data

def main():
    """Test the office code extraction function"""
    print("=" * 80)
    print("TESTING esad_office_code.extract_office_information()")
    print("=" * 80)
    
    # Load test data
    print("\n📁 Loading test data from ORD-20251009-002...")
    bol_data = load_test_data()
    
    print("✅ Test data loaded successfully")
    print(f"   - BOL: {bol_data.get('bill_of_lading', 'N/A')}")
    print(f"   - Document Type: {bol_data.get('document_type', 'N/A')}")
    
    # Call the extraction function (with verbose=True to see prints)
    print("\n" + "=" * 80)
    result = extract_office_information(bol_data, verbose=True)
    print("=" * 80)
    
    # Display detailed results
    print("\n📊 DETAILED RESULTS:")
    print("=" * 80)
    print(json.dumps(result, indent=2))
    print("=" * 80)
    
    # Summary
    print("\n✅ TEST COMPLETED SUCCESSFULLY")
    print("\n📋 QUICK SUMMARY:")
    print(f"   Status: {result.get('extraction_metadata', {}).get('status', 'unknown')}")
    print(f"   Asycuda/Manifest Ref: {result.get('asycuda_number', 'N/A')}")
    print(f"   BOL Number: {result.get('bol_number', 'N/A')}")
    print(f"   Wharfinger: {result.get('wharfinger', 'N/A')}")
    print(f"   Office Of Submission: {result.get('office_of_submission', 'N/A')}")
    
    if result.get('matched_warehouse'):
        print(f"\n   🏢 Matched Warehouse:")
        print(f"      Code: {result['matched_warehouse']['code']}")
        print(f"      Warehouse: {result['matched_warehouse']['warehouse']}")
        print(f"      Office ID: {result['matched_warehouse']['office_id']}")
    else:
        print(f"\n   ❌ No warehouse match found")
    
    print("\n" + "=" * 80)
    print("FIELD CLARIFICATION:")
    print("=" * 80)
    print("✓ Asycuda Number = Manifest Reference (SAME FIELD, e.g., JMOSC-2025-574)")
    print("✓ BOL Number = Shipping line reference (e.g., PSHFHKIN25072146)")
    print("✓ These are TWO DIFFERENT numbers!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

