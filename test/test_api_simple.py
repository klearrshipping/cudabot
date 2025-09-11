#!/usr/bin/env python3
"""
Simple HS Code API test to verify the HS Code classification API is working.
"""

import requests
import json

def test_hscode_api_health():
    """Test if the HS Code API is responding."""
    try:
        response = requests.get("http://localhost:5000/health", timeout=10)
        print(f"HS Code API health check status: {response.status_code}")
        if response.status_code == 200:
            print(f"Health response: {response.json()}")
            return True
        else:
            print(f"Health check failed: {response.text}")
            return False
    except Exception as e:
        print(f"Health check error: {e}")
        return False

def test_hscode_classification():
    """Test HS Code classification."""
    url = "http://localhost:5000/classify"
    payload = {
        "product_name": "2024 Tesla Model Y"
    }
    
    try:
        print("Testing HS Code classification...")
        response = requests.post(url, json=payload, timeout=60)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if clarification is needed
            if result.get('requires_clarification'):
                print(f"Clarification needed for: {result.get('product_name')}")
                print(f"Session ID: {result.get('session_id')}")
                
                # Display clarification questions
                questions = result.get('clarification_questions', [])
                print(f"\nClarification Questions ({len(questions)}):")
                for i, q in enumerate(questions, 1):
                    print(f"  {i}. {q.get('question')}")
                    print(f"     Type: {q.get('type')}")
                    if q.get('options'):
                        print(f"     Options: {q.get('options')}")
                    if q.get('help'):
                        print(f"     Help: {q.get('help')}")
                
                # Test the continue endpoint with answers
                return test_continue_classification(result.get('session_id'), questions)
            else:
                print(f"Success! HS Code Classification Result:")
                print(f"  Product: {result.get('product_name')}")
                print(f"  HS Code: {result.get('hs_code')}")
                print(f"  Commodity Code: {result.get('commodity_code')}")
                print(f"  Description: {result.get('description')}")
                return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Classification error: {e}")
        return False

def test_continue_classification(session_id, questions):
    """Test the continue classification endpoint with answers."""
    url = "http://localhost:5000/classify/continue"
    
    # Build answers based on the questions
    answers = {}
    for q in questions:
        question_text = q.get('question', '')
        if 'importer' in question_text.lower():
            answers['importer_type'] = 'Individual'  # Default to Individual
        elif 'age' in question_text.lower() or 'old' in question_text.lower():
            answers['product_age_category'] = 'three_years_and_less'  # Default to new
        elif 'propulsion' in question_text.lower():
            answers['propulsion_type'] = 'Only electric motor'  # Default for Tesla
    
    payload = {
        "session_id": session_id,
        "additional_context": answers
    }
    
    try:
        print(f"\nContinuing classification with answers:")
        for key, value in answers.items():
            print(f"  {key}: {value}")
        
        response = requests.post(url, json=payload, timeout=60)
        print(f"Continue response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nFinal Classification Result:")
            print(f"  Product: {result.get('product_name')}")
            print(f"  HS Code: {result.get('hs_code')}")
            print(f"  Commodity Code: {result.get('commodity_code')}")
            print(f"  Description: {result.get('description')}")
            return True
        else:
            print(f"Continue error: {response.text}")
            return False
    except Exception as e:
        print(f"Continue classification error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing HS Code API")
    print("=" * 50)
    
    # Test health first
    if test_hscode_api_health():
        print("\n✅ HS Code API is healthy")
        
        # Test HS Code classification
        if test_hscode_classification():
            print("\n✅ HS Code classification is working")
        else:
            print("\n❌ HS Code classification failed")
    else:
        print("\n❌ HS Code API is not responding")
