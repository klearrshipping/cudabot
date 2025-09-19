#!/usr/bin/env python3
"""
Test script for eSAD Box 24 field (Nature of transaction)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_24_field():
    """Test Box 24 field: Nature of transaction"""
    
    print("🧪 Testing eSAD Box 24 Field")
    print("=" * 50)
    
    # Load test data
    invoice_file = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20250916-004\invoices\invoice_ORD-20250916-004_primary_extract.json"
    bol_file = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20250916-004\bills_of_lading\bill_of_lading_ORD-20250916-004_primary_extract.json"
    
    try:
        # Load invoice data
        with open(invoice_file, 'r', encoding='utf-8') as f:
            invoice_data = json.load(f)
        print(f"✅ Loaded invoice data: {len(invoice_data)} fields")
        
        # Load BOL data
        with open(bol_file, 'r', encoding='utf-8') as f:
            bol_data = json.load(f)
        print(f"✅ Loaded BOL data: {len(bol_data)} fields")
        
        # Test Box 24 field using the transaction type processor directly
        print(f"\n📋 Testing Box 24 Field:")
        print(f"   • Nature of transaction (esad_trans_type)")

        # Import transaction type processor
        from modules.esad_processor.esad_modules.esad_trans_type import process_transaction_type

        # Build raw transaction context text from available data
        raw_transaction_data = (
            invoice_data.get('payment_terms') or
            invoice_data.get('incoterm') or
            invoice_data.get('notes') or
            json.dumps({"invoice_terms": invoice_data.get('payment_terms', ''), "incoterm": invoice_data.get('incoterm', '')})
        )

        print(f"\n🔍 Testing: Nature of transaction")
        print(f"   Script: esad_trans_type")

        tx_result = process_transaction_type(str(raw_transaction_data))

        if tx_result and tx_result.get('nature_of_transaction'):
            print(f"   ✅ Result: {tx_result.get('nature_of_transaction')}")
        else:
            print(f"   ⚠️ No nature of transaction determined")

        print(f"\n📊 Box 24 Test Summary:")
        print(f"   • Field tested: Nature of transaction")
        print(f"   • Script: esad_trans_type")
        print(f"   • Processing: Direct script execution")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_24_field()
    if success:
        print(f"\n🎉 Box 24 test completed successfully!")
    else:
        print(f"\n💥 Box 24 test failed!")
        sys.exit(1)
