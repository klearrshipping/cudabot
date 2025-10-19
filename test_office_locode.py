#!/usr/bin/env python3
"""
Test script for esad_office_code and esad_locode
Tests both modules simultaneously with the same BOL/Arrival Notice data
"""

import json
import sys
import os

# Add customs_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'customs_api'))

from modules.esad_processor.esad_modules.core.esad_office_code import extract_office_information
from modules.esad_processor.esad_modules.secondary.esad_locode import LocodeProcessor

def load_test_data():
    """Load test BOL data from processed orders"""
    bol_path = "customs_api/processed_orders/ORD-20251009-002/bills_of_lading/bill_of_lading_ORD-20251009-002_primary_extract.json"
    
    with open(bol_path, 'r', encoding='utf-8') as f:
        bol_data = json.load(f)
    
    return bol_data

def main():
    """Test both office code and locode extraction functions"""
    print("=" * 80)
    print("TESTING esad_office_code & esad_locode SIMULTANEOUSLY")
    print("=" * 80)
    
    # Load test data once
    print("\n📁 Loading test data from ORD-20251009-002...")
    bol_data = load_test_data()
    
    print("✅ Test data loaded successfully")
    print(f"   - BOL: {bol_data.get('bill_of_lading', 'N/A')}")
    print(f"   - Document Type: {bol_data.get('document_type', 'N/A')}")
    
    # ========================================================================
    # TEST 1: Office Code Extraction
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 1: OFFICE CODE & WAREHOUSE EXTRACTION")
    print("=" * 80)
    
    office_result = extract_office_information(bol_data, verbose=True)
    
    # ========================================================================
    # TEST 2: LOCODE Extraction
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST 2: JAMAICAN PORT & LOCODE EXTRACTION")
    print("=" * 80)
    
    locode_processor = LocodeProcessor()
    locode_result = locode_processor.extract_jamaican_port(bol_data, verbose=True)
    
    # ========================================================================
    # COMBINED RESULTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("COMBINED RESULTS SUMMARY")
    print("=" * 80)
    
    print("\n📦 OFFICE & WAREHOUSE INFORMATION:")
    print("-" * 80)
    print(f"   Asycuda/Manifest Ref: {office_result.get('asycuda_number', 'N/A')}")
    print(f"   BOL Number: {office_result.get('bol_number', 'N/A')}")
    print(f"   Wharfinger: {office_result.get('wharfinger', 'N/A')}")
    print(f"   Office Of Submission: {office_result.get('office_of_submission', 'N/A')}")
    
    if office_result.get('matched_warehouse'):
        print(f"\n   🏢 Matched Warehouse (BOX 30):")
        print(f"      Code: {office_result['matched_warehouse']['code']}")
        print(f"      Warehouse: {office_result['matched_warehouse']['warehouse']}")
        print(f"      Office ID: {office_result['matched_warehouse']['office_id']}")
    
    print("\n🚢 PORT & LOCODE INFORMATION:")
    print("-" * 80)
    print(f"   Jamaican Port: {locode_result.get('jamaican_port', 'N/A')}")
    
    if locode_result.get('locode'):
        print(f"\n   📍 Matched LOCODE (BOX 27):")
        print(f"      LOCODE: {locode_result['locode']}")
        print(f"      Location: {locode_result['location_name']}")
        print(f"      Subdivision: {locode_result.get('subdivision', 'N/A')}")
    
    # ========================================================================
    # ESAD BOX MAPPING
    # ========================================================================
    print("\n" + "=" * 80)
    print("eSAD BOX FIELD MAPPING")
    print("=" * 80)
    
    print(f"\nBOX 30 (Location of goods):")
    if office_result.get('matched_warehouse'):
        print(f"   → {office_result['matched_warehouse']['code']} ({office_result['matched_warehouse']['warehouse']})")
    else:
        print(f"   → Not matched")
    
    print(f"\nBOX 27 (Place of unloading):")
    if locode_result.get('locode'):
        print(f"   → {locode_result['locode']} ({locode_result['location_name']})")
    else:
        print(f"   → Not matched")
    
    print(f"\nAsycuda/Manifest Reference:")
    print(f"   → {office_result.get('asycuda_number', 'N/A')}")
    
    print(f"\nBOL Number:")
    print(f"   → {office_result.get('bol_number', 'N/A')}")
    
    # ========================================================================
    # DETAILED JSON OUTPUT
    # ========================================================================
    print("\n" + "=" * 80)
    print("DETAILED JSON OUTPUT")
    print("=" * 80)
    
    combined_output = {
        "office_code_result": office_result,
        "locode_result": locode_result
    }
    
    print(json.dumps(combined_output, indent=2))
    
    # ========================================================================
    # TEST STATUS
    # ========================================================================
    print("\n" + "=" * 80)
    print("TEST STATUS")
    print("=" * 80)
    
    office_status = "✅ PASS" if office_result.get('extraction_metadata', {}).get('status') == 'success' else "❌ FAIL"
    locode_status = "✅ PASS" if locode_result.get('success') else "❌ FAIL"
    
    print(f"\nOffice Code Extraction: {office_status}")
    print(f"LOCODE Extraction: {locode_status}")
    
    if office_status == "✅ PASS" and locode_status == "✅ PASS":
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n⚠️  Some tests failed - review results above")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

