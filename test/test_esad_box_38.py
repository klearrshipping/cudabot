#!/usr/bin/env python3
"""
Test script for eSAD Box 38 field (Net mass)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_38_field():
    """Test Box 38 field: Net mass"""
    
    print("🧪 Testing eSAD Box 38 Field")
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
        
        # Test Box 38 field
        box_38_field = {
            "box_field": "38",
            "field_name": "Net mass",
            "description": "Net weight of the goods (excluding packaging)",
            "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_weight script using net weight calculations. No LLM processing required.",
            "processing_method": "automated_net_weight_calculation",
            "script": "esad_weight"
        }
        
        print(f"\n📋 Testing Box 38 Field:")
        print(f"   • Net mass (esad_weight script)")
        
        # Test specialized script processing
        field_name = box_38_field["field_name"]
        script = box_38_field["script"]
        
        print(f"\n🔍 Testing: {field_name}")
        print(f"   Script: {script}")
        
        field_value = orchestrator._run_specialized_script(
            script, field_name, invoice_data, bol_data
        )
        
        if field_value:
            print(f"   ✅ Result: {field_value}")
        else:
            print(f"   ⚠️ No data returned from {script}")
        
        print(f"\n📊 Box 38 Test Summary:")
        print(f"   • Field tested: Net mass")
        print(f"   • Script: esad_weight")
        print(f"   • Processing: Automated net weight calculation")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_38_field()
    if success:
        print(f"\n🎉 Box 38 test completed successfully!")
    else:
        print(f"\n💥 Box 38 test failed!")
        sys.exit(1)
