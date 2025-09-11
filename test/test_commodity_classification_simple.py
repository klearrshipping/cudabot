#!/usr/bin/env python3
"""
Simple test script for commodity code classification scenarios.
Tests the fix for partial answers issue with direct HS code testing.
"""

import sys
import os
import json
import requests
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# API Configuration
API_BASE_URL = "http://localhost:5000"  # Adjust if different

def call_classify_api(product_name, contextual_data=None):
    """Call the classify API endpoint."""
    url = f"{API_BASE_URL}/classify"
    
    payload = {
        "product_name": product_name,
        "contextual_data": contextual_data
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)  # Increased timeout
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"   ❌ API Error: {e}")
        return None

def print_separator(title):
    """Print a formatted separator for test sections."""
    print(f"\n{'='*80}")
    print(f"🧪 {title}")
    print(f"{'='*80}")

def print_test_result(test_name, result, expected_behavior):
    """Print formatted test results."""
    print(f"\n📊 {test_name} RESULTS:")
    print(f"   Expected: {expected_behavior}")
    
    if isinstance(result, dict):
        # Handle API response format
        if 'status' in result:
            print(f"   Status: {result.get('status', 'N/A')}")
            print(f"   Product: {result.get('product_name', 'N/A')}")
            print(f"   HS Code: {result.get('hs_code', 'N/A')}")
            print(f"   Commodity Code: {result.get('commodity_code', 'N/A')}")
            print(f"   Description: {result.get('description', 'N/A')}")
            
            if result.get('status') == 'needs_clarification':
                print(f"   ✅ Status: Clarification Required")
                questions = result.get('clarification_questions', [])
                print(f"   📋 Questions: {len(questions)}")
                
                if questions:
                    print(f"   🔍 Questions that need answers:")
                    for i, q in enumerate(questions, 1):
                        print(f"      Q{i}: {q.get('question', 'N/A')}")
                        print(f"         Options: {q.get('options', [])}")
            elif result.get('hs_code') and result.get('commodity_code'):
                print(f"   ✅ Status: Classification Complete")
            else:
                print(f"   ❓ Status: Partial or unclear result")
        else:
            # Handle direct function call format (fallback)
            for hs_code, data in result.items():
                print(f"\n   HS Code: {hs_code}")
                if isinstance(data, dict) and data.get('requires_clarification'):
                    print(f"   ✅ Status: Clarification Required")
                    print(f"   📋 Questions: {len(data.get('questions', []))}")
                    print(f"   💡 Reasoning: {data.get('reasoning', 'N/A')}")
                    print(f"   📝 Missing Info: {data.get('missing_info', [])}")
                    
                    # Show the questions that need answers
                    questions = data.get('questions', [])
                    if questions:
                        print(f"   🔍 Questions that need answers:")
                        for i, q in enumerate(questions, 1):
                            print(f"      Q{i}: {q.get('question', 'N/A')}")
                            print(f"         Options: {q.get('options', [])}")
                elif isinstance(data, list) and data:
                    print(f"   ✅ Status: Classification Complete")
                    print(f"   📦 Selected Code: {data[0].get('tariff_code', 'N/A')}")
                    print(f"   📝 Description: {data[0].get('description', 'N/A')}")
                else:
                    print(f"   ❓ Status: Unexpected result type")
    else:
        print(f"   ❓ Unexpected result: {result}")

def test_case_1_basic_tesla():
    """Test Case 1: Basic Tesla Model 3 classification without context."""
    print_separator("TEST CASE 1: 2024 Tesla Model 3 (Basic)")
    
    # Test data
    product_name = "2024 Tesla Model 3"
    contextual_data = None  # No additional context
    
    print(f"📝 Input:")
    print(f"   Product: {product_name}")
    print(f"   Context: None")
    
    # Test via API
    print(f"\n🔍 Testing via API")
    result = call_classify_api(product_name, contextual_data)
    
    if result:
        print_test_result(
            "Basic Tesla Classification",
            result,
            "Should return clarification request if multiple codes exist, or direct classification if single code"
        )
    else:
        print(f"   ❌ API call failed")
    
    return result

def test_case_2_tesla_with_importer():
    """Test Case 2: Tesla Model 3 with importer context (partial answers)."""
    print_separator("TEST CASE 2: 2024 Tesla Model 3 imported by Rafer Johnson (Partial Context)")
    
    # Test data with importer context
    product_name = "2024 Tesla Model 3 imported by Rafer Johnson"
    
    # Mock contextual data that answers some questions
    contextual_data = {
        'importer_type': 'individual',  # Answers importer type question
        'product_age_category': 'three_years_and_less',  # Answers age question
        # Missing: Vehicle type and propulsion type answers
    }
    
    print(f"📝 Input:")
    print(f"   Product: {product_name}")
    print(f"   Context: {contextual_data}")
    
    # Test via API with partial context
    print(f"\n🔍 Testing via API with Partial Context")
    result = call_classify_api(product_name, contextual_data)
    
    if result:
        print_test_result(
            "Tesla with Partial Context",
            result,
            "Should return clarification request since not ALL questions can be answered from context"
        )
    else:
        print(f"   ❌ API call failed")
    
    return result

def test_case_3_document_based():
    """Test Case 3: Classification using real document data."""
    print_separator("TEST CASE 3: Document-Based Classification")
    
    # Load document data
    bol_path = "customs_api/processed_data/orders/ORD-20250907-006/primary_process/bill_of_lading_ORD-20250907-006_primary_extract.json"
    invoice_path = "customs_api/processed_data/orders/ORD-20250907-006/primary_process/invoice_ORD-20250907-006_primary_extract.json"
    
    try:
        with open(bol_path, 'r') as f:
            bol_data = json.load(f)
        with open(invoice_path, 'r') as f:
            invoice_data = json.load(f)
        
        print(f"📄 Loaded Document Data:")
        print(f"   BOL: {bol_data.get('commodity', 'N/A')}")
        print(f"   Invoice: {invoice_data.get('items', [{}])[0].get('description', 'N/A')}")
        
        # Extract product information
        product_name = "2023 Tesla Model Y based on shipping documents"
        
        # Create comprehensive context from documents
        contextual_data = {
            'importer_type': 'individual',  # Rafer Johnson is individual
            'product_age_category': 'three_years_and_less',  # 2023 model
            'product_specifications': {
                'year_of_manufacture': 2023,
                'battery_type': 'lithium_ion',
                'vehicle_type': 'suv'
            },
            'value_category': 'very_high_value',  # $55,000
            'usage_purpose': 'personal'  # Individual buyer
        }
        
        print(f"📝 Extracted Context:")
        for key, value in contextual_data.items():
            print(f"   {key}: {value}")
        
        # Test via API with full context
        print(f"\n🔍 Testing via API with Full Context")
        result = call_classify_api(product_name, contextual_data)
        
        if result:
            print_test_result(
                "Document-Based Classification",
                result,
                "Should either classify directly or return clarification request depending on available codes"
            )
        else:
            print(f"   ❌ API call failed")
        
        return result
            
    except Exception as e:
        print(f"   ❌ Error loading documents: {e}")
        return None

def main():
    """Run all test cases."""
    print(f"🚀 COMMODITY CLASSIFICATION TEST SUITE")
    print(f"   Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Testing the fix for partial answers issue")
    
    results = {}
    
    # Run all test cases
    try:
        results['test_case_1'] = test_case_1_basic_tesla()
    except Exception as e:
        print(f"❌ Test Case 1 failed: {e}")
        results['test_case_1'] = None
    
    try:
        results['test_case_2'] = test_case_2_tesla_with_importer()
    except Exception as e:
        print(f"❌ Test Case 2 failed: {e}")
        results['test_case_2'] = None
    
    try:
        results['test_case_3'] = test_case_3_document_based()
    except Exception as e:
        print(f"❌ Test Case 3 failed: {e}")
        results['test_case_3'] = None
    
    # Summary
    print_separator("TEST SUMMARY")
    print(f"✅ Test Cases Completed: {len([r for r in results.values() if r is not None])}/3")
    print(f"❌ Test Cases Failed: {len([r for r in results.values() if r is None])}/3")
    
    print(f"\n🎯 Key Validation Points:")
    print(f"   - Partial answers should NOT proceed with classification")
    print(f"   - ALL questions must be answered before classification")
    print(f"   - Clarification requests should identify missing information")
    
    print(f"\n📝 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
