#!/usr/bin/env python3
"""
Test CIF module with real BOL and invoice data
"""

import json
import sys
import os

# Add project paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
customs_api_dir = os.path.join(current_dir, 'customs_api')
sys.path.insert(0, customs_api_dir)
sys.path.insert(0, current_dir)

# Data file paths
INVOICE_FILE = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\invoices\invoice_ORD-20251015-001_invoice_1_extract.json"
BOL_FILE = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\bills_of_lading\bill_of_lading_ORD-20251015-001_primary_extract.json"

def test_cif_with_real_data():
    """Test CIF module with real data files."""
    
    try:
        # Load real data
        with open(INVOICE_FILE, 'r', encoding='utf-8') as f:
            invoice_data = json.load(f)
        
        with open(BOL_FILE, 'r', encoding='utf-8') as f:
            bol_data = json.load(f)
        
        print("📁 Real data loaded successfully")
        
        # Show BOL charges for debugging
        print("\n🔍 BOL Charges Analysis:")
        charges = bol_data.get('charges', [])
        print(f"Found {len(charges)} charges in BOL:")
        
        foreign_charges = []
        for charge in charges:
            currency = charge.get('currency', '')
            amount = charge.get('local_collect_amount', '0')
            charge_type = charge.get('charge_type', '')
            
            print(f"  - {charge_type}: {amount} {currency}")
            
            # Track foreign currency charges
            if currency and currency.upper() != 'JMD':
                foreign_charges.append({
                    'type': charge_type,
                    'amount': amount,
                    'currency': currency
                })
        
        print(f"\n💱 Foreign currency charges found: {len(foreign_charges)}")
        for charge in foreign_charges:
            print(f"  - {charge['type']}: {charge['amount']} {charge['currency']}")
        
        # Test CIF extraction
        print("\n🧮 Testing CIF extraction with real data...")
        from customs_api.modules.esad_processor.esad_modules.core.esad_cif import ask_llm_for_cif_components, aggregate_cif_summary
        
        result = ask_llm_for_cif_components(invoice_data, bol_data)
        
        print(f"\n📊 CIF EXTRACTION RESULTS:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Test aggregation summary
        print(f"\n📈 CIF SUMMARY:")
        summary = aggregate_cif_summary(result)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cif_with_real_data()
