#!/usr/bin/env python3
"""
Test Script for Box Field 31: Commercial Description
Tests the esad_product.py script for standardizing commercial descriptions
"""

import sys
import os
# Add the project root to the path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'modules', 'secondary_processing'))

from modules.secondary_processing.esad_product import process_commercial_description, clean_commercial_description

if __name__ == "__main__":
    print("🧪 Product Name Test")
    print("=" * 25)
    
    # Ask user to enter product name
    product_name = input("Enter product name: ").strip()
    
    if not product_name:
        print("No product name entered. Exiting.")
        exit()
    
    print(f"\nProcessing: {product_name}")
    print("-" * 30)
    
    # Process through esad_product module
    result = process_commercial_description(product_name, verbose=False, get_hs_code=True)
    
    # Display the result
    print(f"Product Name: {result['product_name']}")
    
    if result['hs_code']:
        print(f"HS Code: {result['hs_code']}")
        print(f"Commodity Code: {result['commodity_code']}")
        print(f"Description: {result['hs_description']}")
    else:
        print("HS Code: Not available (API may be down)")
    
    print("\n✅ Processing completed!")
