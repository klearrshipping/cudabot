#!/usr/bin/env python3
"""
Test script for eSAD Box 25 field (Transport mode)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_25_field():
    """Test Box 25 field: Transport mode"""
    
    print("🧪 Testing eSAD Box 25 Field")
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
        
        # Test Box 25 field using the transport mode processor directly
        print(f"\n📋 Testing Box 25 Field:")
        print(f"   • Transport mode (esad_transport_mode script)")

        # Import transport mode processor
        from modules.esad_processor.esad_modules.esad_transport_mode import TransportModeProcessor

        # Determine raw transport context from BOL or invoice
        raw_transport_data = (
            bol_data.get('vessel_name') or
            bol_data.get('voyage_number') or
            bol_data.get('transport_document') or
            invoice_data.get('transport_mode') or
            json.dumps({"bol": bol_data.get('vessel_name') or bol_data.get('carrier', ''), "invoice": invoice_data.get('transport_mode', '')})
        )

        print(f"\n🔍 Testing: Transport mode")
        print(f"   Script: esad_transport_mode")

        processor = TransportModeProcessor()
        result = processor.process_transport_mode(str(raw_transport_data))

        if result and result.get('mode_code'):
            print(f"   ✅ Result: mode_code={result.get('mode_code')} ({result.get('mode')})")
        else:
            print(f"   ⚠️ No transport mode determined")

        print(f"\n📊 Box 25 Test Summary:")
        print(f"   • Field tested: Transport mode")
        print(f"   • Script: esad_transport_mode")
        print(f"   • Processing: Direct script execution")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_25_field()
    if success:
        print(f"\n🎉 Box 25 test completed successfully!")
    else:
        print(f"\n💥 Box 25 test failed!")
        sys.exit(1)
