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
        
        # Display invoice fields for debugging
        print(f"\n📋 Invoice Data Fields:")
        print(f"   • items: {invoice_data.get('items', [])}")
        print(f"   • totals: {invoice_data.get('totals', {})}")
        print(f"   • shipping: {invoice_data.get('shipping', {})}")
        print(f"   • currency: {invoice_data.get('currency', 'N/A')}")
        
        # Load BOL data
        with open(bol_file, 'r', encoding='utf-8') as f:
            bol_data = json.load(f)
        print(f"✅ Loaded BOL data: {len(bol_data)} fields")
        
        # Display BOL fields for debugging
        print(f"\n📋 BOL Data Fields:")
        print(f"   • freight_and_charges: {bol_data.get('freight_and_charges', 'N/A')}")
        print(f"   • charges_table: {bol_data.get('charges_table', [])}")
        print(f"   • cargo: {bol_data.get('cargo', {})}")
        
        # Import the CIF processor directly
        from modules.esad_processor.esad_modules.esad_cif import CIFProcessor
        
        # Prepare input data for CIF processor
        input_data = {
            'invoice_data': invoice_data,
            'bol_data': bol_data,
            'existing_fields': {}
        }
        
        # Initialize CIF processor
        cif_processor = CIFProcessor()
        
        # Test CIF processor directly
        cif_result = cif_processor.process(input_data)
        
        if cif_result and cif_result.get('success'):
            # Display the model used for extraction
            model_used = cif_result.get('model_used', 'Unknown')
            print(f"\n🤖 LLM Model Used for Extraction: {model_used}")
            
            # Display results in JSON format
            print(f"\n📊 CIF Extraction Results (JSON Format)")
            print("=" * 60)
            
            # Prepare the JSON structure
            extraction_results = {
                "model_used": model_used,
                "invoice_data": {
                    "invoice_total_including_freight": cif_result.get('val_note_invoice_total_including_freight'),
                    "invoice_value_goods_only": cif_result.get('val_note_invoice_value_goods_only'),
                    "freight_charges_invoice": cif_result.get('val_note_freight_charges_invoice'),
                    "other_charges_invoice": cif_result.get('val_note_other_charges_invoice'),
                    "currency": cif_result.get('invoice_currency')
                },
                "bol_data": {
                    "freight_charges_bol_foreign": cif_result.get('val_note_freight_charges_bol'),
                    "insurance_charges_bol_foreign": cif_result.get('val_note_insurance_charges_bol'),
                    "other_charges_bol_foreign": cif_result.get('val_note_other_charges_bol'),
                    "foreign_currency": cif_result.get('bol_foreign_currency')
                },
                "additional_data": {
                    "incoterms": cif_result.get('incoterms')
                },
                "calculated_values": {
                    "insurance_charges_invoice": cif_result.get('val_note_insurance_charges_invoice'),
                    "cost_and_freight": cif_result.get('val_note_cost_and_freight')
                }
            }
            
            # Display JSON with proper formatting
            print(json.dumps(extraction_results, indent=2, ensure_ascii=False))
            print("=" * 60)
            
            # Display calculation details after JSON
            extracted_data = cif_result.get('extracted_data', {})
            
            # Show calculation details
            if extracted_data.get('_insurance_debug') or extracted_data.get('_cf_debug'):
                print(f"\n🔍 CALCULATION DETAILS:")
                if extracted_data.get('_insurance_debug'):
                    print(f"   {extracted_data['_insurance_debug']}")
                if extracted_data.get('_cf_debug'):
                    print(f"   {extracted_data['_cf_debug']}")
        else:
            error_msg = cif_result.get('error', 'Unknown error') if cif_result else 'No result returned'
            print(f"   ⚠️ CIF processing failed: {error_msg}")
        
        print(f"\n📊 val_note Test Summary:")
        print(f"   • Fields tested: CIF Components")
        print(f"   • Script: esad_cif")
        print(f"   • Processing: Direct CIF processor execution")
        
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
