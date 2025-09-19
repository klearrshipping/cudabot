#!/usr/bin/env python3
"""
Test script for eSAD Box 1 field (Regime Type)
"""

import sys
import os
import json
from pathlib import Path

# Add the customs_api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api'))

from modules.esad_processor.process_esad import ESADOrchestrator

def test_box_1_field():
    """Test Box 1 field: Regime Type"""
    
    print("🧪 Testing eSAD Box 1 Field")
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
        
        # Test Box 1 field using the esad_regime script directly
        print(f"\n📋 Testing Box 1 Field:")
        print(f"   • Regime Type (esad_regime script)")
        
        # Import the esad_regime script
        from modules.esad_processor.esad_modules.esad_regime import RegimeTypeProcessor
        
        print(f"\n🔍 Testing: Regime Type")
        print(f"   Script: esad_regime")
        
        # Initialize the regime processor
        regime_processor = RegimeTypeProcessor()
        
        # Test the regime processor directly
        regime_result = regime_processor.process_regime_type(invoice_data, bol_data)
        
        if regime_result and regime_result.regime_type:
            print(f"   ✅ Result: {regime_result.regime_type}")
            print(f"   📋 Description: {regime_result.description}")
            print(f"   🎯 Confidence: {regime_result.confidence}")
        else:
            print(f"   ⚠️ No data returned from esad_regime")
        
        print(f"\n📊 Box 1 Test Summary:")
        print(f"   • Field tested: Regime Type")
        print(f"   • Script: esad_regime")
        print(f"   • Processing: Direct script execution")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_box_1_field()
    if success:
        print(f"\n🎉 Box 1 test completed successfully!")
    else:
        print(f"\n💥 Box 1 test failed!")
        sys.exit(1)
