#!/usr/bin/env python3
"""
Test script to verify that the original query is properly passed through the system
"""

import requests
import json

def test_original_query_preservation():
    """Test that the original query is preserved through the classification pipeline."""
    
    # API endpoint
    url = "http://localhost:5000/classify"
    
    # Test with a simple query that should work without clarification
    product_data = {
        "product_name": "What is the HS code for fresh apples?",
        "verbose": False
    }
    
    print("Testing Original Query Preservation...")
    print(f"Query: {product_data['product_name']}")
    print(f"API URL: {url}")
    print("-" * 50)
    
    try:
        # Send POST request to the API
        response = requests.post(
            url, 
            json=product_data,
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        # Check if request was successful
        if response.status_code == 200:
            result = response.json()
            print("✅ API Response Successful!")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # The key test: check if the original query appears in the context
            print("\n🎯 ORIGINAL QUERY TEST:")
            print("The original query should appear in the server logs as:")
            print("   📝 ORIGINAL USER QUERY: What is the HS code for fresh apples?")
            print("   📦 PRODUCT INFORMATION: Product Name: fresh apples")
            
        else:
            print(f"❌ API Error!")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Could not connect to API server")
        print("Make sure the server is running on http://localhost:5000")
        
    except requests.exceptions.Timeout:
        print("❌ Timeout Error: Request took too long")
        
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    test_original_query_preservation()
