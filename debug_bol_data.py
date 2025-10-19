#!/usr/bin/env python3
"""
Debug BOL data structure to see what's being passed to LLM
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
BOL_FILE = r"C:\Users\rafer\OneDrive\Desktop\projects\cuda\customs_api\processed_orders\ORD-20251015-001\bills_of_lading\bill_of_lading_ORD-20251015-001_primary_extract.json"

def debug_bol_data():
    """Debug the BOL data structure."""
    
    with open(BOL_FILE, 'r', encoding='utf-8') as f:
        bol_data = json.load(f)
    
    print("🔍 BOL Data Structure Analysis:")
    print(f"📄 Document type: {bol_data.get('document_type', 'N/A')}")
    
    # Check charges_totals
    charges_totals = bol_data.get('charges_totals', {})
    print(f"\n💰 Charges Totals:")
    for key, value in charges_totals.items():
        print(f"  - {key}: {value}")
    
    # Check individual charges
    charges = bol_data.get('charges', [])
    print(f"\n📋 Individual Charges ({len(charges)} found):")
    for i, charge in enumerate(charges):
        print(f"  {i+1}. {charge.get('charge_type', 'Unknown')}: {charge.get('local_collect_amount', '0')} {charge.get('currency', 'N/A')}")
    
    # Simulate what the CIF module sees
    print(f"\n🧮 BOL Summary (what CIF module sees):")
    bol_summary = {
        "freight_and_charges": bol_data.get("freight_and_charges", ""),
        "charges_table": bol_data.get("charges_table", []),
        "charges": bol_data.get("charges", []),
        "charges_totals": bol_data.get("charges_totals", {}),
        "freight_charge_amount": bol_data.get("freight_charge_amount", ""),
        "cargo_summary_table": bol_data.get("cargo_summary_table", {}),
        "document_type": bol_data.get("document_type", ""),
        "vessel_info": bol_data.get("vessel_info", {})
    }
    
    print(json.dumps(bol_summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_bol_data()
