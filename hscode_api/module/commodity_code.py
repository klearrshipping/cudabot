#!/usr/bin/env python3
"""
Commodity Code Lookup with LLM Selection
----------------------------------------

Look up Jamaican 10-digit tariff codes that start with the supplied 6-digit HS codes,
then use LLM reasoning to select the most appropriate commodity code for the product.
"""

import json
import sys
import logging
import os
import argparse
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

import requests
from supabase import create_client, Client
# Removed circular import - will define reason_with_llm_fn locally

# Add parent directory to Python path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import config from the hscode_api directory
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
hscode_api_dir = os.path.dirname(current_dir)
sys.path.insert(0, hscode_api_dir)

from config import SUPABASE_URL, SUPABASE_KEY, OPENROUTER_API_KEY, OPENROUTER_CONFIG, OPENROUTER_MODELS  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# FLEXIBLE CONTEXT RESOLUTION SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_context(product_name: str, contextual_data: Dict[str, Any] = None, 
                   order_id: str = None, original_query: str = None) -> Dict[str, Any]:
    """
    Flexible context resolution supporting multiple scenarios:
    1. Basic request (no context) - extract from query
    2. Order-based context (order_id lookup) - fetch from database
    3. Direct context (contextual_data provided) - use provided data
    
    Args:
        product_name: Name of the product
        contextual_data: Direct contextual data from request
        order_id: Order ID for database lookup
        original_query: Original user query for context extraction
        
    Returns:
        Resolved context dictionary for classification
    """
    print(f"\n🔍 FLEXIBLE CONTEXT RESOLUTION")
    print("-" * 50)
    print(f"Product: {product_name}")
    print(f"Has contextual_data: {bool(contextual_data)}")
    print(f"Has order_id: {bool(order_id)}")
    print(f"Has original_query: {bool(original_query)}")
    
    context = {}
    
    # Scenario 1: Direct context provided (most rich)
    if contextual_data:
        print("✅ Using direct contextual data")
        context = _process_direct_context(contextual_data)
        
    # Scenario 2: Order-based context lookup (rich)
    elif order_id:
        print(f"✅ Using order-based context for {order_id}")
        order_context = get_order_context_by_id(order_id)
        if order_context:
            context = order_context.get('extracted_context', {})
            # Also include raw document data
            context.update({
                'file_data': order_context.get('file_data', {}),
                'order_number': order_context.get('order_number', ''),
                'order_id': order_id
            })
        else:
            print(f"❌ No order context found, falling back to query-based")
            context = extract_context_from_query(original_query or product_name, product_name, "")
    
    # Scenario 3: Basic request (minimal context)
    else:
        print("✅ Using basic query-based context")
        context = extract_context_from_query(original_query or product_name, product_name, "")
    
    print(f"📊 Resolved context keys: {list(context.keys())}")
    return context

def _process_direct_context(contextual_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process direct contextual data into standardized format for classification.
    
    Args:
        contextual_data: Direct context data from API request
        
    Returns:
        Processed context in standardized format
    """
    print(f"\n🔄 PROCESSING DIRECT CONTEXTUAL DATA")
    print("-" * 50)
    
    processed_context = {}
    
    # Process buyer information
    buyer_info = contextual_data.get('buyer_info', {})
    if buyer_info:
        processed_context['importer_type'] = _determine_importer_type_from_buyer(buyer_info)
        processed_context['usage_purpose'] = _determine_usage_purpose_from_buyer(buyer_info)
        print(f"✅ Processed buyer info: {buyer_info.get('name', 'Unknown')}")
    
    # Process supplier information
    supplier_info = contextual_data.get('supplier_info', {})
    if supplier_info:
        processed_context['supplier_name'] = supplier_info.get('name', '')
        processed_context['supplier_address'] = supplier_info.get('address', '')
        print(f"✅ Processed supplier info: {supplier_info.get('name', 'Unknown')}")
    
    # Process product details
    product_details = contextual_data.get('product_details', {})
    if product_details:
        processed_context['product_specifications'] = _extract_product_specs_from_details(product_details)
        processed_context['value_category'] = _determine_value_category_from_details(product_details)
        processed_context['quantity_category'] = _determine_quantity_category_from_details(product_details)
        print(f"✅ Processed product details: {product_details.get('description', 'Unknown')}")
    
    # Process shipping information
    shipping_info = contextual_data.get('shipping_info', {})
    if shipping_info:
        processed_context['origin_country'] = _extract_origin_country_from_shipping(shipping_info)
        processed_context['size_weight_category'] = _determine_size_weight_from_shipping(shipping_info)
        print(f"✅ Processed shipping info: {shipping_info.get('port_of_origin', 'Unknown')}")
    
    # Process document metadata
    doc_metadata = contextual_data.get('document_metadata', {})
    if doc_metadata:
        processed_context['product_age_category'] = _determine_age_from_metadata(doc_metadata)
        processed_context['extraction_confidence'] = doc_metadata.get('extraction_confidence', 'unknown')
        print(f"✅ Processed document metadata: {doc_metadata.get('invoice_date', 'Unknown date')}")
    
    print(f"📊 Processed context keys: {list(processed_context.keys())}")
    return processed_context

def _determine_importer_type_from_buyer(buyer_info: Dict[str, Any]) -> str:
    """Determine importer type from buyer information."""
    buyer_name = buyer_info.get('name', '').upper()
    
    # Check for commercial indicators
    commercial_patterns = [
        r'(INC|LLC|LTD|CORP|COMPANY|CO\.|ENTERPRISE)',
        r'(IMPORT|EXPORT|TRADING|WHOLESALE|RETAIL)',
    ]
    
    for pattern in commercial_patterns:
        if re.search(pattern, buyer_name):
            return 'dealer'
    
    # Check for individual name patterns
    individual_patterns = [
        r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # First Last
        r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$',  # First M. Last
    ]
    
    for pattern in individual_patterns:
        if re.match(pattern, buyer_name.title()):
            return 'individual'
    
    # Default based on name structure
    if len(buyer_name.split()) == 2 and all(word.isalpha() for word in buyer_name.split()):
        return 'individual'
    
    return 'individual'  # Default assumption

def _determine_usage_purpose_from_buyer(buyer_info: Dict[str, Any]) -> str:
    """Determine usage purpose from buyer information."""
    buyer_address = buyer_info.get('address', '').lower()
    
    # Check for residential vs commercial address patterns
    if any(word in buyer_address for word in ['st', 'street', 'ave', 'avenue', 'rd', 'road']):
        return 'personal'
    
    # Check for commercial indicators
    commercial_indicators = ['business', 'commercial', 'industrial', 'office', 'company']
    if any(indicator in buyer_address for indicator in commercial_indicators):
        return 'commercial'
    
    return 'personal'  # Default assumption

def _extract_product_specs_from_details(product_details: Dict[str, Any]) -> Dict[str, Any]:
    """Extract product specifications from product details."""
    specs = {}
    description = product_details.get('description', '').lower()
    
    # Extract year of manufacture
    year_match = re.search(r'\b(20\d{2})\b', description)
    if year_match:
        specs['year_of_manufacture'] = int(year_match.group(1))
    
    # Extract power specifications
    power_match = re.search(r'(\d+)W', description)
    if power_match:
        specs['power_watts'] = int(power_match.group(1))
    
    # Extract capacity specifications
    capacity_match = re.search(r'(\d+)Wh', description)
    if capacity_match:
        specs['capacity_wh'] = int(capacity_match.group(1))
    
    # Extract battery type
    if 'lithium' in description:
        specs['battery_type'] = 'lithium_ion'
    elif 'lfp' in description:
        specs['battery_type'] = 'LFP'
    
    return specs

def _determine_value_category_from_details(product_details: Dict[str, Any]) -> str:
    """Determine value category from product details."""
    try:
        value = product_details.get('value', 0)
        if value < 500:
            return 'low_value'
        elif value < 2000:
            return 'medium_value'
        elif value < 10000:
            return 'high_value'
        else:
            return 'very_high_value'
    except (ValueError, TypeError):
        return 'unknown_value'

def _determine_quantity_category_from_details(product_details: Dict[str, Any]) -> str:
    """Determine quantity category from product details."""
    try:
        quantity = product_details.get('quantity', 1)
        if quantity == 1:
            return 'single_unit'
        elif quantity <= 5:
            return 'small_quantity'
        elif quantity <= 20:
            return 'medium_quantity'
        else:
            return 'bulk_quantity'
    except (ValueError, TypeError):
        return 'single_unit'

def _extract_origin_country_from_shipping(shipping_info: Dict[str, Any]) -> str:
    """Extract origin country from shipping information."""
    port_of_origin = shipping_info.get('port_of_origin', '')
    if 'UNITED STATES' in port_of_origin or 'USA' in port_of_origin:
        return 'USA'
    elif 'CHINA' in port_of_origin:
        return 'CHINA'
    elif 'GERMANY' in port_of_origin:
        return 'GERMANY'
    elif 'JAPAN' in port_of_origin:
        return 'JAPAN'
    return 'unknown'

def _determine_size_weight_from_shipping(shipping_info: Dict[str, Any]) -> str:
    """Determine size/weight category from shipping information."""
    try:
        weight_str = shipping_info.get('weight', '0 KGS')
        weight_kg = float(re.findall(r'[\d.]+', weight_str)[0])
        
        if weight_kg < 10:
            return 'lightweight'
        elif weight_kg < 50:
            return 'medium_weight'
        elif weight_kg < 200:
            return 'heavy'
        else:
            return 'very_heavy'
    except (ValueError, IndexError):
        return 'unknown_weight'

def _determine_age_from_metadata(doc_metadata: Dict[str, Any]) -> str:
    """Determine product age from document metadata."""
    try:
        from datetime import datetime
        current_date = datetime.now()
        
        # Try to extract date from various fields
        date_str = doc_metadata.get('invoice_date') or doc_metadata.get('date')
        if date_str:
            # Parse various date formats
            for fmt in ['%Y-%m-%d', '%B %d, %Y', '%m/%d/%Y']:
                try:
                    doc_date = datetime.strptime(date_str, fmt)
                    age_years = (current_date - doc_date).days / 365.25
                    
                    if age_years <= 3:
                        return 'three_years_and_less'
                    else:
                        return 'exceeding_three_years'
                except ValueError:
                    continue
        
        return 'three_years_and_less'  # Default for new purchases
    except Exception:
        return 'three_years_and_less'

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINTS (Called by app.py or external systems)
# ═══════════════════════════════════════════════════════════════════════════════

def interactive_commodity_lookup(hs_codes: list[str], product_name: str, product_info_text: str, 
                               original_question: str = "", order_id: str = None) -> dict:
    """
    Interactive version for terminal testing - handles the full question/answer cycle.
    
    Args:
        hs_codes: List of HS codes
        product_name: Name of the product  
        product_info_text: Additional product information
        original_question: The original user question
        order_id: Order ID for context-aware auto-answers
        
    Returns:
        Final commodity code selection
    """
    
    # Use enhanced lookup with context auto-answers if order_id provided
    if order_id:
        print(f"\n🤖 USING ENHANCED LOOKUP WITH CONTEXT AUTO-ANSWERS")
        print(f"Order ID: {order_id}")
        return lookup_commodity_code_with_context_auto_answers(
            hs_codes, product_name, product_info_text, original_question, int(order_id)
        )
    
    # Fallback to manual interactive mode
    # Initial lookup
    result = lookup_commodity_code(hs_codes, product_name, product_info_text, original_question)
    
    # Check if any HS code requires clarification
    for hs_code, data in result.items():
        if isinstance(data, dict) and data.get('requires_clarification'):
            print(f"\n" + "="*60)
            print(f"CLARIFICATION NEEDED FOR {hs_code}")
            print("="*60)
            
            questions = data.get('questions', [])
            user_answers = {}
            
            for question in questions:
                print(f"\n📝 {question['question']}")
                if 'help_text' in question:
                    print(f"   ℹ️  {question['help_text']}")
                
                if question['type'] == 'choice' and 'options' in question:
                    print("\nOptions:")
                    for i, option in enumerate(question['options'], 1):
                        print(f"   {i}. {option['label']}")
                    
                    while True:
                        try:
                            choice = input(f"\nSelect option (1-{len(question['options'])}): ").strip()
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(question['options']):
                                user_answers[question['id']] = question['options'][choice_idx]['value']
                                break
                            else:
                                print("Invalid choice. Please try again.")
                        except ValueError:
                            print("Please enter a number.")
                
                elif question['type'] == 'number':
                    while True:
                        try:
                            value = input(f"\nEnter {question.get('unit', 'value')}: ").strip()
                            # Basic validation if provided
                            if 'validation' in question:
                                val_num = float(value)
                                min_val = question['validation'].get('min', 0)
                                max_val = question['validation'].get('max', 999999)
                                if min_val <= val_num <= max_val:
                                    user_answers[question['id']] = value
                                    break
                                else:
                                    print(f"Value must be between {min_val} and {max_val}")
                            else:
                                user_answers[question['id']] = value
                                break
                        except ValueError:
                            print("Please enter a valid number.")
                
                else:  # text type
                    answer = input(f"\nYour answer: ").strip()
                    user_answers[question['id']] = answer
            
            print(f"\n" + "="*60)
            print("PROCESSING YOUR ANSWERS...")
            print("="*60)
            
            # Re-run lookup with answers
            final_result = lookup_commodity_code_with_answers(
                hs_codes, product_name, product_info_text, original_question, user_answers
            )
            
            return final_result
    
    # No clarification needed
    return result

def lookup_commodity_code_with_answers(hs_codes: list[str], product_name: str, product_info_text: str, 
                                      original_question: str, user_answers: dict, order_id: str = None) -> dict:
    """
    Process commodity code lookup with user-provided answers to clarification questions.
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=True)
    results = {}
    
    print(f"\n📝 PROCESSING USER ANSWERS")
    print("-" * 50)
    
    for hs_code in hs_codes:
        # Get all matching codes first
        clean_hs_code = hs_code.replace(".", "")
        try:
            response = (
                lookup.supabase.table("tariff_codes")
                .select("tariff_code,description")
                .ilike("tariff_code", f"{clean_hs_code}%")
                .execute()
            )
            all_matches = response.data or []
            
            if not all_matches:
                results[hs_code] = None
                continue
            
            print(f"\n├── {hs_code}: Found {len(all_matches)} codes")
            
            # Build enhanced product info with user answers
            enhanced_product_info = product_info_text
            if user_answers:
                answer_text = [f"{key}: {value}" for key, value in user_answers.items()]
                enhanced_product_info = f"{product_info_text}\n\nAdditional Information:\n" + "\n".join(answer_text)
            
            # Run LLM analysis with enhanced product information
            print(f"│   └── [LLM] Running LLM analysis with user answers...")
            
            # Extract classification attributes needed
            classification_attributes = lookup.extract_classification_attributes(all_matches)
            
            if not classification_attributes:
                # No distinguishing attributes - can select directly
                best_match = lookup.select_best_commodity_code(
                    hs_code, all_matches, product_name, enhanced_product_info, {}
                )
                if best_match:
                    results[hs_code] = [best_match]
                else:
                    results[hs_code] = []
            else:
                # Still need more clarification
                questions = lookup.generate_questions_for_attributes(classification_attributes)
                
                results[hs_code] = {
                    'requires_clarification': True,
                    'reasoning': 'Classification attributes found',
                    'missing_info': [q['question'] for q in questions],
                    'questions': questions,
                    'available_codes': all_matches,
                    'original_question': original_question,
                    'code_count': len(all_matches)
                }
                
        except Exception as e:
            logger.error(f"Error processing {hs_code}: {str(e)}")
            results[hs_code] = []
    
    return results

def lookup_commodity_code(hs_codes: list[str], product_name: str, product_info_text: str, 
                         original_question: str = "", order_id: str = None, 
                         resolved_context: Dict[str, Any] = None) -> dict:
    """
    Main function called by app.py to lookup commodity codes with LLM selection.
    
    Args:
        hs_codes: List of HS codes (may have dots like ["0706.10"])
        product_name: Name of the product
        product_info_text: Additional product information
        original_question: The original user question for context
        order_id: Order ID for context lookup
        resolved_context: Pre-resolved context data
        
    Returns:
        Dictionary mapping HS codes to their selected best commodity code or clarification request
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=True)
    results = {}
    
    print(f"\n📋 ANALYZING COMMODITY CODES WITH LLM")
    print("-" * 50)
    
    for hs_code in hs_codes:
        # Find all matches
        clean_hs_code = hs_code.replace(".", "")
        try:
            response = (
                lookup.supabase.table("tariff_codes")
                .select("tariff_code,description")
                .ilike("tariff_code", f"{clean_hs_code}%")
                .execute()
            )
            all_matches = response.data or []
            
            if not all_matches:
                print(f"├── {hs_code}: [X] No commodity codes found")
                results[hs_code] = None
                continue
            
            print(f"├── {hs_code}: Found {len(all_matches)} commodity codes, analyzing with LLM...")
            
            # Print found commodity codes for debugging
            print(f"\n📋 Found {len(all_matches)} commodity codes:")
            for match in all_matches:
                print(f"   • {match['tariff_code']}: {match['description']}")
            
            # STEP 1: Extract classification attributes needed
            print(f"\n[ANALYZING] CLASSIFICATION ATTRIBUTES")
            print("-" * 50)
            
            classification_attributes = lookup.extract_classification_attributes(all_matches)
            
            print(f"Found {len(classification_attributes)} classification attribute(s)")
            
            if not classification_attributes:
                print(f"[OK] No distinguishing attributes - can select directly")
                
                # Use LLM to select best match
                best_match = lookup.select_best_commodity_code(
                    hs_code, all_matches, product_name, product_info_text, {}
                )
                
                if best_match:
                    confidence_emoji = {
                        'llm_selected': '[LLM]',
                        'single_match': '[OK]'
                    }.get(best_match.get('selection_method', 'unknown'), '[LLM]')
                    
                    print(f"│   └── Selected: {best_match['tariff_code']} {confidence_emoji}")
                    print(f"│       └── {best_match['description']}")
                    print(f"│       └── Reasoning: {best_match.get('reasoning', 'No reasoning')}")
                    
                    results[hs_code] = [best_match]  # Return as list for consistency
                else:
                    print(f"│   └── [X] LLM rejected all commodity codes as inappropriate")
                    results[hs_code] = []
            else:
                print(f"[X] Classification attributes found - clarification needed")
                print(f"Required attributes: {[attr['name'] for attr in classification_attributes]}")
                
                # Generate specific questions for the required attributes
                print(f"\n[LLM] GENERATING CLARIFICATION QUESTIONS")
                print("-" * 50)
                
                questions = lookup.generate_questions_for_attributes(classification_attributes)
                
                print(f"Generated {len(questions)} questions:")
                for i, q in enumerate(questions, 1):
                    print(f"{i}. {q['question']} ({q['type']})")
                    if 'help_text' in q:
                        print(f"   Help: {q['help_text']}")
                
                # Display comprehensive context after questions are generated
                print(f"\n[CONTEXT] AVAILABLE CONTEXT INFORMATION")
                print("-" * 50)
                
                # Context Source 1: Original Query
                if original_question:
                    print(f"📝 ORIGINAL USER QUERY:")
                    print(f"   {original_question}")
                else:
                    print(f"📝 ORIGINAL USER QUERY: Not provided")
                
                # Context Source 2: Product Information
                print(f"\n📦 PRODUCT INFORMATION:")
                print(f"   Product Name: {product_name}")
                print(f"   Product Details: {product_info_text}")
                
                # Context Source 3: Order Context (if available)
                if order_id:
                    print(f"\n📋 ORDER CONTEXT (Order ID: {order_id}):")
                    order_context = get_order_context_by_id(order_id)
                    
                    if order_context:
                        print(f"   Order Number: {order_context.get('order_number', 'N/A')}")
                        
                        # Display extracted context from DocumentContextExtractor
                        extracted_context = order_context.get('extracted_context', {})
                        if extracted_context:
                            print(f"   📊 EXTRACTED CONTEXT:")
                            for key, value in extracted_context.items():
                                print(f"      - {key}: {value}")
                        else:
                            print(f"   📊 EXTRACTED CONTEXT: Not available")
                        
                        # Display raw document data
                        file_data = order_context.get('file_data', {})
                        if file_data.get('bill_of_lading'):
                            print(f"   📄 BILL OF LADING DATA:")
                            bol_data = file_data['bill_of_lading']
                            print(f"      - Consignee: {bol_data.get('consignee_name', 'N/A')}")
                            print(f"      - Shipper: {bol_data.get('shipper', 'N/A')}")
                            print(f"      - Commodity: {bol_data.get('commodity', 'N/A')}")
                            print(f"      - Weight: {bol_data.get('weight', 'N/A')}")
                            print(f"      - Package Type: {bol_data.get('package_type', 'N/A')}")
                        
                        if file_data.get('invoice'):
                            print(f"   📄 INVOICE DATA:")
                            invoice_data = file_data['invoice']
                            print(f"      - Buyer: {invoice_data.get('buyer', {}).get('name', 'N/A')}")
                            print(f"      - Supplier: {invoice_data.get('supplier', {}).get('name', 'N/A')}")
                            print(f"      - Invoice Date: {invoice_data.get('invoice_details', {}).get('date', 'N/A')}")
                            print(f"      - Total Amount: ${invoice_data.get('totals', {}).get('total_amount', 'N/A')}")
                            
                            # Show items
                            items = invoice_data.get('items', [])
                            if items:
                                print(f"      - Items:")
                                for item in items:
                                    print(f"        * {item.get('description', 'N/A')} - Qty: {item.get('quantity', 'N/A')}")
                    else:
                        print(f"   Order context not available for order ID: {order_id}")
                else:
                    print(f"\n📋 ORDER CONTEXT: Not provided (no order_id)")
                
                print(f"\n[CONTEXT] END OF CONTEXT INFORMATION")
                print("-" * 50)
                
                # UNIFIED APPROACH: Try to auto-answer questions using available context
                print(f"\n🤖 ATTEMPTING AUTO-ANSWER USING AVAILABLE CONTEXT")
                print("-" * 50)
                
                # Use resolved context if available, otherwise extract from sources
                if resolved_context:
                    print(f"✅ Using pre-resolved context: {len(resolved_context)} fields")
                    extracted_context = resolved_context
                elif order_id:
                    # Scenario 2: Order-based context
                    print(f"📋 Using order-based context (Order ID: {order_id})")
                    order_context = get_order_context_by_id(order_id)
                    if order_context:
                        extracted_context = order_context.get('extracted_context', {})
                        print(f"✅ Retrieved order context: {len(extracted_context)} fields")
                    else:
                        print(f"❌ No order context found for order ID: {order_id}")
                else:
                    # Scenario 1: Query-based context
                    print(f"📝 Using query-based context extraction")
                    extracted_context = extract_context_from_query(original_question, product_name, product_info_text)
                    print(f"✅ Extracted query context: {len(extracted_context)} fields")
                
                # Try to map context to answers
                if extracted_context:
                    print(f"\n🎯 MAPPING CONTEXT TO ANSWERS")
                    print("-" * 50)
                    
                    # Map context to answers using simplified logic
                    answers = {}
                    for i, question in enumerate(questions, 1):
                        question_text = question.get('question', '')
                        question_options = question.get('options', [])
                        question_id = f'question_{i}'
                        
                        print(f"\nQ{i}: {question_text}")
                        print(f"   Options: {question_options}")
                        
                        answer = None
                        
                        # Map based on question content
                        if "importer" in question_text.lower():
                            importer_type = extracted_context.get('importer_type', '')
                            if importer_type == 'individual':
                                answer = 'Individual'
                            elif importer_type == 'dealer':
                                answer = 'Dealer'
                            print(f"   Context: importer_type = {importer_type}")
                        
                        elif "age" in question_text.lower() or "old" in question_text.lower():
                            age_category = extracted_context.get('product_age_category', '')
                            if age_category == 'three_years_and_less':
                                answer = 'Three years or less since manufacture'
                            elif age_category == 'exceeding_three_years':
                                answer = 'Exceeding three years since manufacture'
                            print(f"   Context: product_age_category = {age_category}")
                        
                        elif "propulsion" in question_text.lower() or "motor" in question_text.lower():
                            product_specs = extracted_context.get('product_specifications', {})
                            if product_specs.get('battery_type'):
                                answer = 'Only electric motor'
                            print(f"   Context: product_specifications = {product_specs}")
                        
                        # Check if answer matches available options
                        if answer and answer in question_options:
                            answers[question_id] = answer
                            print(f"   ✅ Mapped to: {answer}")
                        elif answer:
                            # Try to find partial match
                            for option in question_options:
                                if answer.lower() in option.lower() or option.lower() in answer.lower():
                                    answers[question_id] = option
                                    print(f"   ✅ Partial match: {option}")
                                    break
                            else:
                                print(f"   ❌ No match found for: {answer}")
                        else:
                            print(f"   ❌ No context mapping available")
                    
                    if len(answers) == len(questions):
                        print(f"\n✅ Successfully mapped ALL {len(answers)}/{len(questions)} questions")
                        
                        # Use answers to select best commodity code
                        print(f"\n🔍 SELECTING BEST COMMODITY CODE WITH ANSWERS")
                        print("-" * 50)
                        
                        # Filter codes based on answers (single pass)
                        filtered_codes = all_matches.copy()
                        
                        # Extract filter criteria from answers
                        importer_filter = None
                        age_filter = None
                        
                        for q_id, answer in answers.items():
                            question = questions[int(q_id.split('_')[1])-1]
                            question_text = question['question'].lower()
                            
                            if "importer" in question_text:
                                if answer == 'Individual':
                                    importer_filter = 'individual'
                                elif answer == 'Dealer':
                                    importer_filter = 'dealer'
                            elif "age" in question_text or "old" in question_text:
                                if 'three years and less' in answer.lower():
                                    age_filter = 'three years and less'
                                elif 'exceeding three years' in answer.lower():
                                    age_filter = 'exceeding three years'
                        
                        # Apply all filters in one pass
                        if importer_filter or age_filter:
                            filtered_codes = [
                                code for code in filtered_codes
                                if (not importer_filter or importer_filter in code['description'].lower()) and
                                   (not age_filter or age_filter in code['description'].lower())
                            ]
                        
                        print(f"📊 Filtered to {len(filtered_codes)} codes based on answers")
                        
                        if filtered_codes:
                            print(f"📋 Filtered codes:")
                            for i, code in enumerate(filtered_codes, 1):
                                print(f"   {i}. {code['tariff_code']}: {code['description']}")
                            
                            # If only one code left, select it directly
                            if len(filtered_codes) == 1:
                                best_match = filtered_codes[0]
                                print(f"✅ Only one code remaining - selecting directly: {best_match['tariff_code']}")
                                results[hs_code] = [best_match]
                                continue
                            
                            # Use LLM to select best match from filtered codes
                            best_match = lookup.select_best_commodity_code(
                                hs_code, filtered_codes, product_name, product_info_text, extracted_context
                            )
                            
                            if best_match:
                                print(f"✅ Selected: {best_match['tariff_code']}")
                                print(f"   Description: {best_match['description']}")
                                results[hs_code] = [best_match]
                                continue
                            else:
                                print(f"❌ LLM rejected all filtered codes")
                        else:
                            print(f"❌ No codes match the filtered criteria")
                    elif answers:
                        print(f"\n⚠️ PARTIAL ANSWERS: Only {len(answers)}/{len(questions)} questions answered")
                        print("❌ ALL questions must be answered to proceed with classification")
                        
                        # Identify unanswered questions
                        unanswered_questions = []
                        for i, question in enumerate(questions, 1):
                            question_id = f'question_{i}'
                            if question_id not in answers:
                                unanswered_questions.append(question['question'])
                        
                        print(f"❌ Missing answers for: {unanswered_questions}")
                    else:
                        print(f"❌ Could not map context to any answers")
                else:
                    print(f"❌ No context available for auto-answering")
                
                # Fallback: Return clarification request if auto-answering failed
                print(f"\n⚠️ FALLBACK: Returning clarification request")
                print("-" * 50)
                results[hs_code] = {
                    'requires_clarification': True,
                    'reasoning': 'Classification attributes found - auto-answering failed',
                    'missing_info': [q['question'] for q in questions],
                    'questions': questions,
                    'available_codes': all_matches,
                    'original_question': original_question,
                    'code_count': len(all_matches)
                }
                
        except Exception as e:
            logger.error(f"Error processing {hs_code}: {str(e)}")
            results[hs_code] = []
    
    # Debug: Print what we're returning
    print(f"\n[DEBUG] Returning results:")
    for hs_code, result in results.items():
        if isinstance(result, dict) and result.get('requires_clarification'):
            print(f"   {hs_code}: Clarification needed ({result.get('code_count', 0)} codes available)")
        elif isinstance(result, list):
            print(f"   {hs_code}: {len(result)} selected codes")
        else:
            print(f"   {hs_code}: {result}")
    
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT CONTEXT EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentContextExtractor:
    """Extract tariff classification context from bill of lading and invoice documents."""
    
    def __init__(self):
        # Common patterns for identifying individual vs commercial importers
        self.individual_patterns = [
            r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # First Last
            r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$',  # First M. Last
        ]
        
        self.commercial_patterns = [
            r'(INC|LLC|LTD|CORP|COMPANY|CO\.|ENTERPRISE)',
            r'(IMPORT|EXPORT|TRADING|WHOLESALE|RETAIL)',
        ]
        
        # Usage context indicators
        self.personal_use_indicators = [
            'personal', 'home', 'family', 'camping', 'rv', 'recreational',
            'hobby', 'private', 'residential'
        ]
        
        self.commercial_use_indicators = [
            'business', 'commercial', 'industrial', 'office', 'company',
            'resale', 'wholesale', 'retail', 'professional'
        ]
    
    def extract_context_from_documents(self, bill_of_lading: Dict, invoice: Dict) -> Dict[str, Any]:
        """
        Extract comprehensive context from bill of lading and invoice documents.
        
        Args:
            bill_of_lading: Parsed bill of lading JSON
            invoice: Parsed invoice JSON
            
        Returns:
            Dictionary of extracted contextual attributes
        """
        context = {}
        
        # Extract importer type
        context['importer_type'] = self._determine_importer_type(bill_of_lading, invoice)
        
        # Extract product age/manufacture date context
        context['product_age_category'] = self._determine_product_age(bill_of_lading, invoice)
        
        # Extract usage purpose
        context['usage_purpose'] = self._determine_usage_purpose(invoice)
        
        # Extract value/price category
        context['value_category'] = self._determine_value_category(invoice)
        
        # Extract quantity context
        context['quantity_category'] = self._determine_quantity_category(invoice)
        
        # Extract weight/size context  
        context['size_weight_category'] = self._determine_size_weight_category(bill_of_lading)
        
        # Extract country of origin
        context['origin_country'] = self._extract_origin_country(bill_of_lading)
        
        # Extract detailed product information
        context['product_specifications'] = self._extract_product_specs(invoice)
        
        return context
    
    def _determine_importer_type(self, bill_of_lading: Dict, invoice: Dict) -> str:
        """Determine if importer is individual, dealer, or company."""
        # Check consignee from bill of lading
        consignee = bill_of_lading.get('consignee_name', '').upper()
        
        # Check for commercial indicators
        for pattern in self.commercial_patterns:
            if re.search(pattern, consignee):
                return 'dealer'
        
        # Check invoice buyer
        buyer_name = invoice.get('buyer', {}).get('name', '').upper()
        for pattern in self.commercial_patterns:
            if re.search(pattern, buyer_name):
                return 'dealer'
        
        # Check if it matches individual name patterns
        for pattern in self.individual_patterns:
            if re.match(pattern, consignee.title()) or re.match(pattern, buyer_name.title()):
                return 'individual'
        
        # Default based on name structure
        if len(consignee.split()) == 2 and all(word.isalpha() for word in consignee.split()):
            return 'individual'
        
        return 'individual'  # Default assumption
    
    def _determine_product_age(self, bill_of_lading: Dict, invoice: Dict) -> str:
        """Determine product age category based on dates."""
        try:
            # Get current date
            current_date = datetime.now()
            
            # Try to extract manufacture/purchase date from invoice
            invoice_date_str = invoice.get('invoice_details', {}).get('date')
            if invoice_date_str:
                invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d')
                age_years = (current_date - invoice_date).days / 365.25
                
                if age_years <= 3:
                    return 'three_years_and_less'
                else:
                    return 'exceeding_three_years'
            
            # Fallback: check for age indicators in product description
            product_desc = invoice.get('items', [{}])[0].get('description', '').lower()
            if 'new' in product_desc or '2024' in product_desc or '2025' in product_desc:
                return 'three_years_and_less'
            
        except (ValueError, KeyError):
            pass
        
        return 'three_years_and_less'  # Default for new purchases
    
    def _determine_usage_purpose(self, invoice: Dict) -> str:
        """Determine intended usage purpose."""
        # Check product description for usage indicators
        product_desc = invoice.get('items', [{}])[0].get('description', '').lower()
        
        # Check for personal use indicators
        for indicator in self.personal_use_indicators:
            if indicator in product_desc:
                return 'personal'
        
        # Check buyer address for residential vs commercial
        buyer_address = invoice.get('buyer', {}).get('address', '').lower()
        if any(word in buyer_address for word in ['st', 'street', 'ave', 'avenue', 'rd', 'road']):
            # Likely residential address
            return 'personal'
        
        # Check for commercial indicators
        for indicator in self.commercial_use_indicators:
            if indicator in product_desc:
                return 'commercial'
        
        return 'personal'  # Default assumption for individual buyers
    
    def _determine_value_category(self, invoice: Dict) -> str:
        """Categorize product by value ranges."""
        try:
            total_value = invoice.get('totals', {}).get('total_amount', 0)
            
            if total_value < 500:
                return 'low_value'
            elif total_value < 2000:
                return 'medium_value'
            elif total_value < 10000:
                return 'high_value'
            else:
                return 'very_high_value'
        except (ValueError, TypeError):
            return 'unknown_value'
    
    def _determine_quantity_category(self, invoice: Dict) -> str:
        """Categorize by quantity (single vs bulk)."""
        try:
            quantity = invoice.get('items', [{}])[0].get('quantity', 1)
            
            if quantity == 1:
                return 'single_unit'
            elif quantity <= 5:
                return 'small_quantity'
            elif quantity <= 20:
                return 'medium_quantity'
            else:
                return 'bulk_quantity'
        except (ValueError, TypeError):
            return 'single_unit'
    
    def _determine_size_weight_category(self, bill_of_lading: Dict) -> str:
        """Categorize by physical dimensions/weight."""
        try:
            weight_str = bill_of_lading.get('weight', '0 KGM')
            weight_kg = float(re.findall(r'[\d.]+', weight_str)[0])
            
            if weight_kg < 10:
                return 'lightweight'
            elif weight_kg < 50:
                return 'medium_weight'
            elif weight_kg < 200:
                return 'heavy'
            else:
                return 'very_heavy'
        except (ValueError, IndexError):
            return 'unknown_weight'
    
    def _extract_origin_country(self, bill_of_lading: Dict) -> str:
        """Extract country of origin."""
        port_of_origin = bill_of_lading.get('port_of_origin', '')
        if 'UNITED STATES' in port_of_origin:
            return 'USA'
        elif 'CHINA' in port_of_origin:
            return 'CHINA'
        # Add more countries as needed
        return 'unknown'
    
    def _extract_product_specs(self, invoice: Dict) -> Dict[str, Any]:
        """Extract detailed product specifications."""
        specs = {}
        
        product_desc = invoice.get('items', [{}])[0].get('description', '')
        
        # Extract power specifications
        power_match = re.search(r'(\d+)W', product_desc)
        if power_match:
            specs['power_watts'] = int(power_match.group(1))
        
        # Extract capacity specifications  
        capacity_match = re.search(r'(\d+)Wh', product_desc)
        if capacity_match:
            specs['capacity_wh'] = int(capacity_match.group(1))
        
        # Extract voltage specifications
        voltage_match = re.search(r'(\d+)V', product_desc)
        if voltage_match:
            specs['voltage'] = int(voltage_match.group(1))
        
        # Extract solar panel info
        if 'solar' in product_desc.lower():
            specs['has_solar_panels'] = True
            panel_match = re.search(r'(\d+)X(\d+)W', product_desc)
            if panel_match:
                specs['solar_panel_count'] = int(panel_match.group(1))
                specs['solar_panel_watts'] = int(panel_match.group(2))
        
        # Extract battery type
        if 'LFP' in product_desc:
            specs['battery_type'] = 'LFP'  # Lithium Iron Phosphate
        elif 'lithium' in product_desc.lower():
            specs['battery_type'] = 'lithium'
        
        return specs

def get_order_context_by_id(order_id: int) -> Dict[str, Any]:
    """
    Retrieve order context (BOL and invoice data) by order ID and extract structured context.
    
    Args:
        order_id: Order ID to retrieve context for
        
    Returns:
        Dictionary containing order context data with extracted structured context
    """
    try:
        # Import here to avoid circular imports
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up from hscode_api/module to hscode_api, then to root, then to customs_api
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        customs_api_dir = os.path.join(root_dir, "customs_api")
        sys.path.insert(0, customs_api_dir)
        
        from modules.core.supabase_client import get_order_extractions
        
        # Get order extractions from database
        order_data = get_order_extractions(order_id)
        if not order_data:
            print(f"❌ No order data found for order ID: {order_id}")
            return {}
        
        # Also try to get processed data from files
        order_number = order_data['order']['order_number']
        processed_data_dir = Path(customs_api_dir) / "processed_data" / "orders" / order_number / "primary_process"
        
        context = {
            'order_id': order_id,
            'order_number': order_number,
            'database_data': order_data,
            'file_data': {},
            'extracted_context': {}
        }
        
        # Try to load processed files
        bol_file = processed_data_dir / f"bill_of_lading_{order_number}_primary_extract.json"
        invoice_file = processed_data_dir / f"invoice_{order_number}_primary_extract.json"
        
        bol_data = None
        invoice_data = None
        
        if bol_file.exists():
            with open(bol_file, 'r', encoding='utf-8') as f:
                bol_data = json.load(f)
                context['file_data']['bill_of_lading'] = bol_data
        
        if invoice_file.exists():
            with open(invoice_file, 'r', encoding='utf-8') as f:
                invoice_data = json.load(f)
                context['file_data']['invoice'] = invoice_data
        
        # Use existing DocumentContextExtractor to extract structured context
        if bol_data and invoice_data:
            print(f"📋 Extracting structured context using DocumentContextExtractor...")
            extractor = DocumentContextExtractor()
            extracted_context = extractor.extract_context_from_documents(bol_data, invoice_data)
            context['extracted_context'] = extracted_context
            
            print(f"✅ Extracted context attributes:")
            for key, value in extracted_context.items():
                print(f"   - {key}: {value}")
        else:
            print(f"⚠️  Missing document data - cannot extract structured context")
            if not bol_data:
                print(f"   - Bill of lading file not found: {bol_file}")
            if not invoice_data:
                print(f"   - Invoice file not found: {invoice_file}")
        
        return context
        
    except Exception as e:
        print(f"❌ Error getting order context for {order_id}: {e}")
        return {}

def extract_context_from_query(original_question: str, product_name: str, product_info_text: str) -> Dict[str, Any]:
    """
    Extract context information from user query and product information for auto-answering clarification questions.
    
    Args:
        original_question: The original user question
        product_name: Name of the product
        product_info_text: Additional product information
        
    Returns:
        Dictionary with extracted context information
    """
    context = {}
    
    print(f"\n🔍 EXTRACTING CONTEXT FROM QUERY AND PRODUCT INFO")
    print("-" * 50)
    
    # Extract importer type from query
    query_lower = original_question.lower()
    if "individual" in query_lower or "personal" in query_lower:
        context['importer_type'] = 'individual'
        print(f"✅ Detected importer type: individual")
    elif "dealer" in query_lower or "company" in query_lower or "business" in query_lower:
        context['importer_type'] = 'dealer'
        print(f"✅ Detected importer type: dealer")
    
    # Extract vehicle age from query (look for year references)
    import re
    from datetime import datetime
    year_match = re.search(r'\b(20\d{2})\b', original_question)
    if year_match:
        year = int(year_match.group(1))
        current_year = datetime.now().year  # Use actual current year
        age_years = current_year - year
        if age_years <= 3:
            context['product_age_category'] = 'three_years_and_less'
            print(f"✅ Detected vehicle age: {age_years} years (≤3 years)")
        else:
            context['product_age_category'] = 'exceeding_three_years'
            print(f"✅ Detected vehicle age: {age_years} years (>3 years)")
    
    # Extract propulsion type from product info and query
    combined_text = (original_question + " " + product_name + " " + product_info_text).lower()
    if any(keyword in combined_text for keyword in ['electric', 'battery', 'tesla', 'ev', 'electric motor']):
        context['product_specifications'] = {'battery_type': 'lithium_ion'}
        print(f"✅ Detected propulsion type: electric")
    
    # Extract usage purpose
    if "personal" in query_lower or "individual" in query_lower:
        context['usage_purpose'] = 'personal'
        print(f"✅ Detected usage: personal")
    elif "commercial" in query_lower or "business" in query_lower:
        context['usage_purpose'] = 'commercial'
        print(f"✅ Detected usage: commercial")
    
    print(f"\n📊 EXTRACTED CONTEXT: {context}")
    return context

def map_context_to_answers(questions: List[Dict], extracted_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Map extracted context directly to question answers using predefined mappings.
    
    Args:
        questions: List of clarification questions from commodity code lookup
        extracted_context: Structured context extracted by DocumentContextExtractor
        
    Returns:
        Dictionary mapping question IDs to answers
    """
    answers = {}
    
    print(f"\n🎯 MAPPING EXTRACTED CONTEXT TO ANSWERS")
    print("-" * 50)
    
    for i, question in enumerate(questions, 1):
        question_id = question.get('id', f'question_{i}')
        question_text = question.get('question', '')
        question_options = question.get('options', [])
        
        print(f"\nQ{i}: {question_text}")
        print(f"   Options: {question_options}")
        
        # Map context to answers based on question type
        answer = None
        
        # Importer Type mapping
        if "importer" in question_text.lower() or "type of importer" in question_text.lower():
            importer_type = extracted_context.get('importer_type', '')
            if importer_type == 'individual':
                answer = 'Individual'
            elif importer_type == 'dealer':
                answer = 'Dealer'
            print(f"   Context: importer_type = {importer_type}")
        
        # Vehicle Age mapping
        elif "age" in question_text.lower() or "old" in question_text.lower():
            age_category = extracted_context.get('product_age_category', '')
            if age_category == 'three_years_and_less':
                answer = 'Three years or less since manufacture'
            elif age_category == 'exceeding_three_years':
                answer = 'Exceeding three years since manufacture'
            print(f"   Context: product_age_category = {age_category}")
        
        # Propulsion Type mapping
        elif "propulsion" in question_text.lower() or "motor" in question_text.lower():
            # Check product specifications for propulsion type
            product_specs = extracted_context.get('product_specifications', {})
            
            # Look for electric motor indicators in product specs
            if product_specs.get('battery_type'):
                answer = 'Only electric motor'
            elif product_specs.get('has_solar_panels'):
                answer = 'Only electric motor'
            print(f"   Context: product_specifications = {product_specs}")
        
        # Usage Purpose mapping
        elif "usage" in question_text.lower() or "purpose" in question_text.lower():
            usage_purpose = extracted_context.get('usage_purpose', '')
            if usage_purpose == 'personal':
                answer = 'Personal use'
            elif usage_purpose == 'commercial':
                answer = 'Commercial use'
            print(f"   Context: usage_purpose = {usage_purpose}")
        
        # Value Category mapping
        elif "value" in question_text.lower() or "price" in question_text.lower():
            value_category = extracted_context.get('value_category', '')
            if value_category == 'low_value':
                answer = 'Low value (under $500)'
            elif value_category == 'medium_value':
                answer = 'Medium value ($500-$2000)'
            elif value_category == 'high_value':
                answer = 'High value ($2000-$10000)'
            elif value_category == 'very_high_value':
                answer = 'Very high value (over $10000)'
            print(f"   Context: value_category = {value_category}")
        
        # Quantity Category mapping
        elif "quantity" in question_text.lower() or "number" in question_text.lower():
            quantity_category = extracted_context.get('quantity_category', '')
            if quantity_category == 'single_unit':
                answer = 'Single unit'
            elif quantity_category == 'small_quantity':
                answer = 'Small quantity (2-5 units)'
            elif quantity_category == 'medium_quantity':
                answer = 'Medium quantity (6-20 units)'
            elif quantity_category == 'bulk_quantity':
                answer = 'Bulk quantity (20+ units)'
            print(f"   Context: quantity_category = {quantity_category}")
        
        # Check if answer matches available options
        if answer and answer in question_options:
            answers[question_id] = answer
            print(f"   ✅ Mapped to: {answer}")
        elif answer:
            # Try to find partial match
            for option in question_options:
                if answer.lower() in option.lower() or option.lower() in answer.lower():
                    answers[question_id] = option
                    print(f"   ✅ Partial match: {option}")
                    break
            else:
                print(f"   ❌ No match found for: {answer}")
        else:
            print(f"   ❌ No context mapping available")
    
    print(f"\n📊 MAPPING RESULTS: {len(answers)}/{len(questions)} questions answered")
    return answers

def generate_context_aware_answers(questions: List[Dict], order_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate answers to clarification questions using order context.
    First tries direct mapping, then falls back to LLM if needed.
    
    Args:
        questions: List of clarification questions from commodity code lookup
        order_context: Order context data (BOL, invoice, etc.)
        
    Returns:
        Dictionary mapping question IDs to answers
    """
    try:
        # Get extracted context from DocumentContextExtractor
        extracted_context = order_context.get('extracted_context', {})
        
        if not extracted_context:
            print("❌ No extracted context available - cannot generate answers")
            return {}
        
        print(f"\n🤖 GENERATING CONTEXT-AWARE ANSWERS")
        print("-" * 50)
        print(f"Using order: {order_context.get('order_number', 'Unknown')}")
        
        # First try direct mapping from extracted context
        answers = map_context_to_answers(questions, extracted_context)
        
        # Check if we need LLM for remaining questions
        unanswered_questions = []
        for i, question in enumerate(questions, 1):
            question_id = question.get('id', f'question_{i}')
            if question_id not in answers:
                unanswered_questions.append(question)
        
        if unanswered_questions:
            print(f"\n🔄 {len(unanswered_questions)} questions need LLM analysis...")
            
            # Fall back to LLM for complex questions
            llm_answers = _generate_llm_answers(unanswered_questions, order_context)
            answers.update(llm_answers)
        
        print(f"\n✅ FINAL RESULTS: {len(answers)}/{len(questions)} questions answered")
        for q_id, answer in answers.items():
            print(f"   {q_id}: {answer}")
        
        return answers
        
    except Exception as e:
        print(f"[ERROR] Error generating context-aware answers: {e}")
        return {}

def _generate_llm_answers(questions: List[Dict], order_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Fallback LLM-based answer generation for complex questions.
    """
    try:
        # Extract relevant data from context
        bol_data = order_context.get('file_data', {}).get('bill_of_lading', {})
        invoice_data = order_context.get('file_data', {}).get('invoice', {})
        extracted_context = order_context.get('extracted_context', {})
        
        # Build context summary for LLM
        context_summary = "ORDER CONTEXT:\n\n"
        
        # Add extracted context
        context_summary += "EXTRACTED CONTEXT:\n"
        for key, value in extracted_context.items():
            context_summary += f"- {key}: {value}\n"
        context_summary += "\n"
        
        # Add raw document data
        if bol_data:
            context_summary += "BILL OF LADING:\n"
            context_summary += f"- Consignee: {bol_data.get('consignee_name', 'N/A')}\n"
            context_summary += f"- Commodity: {bol_data.get('commodity', 'N/A')}\n\n"
        
        if invoice_data:
            context_summary += "INVOICE:\n"
            context_summary += f"- Buyer: {invoice_data.get('buyer', {}).get('name', 'N/A')}\n"
            context_summary += f"- Total Amount: {invoice_data.get('totals', {}).get('total_amount', 'N/A')}\n\n"
        
        # Build questions for LLM
        questions_text = "REMAINING QUESTIONS:\n"
        for i, q in enumerate(questions, 1):
            questions_text += f"{i}. {q.get('question', 'N/A')}\n"
            questions_text += f"   Options: {q.get('options', [])}\n\n"
        
        # Create LLM prompt
        prompt = f"""You are a customs classification expert. Based on the order context provided, answer the remaining clarification questions.

{context_summary}

{questions_text}

Return ONLY a JSON object with question IDs as keys and selected option values as values.

Example format:
{{
  "question_1": "Selected Option",
  "question_2": "Another Option"
}}"""
        
        print(f"[LLM] Analyzing remaining questions with LLM...")
        response = reason_with_llm_fn(prompt)
        
        # Parse JSON response
        import json
        try:
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            llm_answers = json.loads(cleaned_response)
            print(f"[LLM] Generated {len(llm_answers)} additional answers")
            return llm_answers
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse LLM response: {e}")
            return {}
            
    except Exception as e:
        print(f"[ERROR] LLM fallback failed: {e}")
        return {}

def lookup_commodity_code_with_context_auto_answers(hs_codes: list[str], product_name: str, product_info_text: str, 
                                                   original_question: str = "", order_id: int = None) -> dict:
    """
    Enhanced commodity code lookup that automatically answers clarification questions using order context.
    
    Args:
        hs_codes: List of HS codes
        product_name: Name of the product
        product_info_text: Additional product information
        original_question: The original user question
        order_id: Order ID to retrieve context from
        
    Returns:
        Dictionary with commodity code results and auto-answered questions
    """
    print(f"\n🚀 ENHANCED COMMODITY CODE LOOKUP WITH CONTEXT AUTO-ANSWERS")
    print("=" * 70)
    
    # Step 1: Get order context if order_id provided
    order_context = {}
    if order_id:
        print(f"\n📋 RETRIEVING ORDER CONTEXT")
        print("-" * 50)
        order_context = get_order_context_by_id(order_id)
        if order_context:
            print(f"✅ Retrieved context for order: {order_context.get('order_number', 'Unknown')}")
        else:
            print(f"❌ No context found for order ID: {order_id}")
    
    # Step 2: Run initial commodity code lookup
    print(f"\n🔍 RUNNING INITIAL COMMODITY CODE LOOKUP")
    print("-" * 50)
    initial_result = lookup_commodity_code(hs_codes, product_name, product_info_text, original_question, order_id)
    
    # Step 3: Check if clarification is needed and auto-answer if context available
    enhanced_result = {}
    
    for hs_code, result in initial_result.items():
        if isinstance(result, dict) and result.get('requires_clarification') and order_context:
            print(f"\n🤖 AUTO-ANSWERING QUESTIONS FOR {hs_code}")
            print("-" * 50)
            
            # Get questions from the result
            questions = result.get('questions', [])
            if not questions:
                print(f"❌ No questions found for {hs_code}")
                enhanced_result[hs_code] = result
                continue
            
            # Display comprehensive context before generating answers
            print(f"\n[CONTEXT] AVAILABLE CONTEXT INFORMATION")
            print("-" * 50)
            
            # Context Source 1: Original Query
            if original_question:
                print(f"📝 ORIGINAL USER QUERY:")
                print(f"   {original_question}")
            else:
                print(f"📝 ORIGINAL USER QUERY: Not provided")
            
            # Context Source 2: Product Information
            print(f"\n📦 PRODUCT INFORMATION:")
            print(f"   Product Name: {product_name}")
            print(f"   Product Details: {product_info_text}")
            
            # Context Source 3: Order Context
            print(f"\n📋 ORDER CONTEXT (Order ID: {order_id}):")
            print(f"   Order Number: {order_context.get('order_number', 'N/A')}")
            
            # Display extracted context from DocumentContextExtractor
            extracted_context = order_context.get('extracted_context', {})
            if extracted_context:
                print(f"   📊 EXTRACTED CONTEXT:")
                for key, value in extracted_context.items():
                    print(f"      - {key}: {value}")
            else:
                print(f"   📊 EXTRACTED CONTEXT: Not available")
            
            # Display raw document data
            file_data = order_context.get('file_data', {})
            if file_data.get('bill_of_lading'):
                print(f"   📄 BILL OF LADING DATA:")
                bol_data = file_data['bill_of_lading']
                print(f"      - Consignee: {bol_data.get('consignee_name', 'N/A')}")
                print(f"      - Shipper: {bol_data.get('shipper', 'N/A')}")
                print(f"      - Commodity: {bol_data.get('commodity', 'N/A')}")
                print(f"      - Weight: {bol_data.get('weight', 'N/A')}")
                print(f"      - Package Type: {bol_data.get('package_type', 'N/A')}")
            
            if file_data.get('invoice'):
                print(f"   📄 INVOICE DATA:")
                invoice_data = file_data['invoice']
                print(f"      - Buyer: {invoice_data.get('buyer', {}).get('name', 'N/A')}")
                print(f"      - Supplier: {invoice_data.get('supplier', {}).get('name', 'N/A')}")
                print(f"      - Invoice Date: {invoice_data.get('invoice_details', {}).get('date', 'N/A')}")
                print(f"      - Total Amount: ${invoice_data.get('totals', {}).get('total_amount', 'N/A')}")
                
                # Show items
                items = invoice_data.get('items', [])
                if items:
                    print(f"      - Items:")
                    for item in items:
                        print(f"        * {item.get('description', 'N/A')} - Qty: {item.get('quantity', 'N/A')}")
            
            print(f"\n[CONTEXT] END OF CONTEXT INFORMATION")
            print("-" * 50)
            
            # Generate context-aware answers
            auto_answers = generate_context_aware_answers(questions, order_context)
            
            if auto_answers:
                print(f"✅ Generated {len(auto_answers)} auto-answers")
                
                # Re-run lookup with auto-answers
                print(f"\n🔄 RE-RUNNING LOOKUP WITH AUTO-ANSWERS")
                print("-" * 50)
                
                # Convert auto-answers to the format expected by lookup_commodity_code_with_answers
                user_answers = {}
                for i, question in enumerate(questions, 1):
                    answer_key = str(i)
                    if answer_key in auto_answers:
                        # Map the answer back to the question's option values
                        selected_answer = auto_answers[answer_key]
                        question_options = question.get('options', [])
                        
                        # Find matching option value
                        for option in question_options:
                            if isinstance(option, dict) and option.get('label') == selected_answer:
                                user_answers[question.get('id', f'question_{i}')] = option.get('value', selected_answer)
                                break
                            elif isinstance(option, str) and option == selected_answer:
                                user_answers[question.get('id', f'question_{i}')] = selected_answer
                                break
                        else:
                            # Fallback to direct value
                            user_answers[question.get('id', f'question_{i}')] = selected_answer
                
                # Re-run with answers
                final_result = lookup_commodity_code_with_answers(
                    [hs_code], product_name, product_info_text, original_question, user_answers, order_id
                )
                
                enhanced_result[hs_code] = final_result.get(hs_code, result)
            else:
                print(f"❌ Failed to generate auto-answers for {hs_code}")
                enhanced_result[hs_code] = result
        else:
            enhanced_result[hs_code] = result
    
    return enhanced_result

def build_enhanced_product_context(bill_of_lading_path: str, invoice_path: str, 
                                  product_name: str, product_info: str) -> str:
    """
    Build enhanced product context by combining document data with existing info.
    
    Args:
        bill_of_lading_path: Path to bill of lading JSON file
        invoice_path: Path to invoice JSON file  
        product_name: Original product name
        product_info: Original product information
        
    Returns:
        Enhanced product information string
    """
    try:
        # Load documents
        with open(bill_of_lading_path, 'r') as f:
            bill_of_lading = json.load(f)
        
        with open(invoice_path, 'r') as f:
            invoice = json.load(f)
        
        # Extract context
        extractor = DocumentContextExtractor()
        context = extractor.extract_context_from_documents(bill_of_lading, invoice)
        
        # Build enhanced context string
        enhanced_info = f"{product_info}\n\nExtracted Document Context:\n"
        
        for key, value in context.items():
            if isinstance(value, dict):
                enhanced_info += f"- {key.replace('_', ' ').title()}:\n"
                for sub_key, sub_value in value.items():
                    enhanced_info += f"  * {sub_key}: {sub_value}\n"
            else:
                enhanced_info += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        return enhanced_info
        
    except Exception as e:
        print(f"Error building enhanced context: {e}")
        return product_info  # Fallback to original info

# ═══════════════════════════════════════════════════════════════════════════════
# CORE LOOKUP LOGIC (Main business logic classes and methods)
# ═══════════════════════════════════════════════════════════════════════════════

class CommodityCodeLookup:
    """Main class for looking up and selecting commodity codes."""
    
    def __init__(self, supabase_url: str, supabase_key: str, use_llm_selection: bool = True):
        """Initialize the lookup service with database connection."""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.use_llm_selection = use_llm_selection

    def find_matching_codes(self, hs_codes: List[str]) -> Dict[str, List[Dict]]:
        """
        Return a dict mapping each HS code to the list of matching 10-digit codes.
        """
        results: Dict[str, List[Dict]] = {}

        for hs_code in hs_codes:
            try:
                # Remove dots from HS code for database query
                clean_hs_code = hs_code.replace(".", "")
                
                response = (
                    self.supabase.table("tariff_codes")
                    .select("*")
                    .ilike("tariff_code", f"{clean_hs_code}%")  # starts-with match
                    .execute()
                )
                data = response.data or []
                results[hs_code] = data
                logger.info("HS %s ➜ %s matches", hs_code, len(data))
            except Exception as exc:  # noqa: BLE001
                logger.error("Supabase query failed for %s: %s", hs_code, exc)
                results[hs_code] = []

        return results

    def find_single_code(self, hs_code: str, product_name: str, product_info_text: str) -> List[Dict]:
        """
        Find matching commodity codes for a given HS code.
        
        Args:
            hs_code: The 6-digit HS code to look up (may have dots like "0706.10")
            product_name: Name of the product
            product_info_text: Additional product information
            
        Returns:
            List of matching commodity codes with their descriptions
        """
        try:
            # Remove dots from HS code for database query
            clean_hs_code = hs_code.replace(".", "")
            
            logger.info(f"Looking up commodity codes for HS code {hs_code} (cleaned: {clean_hs_code})")
            
            # Query tariff_codes table for matches
            response = (
                self.supabase.table("tariff_codes")
                .select("tariff_code,description")
                .ilike("tariff_code", f"{clean_hs_code}%")  # starts-with match
                .execute()
            )
            
            if response.data:
                logger.info(f"Found {len(response.data)} matches for HS code {hs_code}")
                return response.data
            else:
                logger.warning(f"No matches found for HS code {hs_code} (cleaned: {clean_hs_code})")
                return []
                
        except Exception as e:
            logger.error(f"Error looking up commodity codes for {hs_code}: {str(e)}")
            return []

    def extract_classification_attributes(self, commodity_matches: List[Dict]) -> List[Dict]:
        """
        Extract classification attributes needed to distinguish between HS codes.
        Returns a simple list of attributes with their options.
        """
        if len(commodity_matches) <= 1:
            return []
        
        print(f"\n[EXTRACTING] CLASSIFICATION ATTRIBUTES")
        print("-" * 50)
        
        # Build HS codes list for the prompt
        hs_codes_text = ""
        for match in commodity_matches:
            hs_codes_text += f"• {match['tariff_code']}: {match['description']}\n"
        
        # Use the clean prompt structure
        prompt = f"""You are given a set of HS codes and their descriptions.
Your task is not to return the HS code, but to extract the classification attributes that are necessary to decide between them.

HS Codes:
{hs_codes_text.strip()}

Output Requirement:
Return a structured list of attributes that must be determined to select the correct code. Do not return the HS codes themselves.

Example Output Format (JSON):

{{
  "attributes": [
    {{"name": "Importer Type", "options": ["Individual", "Dealer"]}},
    {{"name": "Vehicle Age", "options": ["Three years or less since manufacture", "Exceeding three years since manufacture"]}},
    {{"name": "Propulsion Type", "options": ["Only electric motor"]}}
  ]
}}"""
        
        try:
            print(f"[LLM] Extracting classification attributes...")
            response = reason_with_llm_fn(prompt)
            print(f"[LLM] Raw response: {response}")
            
            # Parse JSON response - handle markdown code blocks
            import json
            try:
                # Clean the response to extract JSON from markdown code blocks
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
                
                result = json.loads(cleaned_response)
                attributes = result.get("attributes", [])
                print(f"[RESULT] Extracted {len(attributes)} classification attribute(s):")
                for attr in attributes:
                    print(f"   - {attr.get('name', 'Unknown')}: {attr.get('options', [])}")
                return attributes
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON response: {e}")
                print(f"[ERROR] Raw response: {response}")
                print(f"[ERROR] Cleaned response: {cleaned_response}")
                return self._retry_with_alternative_llm(commodity_matches)
                
        except Exception as e:
            print(f"[ERROR] LLM extraction failed: {e}, trying alternative LLM...")
            return self._retry_with_alternative_llm(commodity_matches)
    
    def _retry_with_alternative_llm(self, commodity_matches: List[Dict]) -> List[Dict]:
        """Retry attribute extraction with an alternative LLM approach."""
        print(f"[RETRY] Trying alternative LLM approach...")
        
        # Build HS codes list for the prompt
        hs_codes_text = ""
        for match in commodity_matches:
            hs_codes_text += f"• {match['tariff_code']}: {match['description']}\n"
        
        # Simpler prompt for alternative LLM
        prompt = f"""Analyze these HS codes and identify the key attributes that distinguish them:

{hs_codes_text.strip()}

Return ONLY a JSON array of attributes in this format:
[
  {{"name": "Attribute Name", "options": ["Option 1", "Option 2"]}}
]"""
        
        try:
            print(f"[LLM] Retrying with alternative prompt...")
            response = reason_with_llm_fn(prompt)
            print(f"[LLM] Alternative response: {response}")
            
            # Parse JSON response - handle markdown code blocks
            import json
            try:
                # Clean the response to extract JSON from markdown code blocks
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove ```
                cleaned_response = cleaned_response.strip()
                
                result = json.loads(cleaned_response)
                if isinstance(result, list):
                    attributes = result
                else:
                    attributes = result.get("attributes", [])
                
                print(f"[RESULT] Alternative LLM extracted {len(attributes)} attribute(s):")
                for attr in attributes:
                    print(f"   - {attr.get('name', 'Unknown')}: {attr.get('options', [])}")
                return attributes
            except json.JSONDecodeError as e:
                print(f"[ERROR] Alternative LLM also failed to return valid JSON: {e}")
                print(f"[ERROR] Raw response: {response}")
                print(f"[ERROR] Cleaned response: {cleaned_response}")
                return []
                
        except Exception as e:
            print(f"[ERROR] Alternative LLM also failed: {e}")
            return []
    
    def generate_questions_for_attributes(self, attributes: List[Dict]) -> List[Dict]:
        """Generate clarification questions for the required attributes."""
        questions = []
        
        for attr in attributes:
            attr_name = attr.get('name', 'Unknown')
            options = attr.get('options', [])
            
            if attr_name == "Importer Type":
                questions.append({
                    "question": "What type of importer are you?",
                    "type": "multiple_choice",
                    "options": options,
                    "help_text": "Select whether you are importing as an individual or as a dealer/company."
                })
            elif attr_name == "Vehicle Age":
                questions.append({
                    "question": "How old is the vehicle?",
                    "type": "multiple_choice", 
                    "options": options,
                    "help_text": "Select the age category based on years since manufacture."
                })
            else:
                # Generic question for other attributes
                questions.append({
                    "question": f"Please specify: {attr_name}",
                    "type": "multiple_choice",
                    "options": options,
                    "help_text": f"Select the appropriate option for {attr_name.lower()}."
                })
        
        return questions

    def select_best_commodity_code(self, hs_code: str, commodity_matches: List[Dict], 
                                 product_name: str, product_info_text: str, 
                                 extracted_context: Dict[str, str] = None) -> Optional[Dict]:
        """Select the best commodity code using LLM with extracted context."""
        if not commodity_matches:
            return None
        
        if len(commodity_matches) == 1:
            return commodity_matches[0]
        
        # Prepare context for LLM selection
        context_text = f"Product: {product_name}\nInfo: {product_info_text}"
        if extracted_context:
            context_text += f"\nExtracted Context: {extracted_context}"
        
        # Create commodity codes list
        codes_text = "Available commodity codes:\n"
        for i, match in enumerate(commodity_matches):
            codes_text += f"{i+1}. {match['tariff_code']}: {match['description']}\n"
        
        prompt = f"""You are a customs classification expert. Select the most appropriate commodity code based on the product information.

{context_text}

{codes_text}

Select the best matching commodity code and return ONLY the tariff code number (e.g., 8703800010).

If none of the codes are appropriate, return "NONE"."""
        
        try:
            print(f"[LLM] Selecting best commodity code...")
            response = reason_with_llm_fn(prompt)
            print(f"[LLM] Selection response: {response}")
            
            # Parse response
            selected_code = response.strip()
            if selected_code == "NONE":
                print(f"[RESULT] LLM rejected all codes as inappropriate")
                return None
            
            # Clean up response - remove brackets if present
            if selected_code.startswith('[') and selected_code.endswith(']'):
                selected_code = selected_code[1:-1]
            
            # Find the selected code
            for match in commodity_matches:
                if match['tariff_code'] == selected_code:
                    print(f"[RESULT] Selected: {selected_code}")
                    return match
            
            print(f"[ERROR] Selected code {selected_code} not found in matches")
            print(f"[DEBUG] Available codes: {[m['tariff_code'] for m in commodity_matches]}")
            return None
            
        except Exception as e:
            print(f"[ERROR] Error selecting commodity code: {e}")
            return None

def reason_with_llm_fn(prompt: str, hs_code: str = None) -> str:
    """
    Simple wrapper function for LLM reasoning calls.
    Replaces the circular import from confirm_hs_code.
    """
    messages = [
        {"role": "system", "content": "You are an expert in HS Code classification. Always respond in the exact format requested."},
        {"role": "user", "content": prompt}
    ]
    return chat_completion(messages, model_alias="mistral_small")

def reason_with_llm_for_commodity(prompt: str, hs_code: str = None) -> str:
    """
    Alias for reason_with_llm_fn to maintain compatibility with confirm_hs_code.py
    """
    return reason_with_llm_fn(prompt, hs_code)

def call_llm(messages, model_alias, config, models):
    """
    Make the actual HTTP request to the LLM API.
    
    Args:
        messages: Chat messages to send
        model_alias: Model configuration key
        config: API configuration (headers, URL, etc.)
        models: Model definitions and parameters
        
    Returns:
        The response content from the LLM
    """
    model = models[model_alias]["name"]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": models[model_alias].get("temperature", 0.7),
        "max_tokens": models[model_alias].get("max_tokens", 1000),
        "response_format": {"type": "json_object"}
    }
    response = requests.post(
        config["api_url"],
        headers=config["headers"],
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    
    # Debug: Log the full response structure
    logger.info(f"Full LLM API response: {result}")
    
    # Check if response has expected structure
    if "choices" not in result:
        logger.error(f"LLM response missing 'choices' key: {result}")
        return ""
    
    if not result["choices"]:
        logger.error(f"LLM response has empty 'choices' array: {result}")
        return ""
    
    choice = result["choices"][0]
    
    # Check if choice has expected structure
    if "message" not in choice:
        logger.error(f"LLM choice missing 'message' key: {choice}")
        return ""
    
    if "content" not in choice["message"]:
        logger.error(f"LLM message missing 'content' key: {choice['message']}")
        return ""
    
    content = choice["message"]["content"]
    logger.info(f"LLM response content: '{content}'")
    return content

def chat_completion(messages, model_alias="mistral_small"):
    """
    Handle LLM API calls for single model classification.
    
    Args:
        messages: List of message objects for the chat completion
        model_alias: Which model configuration to use
        
    Returns:
        The response content from the LLM
    """
    config = OPENROUTER_CONFIG
    models = OPENROUTER_MODELS
    
    if model_alias not in models:
        logger.error(f"Unknown model alias: {model_alias}")
        return ""
    
    try:
        return call_llm(messages, model_alias, config, models)
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        return ""

def test_context_extraction():
    """Test the context extraction with sample data."""
    extractor = DocumentContextExtractor()
    
    # Sample data
    bill_of_lading = {
        'consignee_name': 'John Smith',
        'port_of_origin': 'UNITED STATES',
        'weight': '2000 KGM'
    }
    
    invoice = {
        'buyer': {'name': 'John Smith', 'address': '123 Main St'},
        'items': [{'description': 'Tesla Model Y 2023 Electric SUV', 'quantity': 1}],
        'totals': {'total_amount': 50000}
    }
    
    context = extractor.extract_context_from_documents(bill_of_lading, invoice)
    print("Extracted context:")
    for key, value in context.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commodity Code Lookup with LLM Selection")
    parser.add_argument("--hs-codes", nargs="+", required=True, help="HS codes to look up")
    parser.add_argument("--product-name", required=True, help="Name of the product")
    parser.add_argument("--product-info", required=True, help="Additional product information")
    parser.add_argument("--question", default="", help="Original user question")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    if args.interactive:
        result = interactive_commodity_lookup(
            args.hs_codes, args.product_name, args.product_info, args.question
        )
    else:
        result = lookup_commodity_code(
            args.hs_codes, args.product_name, args.product_info, args.question
        )
    
    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    print(json.dumps(result, indent=2))
