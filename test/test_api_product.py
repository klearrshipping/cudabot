import requests
import json

def test_product_classification():
    """Test the HS Code API with a Tesla Model Y product."""
    
    # API endpoint
    url = "http://localhost:5000/classify"
    
    # Product data to test (following API documentation)
    product_data = {
        "product_name": "2024 tesla model y imported by an individual",
        "verbose": False
    }
    
    print("Testing HS Code API...")
    print(f"Product: {product_data['product_name']}")
    print(f"API URL: {url}")
    print("-" * 50)
    
    try:
        # Send POST request to the API
        response = requests.post(
            url, 
            json=product_data,
            headers={"Content-Type": "application/json"},
            timeout=120  # Increased timeout to 2 minutes
        )
        
        # Check if request was successful
        if response.status_code == 200:
            result = response.json()
            print("✅ API Response Successful!")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Extract key information
            if 'hs_code' in result:
                print(f"\n🎯 Classified HS Code: {result['hs_code']}")
            if 'confidence' in result:
                print(f"📊 Confidence: {result['confidence']}")
            if 'explanation' in result:
                print(f"💡 Explanation: {result['explanation']}")
                
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
    test_product_classification()
