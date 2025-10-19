#!/usr/bin/env python3
"""
Test script for esad_ports.py
Tests the extract_ports_from_bol function with real BOL and invoice data
"""

import json
import sys
import os

# Add customs_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'customs_api'))

from modules.esad_processor.esad_modules.core.esad_ports import extract_ports_from_bol

def load_test_data():
    """Load test BOL and invoice data from processed orders"""
    bol_path = "customs_api/processed_orders/ORD-20251009-002/bills_of_lading/bill_of_lading_ORD-20251009-002_primary_extract.json"
    invoice_path = "customs_api/processed_orders/ORD-20251009-002/invoices/invoice_ORD-20251009-002_invoice_1_extract.json"
    
    with open(bol_path, 'r', encoding='utf-8') as f:
        bol_data = json.load(f)
    
    with open(invoice_path, 'r', encoding='utf-8') as f:
        invoice_data = json.load(f)
    
    return bol_data, invoice_data

def main():
    """Test the port extraction function"""
    print("=" * 80)
    print("TESTING esad_ports.extract_ports_from_bol()")
    print("=" * 80)
    
    # Load test data
    print("\n📁 Loading test data from ORD-20251009-002...")
    bol_data, invoice_data = load_test_data()
    
    print("✅ Test data loaded successfully")
    print(f"   - BOL: {bol_data.get('bill_of_lading', 'N/A')}")
    print(f"   - Invoice: {invoice_data.get('invoice_details', {}).get('pi_number', 'N/A')}")
    
    # Call the extraction function (with verbose=True to see prints)
    print("\n" + "=" * 80)
    result = extract_ports_from_bol(bol_data, invoice_data, verbose=True)
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
    print(f"   Last Port: {result.get('last_port_of_departure', {}).get('port_name', 'N/A')}")
    print(f"   Jamaica Port: {result.get('jamaica_port_of_entry', {}).get('port_name', 'N/A')}")
    print(f"   Country of Origin: {result.get('country_of_origin', 'N/A')}")
    print(f"   Country of Export: {result.get('country_of_export', 'N/A')}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

