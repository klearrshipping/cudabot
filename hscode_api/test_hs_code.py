#!/usr/bin/env python3
"""
Test script for HS Code Classification module
"""

from module.hs_code import classify_product

def test_hs_code_classification():
    print("=== HS Code Classification Test ===")
    
    try:
        result = classify_product('iPhone 15')
        print(f"Consensus codes: {result.get('consensus_codes', [])}")
        print(f"Product info: {result.get('product_information', 'N/A')}")
        
        if result.get('consensus_codes'):
            print("✅ Success! HS codes generated")
        else:
            print("❌ Failed! No consensus codes found")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_hs_code_classification() 