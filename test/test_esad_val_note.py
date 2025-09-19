#!/usr/bin/env python3
"""
Test script for eSAD val_note fields (Valuation method and related fields)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_val_note_fields():
    """Test val_note fields: Valuation method and related fields"""
    
    print("🧪 Testing eSAD val_note Fields")
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
        
        # Test val_note fields
        val_note_fields = [
            {
                "box_field": "val_note",
                "field_name": "Valuation method",
                "description": "Method used for customs valuation",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_cif script using valuation method analysis. No LLM processing required.",
                "processing_method": "automated_valuation_method",
                "script": "esad_cif"
            },
            {
                "box_field": "val_note",
                "field_name": "Valuation currency",
                "description": "Currency used for customs valuation",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_cif script using currency analysis. No LLM processing required.",
                "processing_method": "automated_currency_analysis",
                "script": "esad_cif"
            },
            {
                "box_field": "val_note",
                "field_name": "Valuation amount",
                "description": "Amount used for customs valuation",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_cif script using valuation calculations. No LLM processing required.",
                "processing_method": "automated_valuation_calculation",
                "script": "esad_cif"
            },
            {
                "box_field": "val_note",
                "field_name": "Valuation exchange rate",
                "description": "Exchange rate used for valuation",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_cif script using exchange rate analysis. No LLM processing required.",
                "processing_method": "automated_exchange_rate",
                "script": "esad_cif"
            },
            {
                "box_field": "val_note",
                "field_name": "Valuation date",
                "description": "Date of valuation",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_cif script using date analysis. No LLM processing required.",
                "processing_method": "automated_date_analysis",
                "script": "esad_cif"
            },
            {
                "box_field": "val_note",
                "field_name": "Valuation notes",
                "description": "Additional notes for valuation",
                "extraction_prompt": "AUTOMATED: This field is automatically populated by the esad_cif script using notes analysis. No LLM processing required.",
                "processing_method": "automated_notes_analysis",
                "script": "esad_cif"
            }
        ]
        
        print(f"\n📋 Testing val_note Fields:")
        print(f"   • Valuation method (esad_cif script)")
        print(f"   • Valuation currency (esad_cif script)")
        print(f"   • Valuation amount (esad_cif script)")
        print(f"   • Valuation exchange rate (esad_cif script)")
        print(f"   • Valuation date (esad_cif script)")
        print(f"   • Valuation notes (esad_cif script)")
        
        # Test each val_note field
        for field_def in val_note_fields:
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
        
        print(f"\n📊 val_note Test Summary:")
        print(f"   • Fields tested: 6")
        print(f"   • Script: esad_cif")
        print(f"   • Processing: Automated valuation analysis")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_val_note_fields()
    if success:
        print(f"\n🎉 val_note test completed successfully!")
    else:
        print(f"\n💥 val_note test failed!")
        sys.exit(1)
