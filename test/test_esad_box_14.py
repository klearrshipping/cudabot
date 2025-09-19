#!/usr/bin/env python3
"""
Test script for eSAD Box 14 field (Declarant/Representative TRN No.)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_14_field():
    """Test Box 14 field: Declarant/Representative TRN No."""
    
    print("🧪 Testing eSAD Box 14 Field")
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
        
        # Test Box 14 field
        box_14_field = {
            "box_field": "14",
            "field_name": "Declarant/Representative TRN No.",
            "description": "TRN of the person/brokerage firm designated to act as clearing agent",
            "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_trn script using client table lookup based on declarant/representative company name. No LLM processing required.",
            "processing_method": "automated_trn_lookup",
            "script": "esad_trn"
        }
        
        print(f"\n📋 Testing Box 14 Field:")
        print(f"   • Declarant/Representative TRN No. (esad_trn script)")
        
        # Test specialized script processing
        field_name = box_14_field["field_name"]
        script = box_14_field["script"]
        
        print(f"\n🔍 Testing: {field_name}")
        print(f"   Script: {script}")
        
        field_value = orchestrator._run_specialized_script(
            script, field_name, invoice_data, bol_data
        )
        
        if field_value:
            print(f"   ✅ Result: {field_value}")
        else:
            print(f"   ⚠️ No data returned from {script}")
        
        print(f"\n📊 Box 14 Test Summary:")
        print(f"   • Field tested: Declarant/Representative TRN No.")
        print(f"   • Script: esad_trn")
        print(f"   • Processing: Automated TRN lookup")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_14_field()
    if success:
        print(f"\n🎉 Box 14 test completed successfully!")
    else:
        print(f"\n💥 Box 14 test failed!")
        sys.exit(1)
