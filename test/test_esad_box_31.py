#!/usr/bin/env python3
"""
Test script for eSAD Box 31 fields (Commercial description, HS Code, Marks and numbers)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_31_fields():
    """Test Box 31 fields: Commercial description, HS Code, Marks and numbers"""
    
    print("🧪 Testing eSAD Box 31 Fields")
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
        
        # Test Box 31 fields by calling processors directly
        print(f"\n📋 Testing Box 31 Fields:")
        print(f"   • Commercial description (esad_product)")
        print(f"   • HS Code (esad_product)")
        print(f"   • Marks and numbers (esad_marks)")

        # Import processors
        from modules.esad_processor.esad_modules.esad_product import process_commercial_description
        from modules.esad_processor.esad_modules.esad_marks import process_commercial_description as process_marks

        # Source description: prefer invoice description then BOL cargo description
        description = (
            invoice_data.get('description') or
            invoice_data.get('item_description') or
            bol_data.get('cargo_description') or
            ''
        )

        print(f"\n🔍 Testing: Commercial description & HS Code")
        product_result = process_commercial_description(description, verbose=False, get_hs_code=True)

        if product_result:
            if product_result.get('standardized_name'):
                print(f"   ✅ Commercial description: {product_result.get('standardized_name')}")
            if product_result.get('hs_code'):
                print(f"   ✅ HS Code: {product_result.get('hs_code')}")
        else:
            print(f"   ⚠️ No result from esad_product")

        print(f"\n🔍 Testing: Marks and numbers")
        marks_result = process_marks(description)
        if marks_result and marks_result.get('marks'):
            print(f"   ✅ Marks and numbers: {marks_result.get('marks')}")
        else:
            print(f"   ⚠️ No marks found")

        print(f"\n📊 Box 31 Test Summary:")
        print(f"   • Fields tested: Commercial description, HS Code, Marks and numbers")
        print(f"   • Scripts: esad_product, esad_marks")
        print(f"   • Processing: Direct script execution")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_31_fields()
    if success:
        print(f"\n🎉 Box 31 test completed successfully!")
    else:
        print(f"\n💥 Box 31 test failed!")
        sys.exit(1)
