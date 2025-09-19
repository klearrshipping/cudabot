#!/usr/bin/env python3
"""
Test script for eSAD Box A fields (Office code and Manifest)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_a_fields():
    """Test Box A fields: Office code and Manifest"""
    
    print("🧪 Testing eSAD Box A Fields")
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
        
        # Test Box A fields specifically
        box_a_fields = [
            {
                "box_field": "A",
                "field_name": "Office code",
                "description": "Identifies the Customs Office where the goods declaration is being submitted for clearance",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_manifest script using Arrival Notice data from Jamaica Customs website. No LLM processing required.",
                "processing_method": "automated_manifest_lookup",
                "script": "esad_manifest"
            },
            {
                "box_field": "A", 
                "field_name": "Manifest",
                "description": "Reference number of the cargo manifest, which contains the goods being declared",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_manifest script using Arrival Notice data from Jamaica Customs website. No LLM processing required.",
                "processing_method": "automated_manifest_lookup",
                "script": "esad_manifest"
            }
        ]
        
        print(f"\n📋 Testing Box A Fields:")
        print(f"   • Office code (esad_manifest script)")
        print(f"   • Manifest (esad_manifest script)")
        
        # Test each Box A field
        for field_def in box_a_fields:
            field_name = field_def["field_name"]
            script = field_def["script"]
            
            print(f"\n🔍 Testing: {field_name}")
            print(f"   Script: {script}")
            
            # Test specialized script processing
            field_value = orchestrator._run_specialized_script(
                script, field_name, invoice_data, bol_data
            )
            
            if field_value:
                print(f"   ✅ Result: {field_value}")
            else:
                print(f"   ⚠️ No data returned from {script}")
        
        print(f"\n📊 Box A Test Summary:")
        print(f"   • Fields tested: 2")
        print(f"   • Script: esad_manifest")
        print(f"   • Processing: Automated manifest lookup")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_a_fields()
    if success:
        print(f"\n🎉 Box A test completed successfully!")
    else:
        print(f"\n💥 Box A test failed!")
        sys.exit(1)
