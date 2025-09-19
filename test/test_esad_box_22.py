#!/usr/bin/env python3
"""
Test script for eSAD Box 22 fields (Currency and Invoice amounts)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_22_fields():
    """Test Box 22 fields: Currency and Invoice amounts"""
    
    print("🧪 Testing eSAD Box 22 Fields")
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
        
        # Initialize eSAD orchestrator
        orchestrator = ESADOrchestrator()
        
        # Test Box 22 fields by processing the complete order
        order_number = "ORD-20250916-004"  # Extract from the test data path
        
        print(f"\n📋 Testing Box 22 Fields:")
        print(f"   • Currency code")
        print(f"   • Amount")
        print(f"   • Order: {order_number}")
        
        print(f"\n🔍 Processing complete eSAD for order...")
        
        # Change to customs_api directory so orchestrator can find processed_orders
        original_cwd = os.getcwd()
        customs_api_dir = os.path.join(os.path.dirname(__file__), '..', 'customs_api')
        os.chdir(customs_api_dir)
        
        try:
            # Process the complete eSAD using the orchestrator
            esad_result = orchestrator.process_order_esad(order_number)
        finally:
            # Restore original working directory
            os.chdir(original_cwd)
        
        # Extract Box 22 results from the processing results
        if esad_result.get("status") == "success":
            esad_data = esad_result.get("esad_data", {})
            box_22_data = esad_data.get("22", {})
            
            currency_code = box_22_data.get("Currency code")
            amount = box_22_data.get("Amount")
            
            print(f"\n🔍 Box 22 Results:")
            if currency_code:
                print(f"   ✅ Currency code: {currency_code}")
            else:
                print(f"   ⚠️ No data found for Currency code")
                
            if amount:
                print(f"   ✅ Amount: {amount}")
            else:
                print(f"   ⚠️ No data found for Amount")
                
            print(f"\n📊 Box 22 Test Summary:")
            print(f"   • Fields tested: 2 (Currency code, Amount)")
            print(f"   • Processing: Complete eSAD processing via ESADOrchestrator")
            print(f"   • Status: {esad_result.get('status')}")
        else:
            print(f"   ❌ eSAD processing failed: {esad_result.get('error')}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_22_fields()
    if success:
        print(f"\n🎉 Box 22 test completed successfully!")
    else:
        print(f"\n💥 Box 22 test failed!")
        sys.exit(1)
