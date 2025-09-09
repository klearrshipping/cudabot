#!/usr/bin/env python3
"""
Simple Manifest Lookup Test Script
Tests manifest lookup by extracting BOL number from processed data and submitting to esad_manifest
"""

import json
import os
import sys
from pathlib import Path

# Add the customs_api modules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'customs_api', 'modules'))

def test_manifest_lookup():
    """Test manifest lookup with the actual BOL data"""
    
    print("🧪 Testing Manifest Lookup")
    print("=" * 40)
    
    # Load the specific BOL file
    bol_file = "../customs_api/processed_data/orders/ORD-20250906-003/primary_process/bill_of_lading_ORD-20250906-003_primary_extract.json"
    
    if not os.path.exists(bol_file):
        print(f"❌ BOL file not found: {bol_file}")
        return
    
    print(f"📋 Loading BOL file: {bol_file}")
    
    with open(bol_file, 'r', encoding='utf-8') as f:
        bol_data = json.load(f)
    
    # Extract BOL number
    bol_number = bol_data.get('master_bill_of_lading')
    print(f"🎯 BOL Number: {bol_number}")
    
    if not bol_number:
        print("❌ No BOL number found in master_bill_of_lading field")
        return
    
    # Test manifest lookup
    try:
        from secondary_processing.esad_manifest import ManifestTracker
        
        print(f"\n🔄 Submitting BOL '{bol_number}' to esad_manifest...")
        
        tracker = ManifestTracker()
        result = tracker.track_bol(bol_number)
        
        print(f"\n📊 Results:")
        print(f"   Success: {result.success}")
        print(f"   Total Entries: {result.total_entries}")
        print(f"   Error: {result.error_message}")
        
        if result.entries:
            entry = result.entries[0]
            print(f"\n📋 First Entry:")
            print(f"   Office: {entry.office}")
            print(f"   Reference ID: {entry.reference_id}")
            print(f"   Date: {entry.date}")
            print(f"   Status: {entry.status}")
            
            # Check what data is available for eSAD fields
            if entry.office and entry.reference_id:
                print("\n✅ Both Office Code and Manifest data available!")
            elif entry.office:
                print("\n⚠️ Only Office Code available - Manifest missing")
            elif entry.reference_id:
                print("\n⚠️ Only Manifest available - Office Code missing")
            else:
                print("\n❌ Neither Office Code nor Manifest data available")
        else:
            print("\n❌ No manifest entries found")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_manifest_lookup()