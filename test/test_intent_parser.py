#!/usr/bin/env python3
"""
Test script to verify intent parser is working correctly
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'hscode_api'))

from module.intent_parser import parse_user_intent

def test_intent_parser():
    """Test the intent parser with the problematic query"""
    
    test_query = "What is the HS code for 2024 tesla model y imported by an individual?"
    
    print("Testing Intent Parser...")
    print(f"Query: {test_query}")
    print("-" * 50)
    
    result = parse_user_intent(test_query)
    
    print(f"Original Query: {result.original_query}")
    print(f"Product Name: {result.product_name}")
    print(f"Intent: {result.intent.value}")
    print(f"Confidence: {result.confidence}")
    print(f"Keywords: {result.extracted_keywords}")
    
    # Check if the product name is correctly extracted
    expected_product = "tesla model y"
    if result.product_name.lower() == expected_product.lower():
        print(f"✅ SUCCESS: Product name correctly extracted as '{result.product_name}'")
    else:
        print(f"❌ FAILURE: Expected '{expected_product}', got '{result.product_name}'")

if __name__ == "__main__":
    test_intent_parser()
