#!/usr/bin/env python3
"""
Comprehensive test script for commodity code classification scenarios.
Tests the fix for partial answers issue in different contexts.
"""

import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from hscode_api.module.commodity_code import lookup_commodity_code

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
        for hs_code, data in result.items():
            print(f"\n   HS Code: {hs_code}")
            if isinstance(data, dict) and data.get('requires_clarification'):
                print(f"   ✅ Status: Clarification Required")
                print(f"   📋 Questions: {len(data.get('questions', []))}")
                print(f"   💡 Reasoning: {data.get('reasoning', 'N/A')}")
                print(f"   📝 Missing Info: {data.get('missing_info', [])}")
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
    product_info = "Electric vehicle, sedan, lithium-ion battery"
    original_question = "Classify this electric vehicle"
    
    print(f"📝 Input:")
    print(f"   Product: {product_name}")
    print(f"   Info: {product_info}")
    print(f"   Question: {original_question}")
    
    # First get HS code from classification
    print(f"\n🔍 Step 1: Getting HS Code from Classification")
    classification_result = classify_product(product_name)
    print(f"   Classification Result: {classification_result}")
    
    if classification_result and classification_result.get("consensus_codes"):
        hs_codes = classification_result["consensus_codes"]
        product_info = classification_result.get("product_information", product_info)
        print(f"   ✅ HS Codes: {hs_codes}")
        
        # Now test commodity code lookup
        print(f"\n🔍 Step 2: Commodity Code Classification")
        result = lookup_commodity_code(
            hs_codes=hs_codes,
            product_name=product_name,
            product_info_text=product_info,
            original_question=original_question
        )
        
        print_test_result(
            "Basic Tesla Classification",
            result,
            "Should return clarification request if multiple codes exist, or direct classification if single code"
        )
        
        return result
    else:
        print(f"   ❌ Failed to get HS code from intent parser")
        return None

def test_case_2_tesla_with_importer():
    """Test Case 2: Tesla Model 3 with importer context."""
    print_separator("TEST CASE 2: 2024 Tesla Model 3 imported by Rafer Johnson")
    
    # Test data with importer context
    product_name = "2024 Tesla Model 3"
    product_info = "Electric vehicle, sedan, lithium-ion battery, imported by Rafer Johnson"
    original_question = "Classify this electric vehicle imported by Rafer Johnson"
    
    # Mock resolved context that answers some questions
    resolved_context = {
        'importer_type': 'individual',  # Answers importer type question
        'product_age_category': 'three_years_and_less',  # Answers age question
        # Missing: Vehicle type and propulsion type answers
    }
    
    print(f"📝 Input:")
    print(f"   Product: {product_name}")
    print(f"   Info: {product_info}")
    print(f"   Context: {resolved_context}")
    
    # First get HS code
    print(f"\n🔍 Step 1: Getting HS Code from Classification")
    classification_result = classify_product(product_name)
    print(f"   Classification Result: {classification_result}")
    
    if classification_result and classification_result.get("consensus_codes"):
        hs_codes = classification_result["consensus_codes"]
        product_info = classification_result.get("product_information", product_info)
        print(f"   ✅ HS Codes: {hs_codes}")
        
        # Test commodity code lookup with partial context
        print(f"\n🔍 Step 2: Commodity Code Classification with Partial Context")
        result = lookup_commodity_code(
            hs_codes=hs_codes,
            product_name=product_name,
            product_info_text=product_info,
            original_question=original_question,
            resolved_context=resolved_context
        )
        
        print_test_result(
            "Tesla with Partial Context",
            result,
            "Should return clarification request since not ALL questions can be answered from context"
        )
        
        return result
    else:
        print(f"   ❌ Failed to get HS code from intent parser")
        return None

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
        product_name = "2023 Tesla Model Y"
        product_info = f"""
        Vehicle: {bol_data.get('commodity', '')}
        Buyer: {invoice_data.get('buyer', {}).get('name', 'N/A')}
        Supplier: {invoice_data.get('supplier', {}).get('name', 'N/A')}
        Value: ${invoice_data.get('totals', {}).get('total_amount', 'N/A')}
        Weight: {bol_data.get('weight', 'N/A')}
        """
        
        original_question = "Classify this vehicle based on the shipping documents"
        
        # Create comprehensive context from documents
        resolved_context = {
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
        for key, value in resolved_context.items():
            print(f"   {key}: {value}")
        
        # Get HS code
        print(f"\n🔍 Step 1: Getting HS Code from Classification")
        classification_result = classify_product(product_name)
        print(f"   Classification Result: {classification_result}")
        
        if classification_result and classification_result.get("consensus_codes"):
            hs_codes = classification_result["consensus_codes"]
            product_info = classification_result.get("product_information", product_info)
            print(f"   ✅ HS Codes: {hs_codes}")
            
            # Test commodity code lookup with full context
            print(f"\n🔍 Step 2: Commodity Code Classification with Full Context")
            result = lookup_commodity_code(
                hs_codes=hs_codes,
                product_name=product_name,
                product_info_text=product_info,
                original_question=original_question,
                resolved_context=resolved_context
            )
            
            print_test_result(
                "Document-Based Classification",
                result,
                "Should either classify directly or return clarification request depending on available codes"
            )
            
            return result
        else:
            print(f"   ❌ Failed to get HS code from intent parser")
            return None
            
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
