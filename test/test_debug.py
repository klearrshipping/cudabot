#!/usr/bin/env python3
"""
Simple debug test to see Stage 5 output
"""

import requests
import json

# API Configuration
API_BASE_URL = "http://localhost:5000"

def test_debug():
    """Test to see detailed stage output"""
    url = f"{API_BASE_URL}/classify"
    
    payload = {
        "product_name": "2024 Tesla Model 3",
        "contextual_data": None
    }
    
    print("🚀 DEBUGGING STAGE 5 OUTPUT")
    print("=" * 50)
    print(f"📝 Sending request to: {url}")
    print(f"📝 Payload: {json.dumps(payload, indent=2)}")
    print("=" * 50)
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        print("✅ API Response received")
        print(f"📊 Response type: {type(result)}")
        print(f"📊 Response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        # The detailed stage output should be visible in the server logs
        print("\n🔍 Check your server console/logs for the detailed Stage 5 output!")
        print("🔍 Look for: '🔍 DEBUG: contextual_data = ...'")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_debug()
