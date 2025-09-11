#!/usr/bin/env python3
"""
Interactive test script that handles user input for unanswered questions
FIXED VERSION - Uses correct endpoints and session management
"""

import requests
import json

def get_user_answers(questions):
    """Get user answers for unanswered questions"""
    user_answers = {}
    
    print("\n" + "="*60)
    print("🔍 USER INPUT REQUIRED")
    print("="*60)
    print("Please answer the following questions:")
    print()
    
    for i, question in enumerate(questions, 1):
        question_text = question.get('question', 'N/A')
        options = question.get('options', [])
        question_id = question.get('id', f'question_{i}')
        
        print(f"Question {i}: {question_text}")
        print("Options:")
        for j, option in enumerate(options, 1):
            value = option.get('value', 'N/A')
            label = option.get('label', value)
            print(f"  {j}. {label}")
        
        while True:
            try:
                choice = input(f"\nEnter your choice (1-{len(options)}): ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(options):
                    selected_option = options[choice_num - 1]
                    user_answers[question_id] = selected_option.get('value')
                    print(f"✅ Selected: {selected_option.get('label')}")
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {len(options)}")
            except ValueError:
                print("❌ Please enter a valid number")
        
        print("-" * 40)
    
    return user_answers

def test_api_with_user_input():
    """Test the API with interactive user input"""
    
    # API endpoints
    classify_url = "http://localhost:5000/classify"
    continue_url = "http://localhost:5000/classify/continue"
    
    # Test with Tesla Model 3 query
    product_data = {
        "product_name": "2024 Tesla Model 3",
        "contextual_data": None
    }
    
    print("🚀 INTERACTIVE API TEST")
    print("="*60)
    print(f"Initial Query: {product_data['product_name']}")
    print(f"Classify URL: {classify_url}")
    print(f"Continue URL: {continue_url}")
    print()
    
    try:
        # Send initial POST request
        print("📤 Sending initial request...")
        response = requests.post(
            classify_url, 
            json=product_data,
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Initial API Response Received!")
            
            # Debug: Print the actual response structure
            print(f"\n🔍 DEBUG: API Response Structure:")
            print(f"   Keys: {list(result.keys())}")
            print(f"   requires_clarification: {result.get('requires_clarification')}")
            print(f"   session_id: {result.get('session_id')}")
            
            # Check if clarification is needed
            if result.get('requires_clarification') and result.get('clarification_questions'):
                
                session_id = result.get('session_id')
                clarification_questions = result.get('clarification_questions')
                
                if not session_id:
                    print("❌ No session_id returned by API")
                    return
                
                print(f"\n📋 Clarification Questions Found: {len(clarification_questions)}")
                print(f"Session ID: {session_id}")
                
                # Get user answers
                user_answers = get_user_answers(clarification_questions)
                
                # Send follow-up request with user answers to CORRECT endpoint
                print(f"\n📤 Sending follow-up request to /classify/continue...")
                continue_data = {
                    "session_id": session_id,
                    "additional_context": user_answers
                }
                
                print(f"Continue Data: {json.dumps(continue_data, indent=2)}")
                
                continue_response = requests.post(
                    continue_url,  # Use correct endpoint
                    json=continue_data,
                    headers={"Content-Type": "application/json"},
                    timeout=120
                )
                
                print(f"Continue Status Code: {continue_response.status_code}")
                
                if continue_response.status_code == 200:
                    final_result = continue_response.json()
                    print("\n🎉 FINAL RESULTS:")
                    print("="*60)
                    print(f"Product Name: {final_result.get('product_name', 'N/A')}")
                    print(f"HS Code: {final_result.get('hs_code', 'N/A')}")
                    print(f"Commodity Code: {final_result.get('commodity_code', 'N/A')}")
                    print(f"Description: {final_result.get('description', 'N/A')}")
                    
                    # Check if still needs clarification
                    if final_result.get('requires_clarification'):
                        print(f"\n⚠️ Still requires clarification:")
                        remaining_questions = final_result.get('clarification_questions', [])
                        print(f"   Remaining questions: {len(remaining_questions)}")
                        for q in remaining_questions:
                            print(f"   - {q.get('question', 'N/A')}")
                else:
                    print(f"❌ Continue API Error ({continue_response.status_code}): {continue_response.text}")
                    
            else:
                print("\n🎉 IMMEDIATE RESULTS (No clarification needed):")
                print("="*60)
                print(f"Product Name: {result.get('product_name', 'N/A')}")
                print(f"HS Code: {result.get('hs_code', 'N/A')}")
                print(f"Commodity Code: {result.get('commodity_code', 'N/A')}")
                print(f"Description: {result.get('description', 'N/A')}")
        else:
            print(f"❌ Initial API Error ({response.status_code}): {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API - make sure server is running")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api_with_user_input()