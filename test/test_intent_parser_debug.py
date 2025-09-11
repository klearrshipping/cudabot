#!/usr/bin/env python3
"""
Debug script to test intent parser behavior
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'hscode_api'))

from module.intent_parser import parse_user_intent

def test_intent_parsing():
    """Test what the intent parser extracts from different inputs"""
    
    test_cases = [
        "2024 Tesla model y imported by an individual",
        "classify 2024 Tesla Model Y",
        "What is the HS code for 2024 Tesla Model Y?",
        "2024 Tesla Model Y"
    ]
    
    for query in test_cases:
        print(f"\n{'='*60}")
        print(f"INPUT: {query}")
        print(f"{'='*60}")
        
        result = parse_user_intent(query)
        
        print(f"Product Name: '{result.product_name}'")
        print(f"Intent: {result.intent.value}")
        print(f"Confidence: {result.confidence}")
        print(f"Original Query: '{result.original_query}'")
        print(f"Keywords: {result.extracted_keywords}")
        print(f"Context: {result.additional_context}")

if __name__ == "__main__":
    test_intent_parsing()
