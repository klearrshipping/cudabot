#!/usr/bin/env python3
"""
Debug test to see what the API is actually receiving and processing
"""

import requests
import json

def test_api_debug():
    """Test the API with debug information"""
    
    # API endpoint
    url = "http://localhost:5000/classify"
    
    # Test with a simple query
    product_data = {
        "product_name": "What is the HS code for fresh apples?",
        "verbose": False
    }
    
    print("Testing API Debug...")
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
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API Response Successful!")
            print(f"Product Name: {result.get('product_name', 'N/A')}")
            print(f"HS Code: {result.get('hs_code', 'N/A')}")
            print(f"Commodity Code: {result.get('commodity_code', 'N/A')}")
        else:
            print(f"❌ API Error!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api_debug()
