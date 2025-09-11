#!/usr/bin/env python3
"""
Commodity Code Lookup with LLM Selection - 10-Stage Workflow
------------------------------------------------------------

Look up Jamaican 10-digit tariff codes that start with the supplied 6-digit HS codes,
then use LLM reasoning to select the most appropriate commodity code for the product.

10-Stage Workflow:
- Stage 3: Simple commodity code lookup
- Stage 4: Generate classification questions  
- Stage 5: Context resolution
- Stage 6: Answer questions with LLM
- Stage 7: List unanswered questions
- Stage 8: Show additional context
- Stage 9: Complete the loop
- Stage 10: Final code selection
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
# 10-STAGE COMMODITY CODE WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

def stage3_commodity_lookup(hs_codes: list[str]) -> dict:
    """
    Stage 3: Simple commodity code lookup - just query database for all matching codes.
    
    Args:
        hs_codes: List of HS codes (may have dots like ["0706.10"])
        
    Returns:
        Dictionary mapping HS codes to list of all matching commodity codes
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=False)
    results = {}
    
    print(f"\n📋 STAGE 3: COMMODITY CODE LOOKUP")
    print("-" * 50)
    
    for hs_code in hs_codes:
        # Find all matches - simple database query
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
                results[hs_code] = []
            else:
                print(f"├── {hs_code}: Found {len(all_matches)} commodity codes")
                # Display the commodity codes
                for i, code in enumerate(all_matches, 1):
                    print(f"│   {i}. {code['tariff_code']}: {code['description']}")
                results[hs_code] = all_matches
                
        except Exception as e:
            print(f"├── {hs_code}: [ERROR] {str(e)}")
            results[hs_code] = []
    
    return results

def stage4_generate_questions(stage3_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 4: Generate Classification Questions
    Takes the commodity codes from Stage 3 as input and uses LLM to analyze 
    the commodity codes and generate clarification questions.
    
    Args:
        stage3_results: Results from Stage 3 (HS codes mapped to commodity codes)
        product_name: Name of the product
        product_info_text: Additional product information
        
    Returns:
        Dictionary mapping HS codes to questions or direct results
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=True)
    results = {}
    
    print(f"\n❓ STAGE 4: GENERATE CLASSIFICATION QUESTIONS")
    print("-" * 50)
    
    for hs_code, commodity_codes in stage3_results.items():
        print(f"\n├── {hs_code}: Analyzing {len(commodity_codes)} commodity codes")
        
        if not commodity_codes:
            print(f"│   └── [SKIP] No commodity codes to analyze")
            results[hs_code] = {
                'stage': 4,
                'status': 'no_codes',
                'message': 'No commodity codes found in Stage 3'
            }
            continue
        
        if len(commodity_codes) == 1:
            print(f"│   └── [SKIP] Only one code - no questions needed")
            results[hs_code] = {
                'stage': 4,
                'status': 'single_code',
                'selected_code': commodity_codes[0],
                'message': 'Only one commodity code available'
            }
            continue
        
        # Extract classification attributes needed
        print(f"│   └── [LLM] Extracting classification attributes...")
        classification_attributes = lookup.extract_classification_attributes(commodity_codes)
        
        if not classification_attributes:
            print(f"│   └── [SKIP] No distinguishing attributes - can select directly")
            # Use LLM to select best match
            best_match = lookup.select_best_commodity_code(
                hs_code, commodity_codes, product_name, product_info_text, {}
            )
            
            if best_match:
                results[hs_code] = {
                    'stage': 4,
                    'status': 'direct_selection',
                    'selected_code': best_match,
                    'message': 'LLM selected best match directly'
                }
            else:
                results[hs_code] = {
                    'stage': 4,
                    'status': 'rejected',
                    'message': 'LLM rejected all codes as inappropriate'
                }
        else:
            print(f"│   └── [QUESTIONS] Generating {len(classification_attributes)} clarification questions")
            
            # Generate specific questions for the required attributes
            questions = lookup.generate_questions_for_attributes(classification_attributes, product_name, product_info_text)
            
            print(f"│       └── Generated questions:")
            for i, q in enumerate(questions, 1):
                print(f"│           {i}. {q['question']} ({q.get('attribute', 'unknown')})")
            
            results[hs_code] = {
                'stage': 4,
                'status': 'questions_generated',
                'questions': questions,
                'commodity_codes': commodity_codes,
                'classification_attributes': classification_attributes,
                'message': f'Generated {len(questions)} clarification questions'
            }
    
    return results

def stage5_resolve_context(stage1_results: dict, original_query: str, order_id: str = None, 
                          contextual_data: Dict[str, Any] = None, product_name: str = None) -> dict:
    """
    Stage 5: Context Resolution
    Displays the available context information without doing any resolution.
    
    Args:
        stage1_results: Results from Stage 1 (HS code classification)
        original_query: The original user query
        order_id: Order ID for context lookup
        contextual_data: Direct contextual data from request
        
    Returns:
        Dictionary with context information displayed
    """
    results = {}
    
    print(f"\n🔍 STAGE 5: CONTEXT")
    print("-" * 50)
    print(f"🔍 DEBUG: contextual_data = {contextual_data}")
    print(f"🔍 DEBUG: product_name = {product_name}")
    print(f"🔍 DEBUG: original_query = {original_query}")
    
    # 1. Product name (from intent parser)
    display_product_name = product_name if product_name else (stage1_results.get('product_name', 'N/A') if stage1_results else 'N/A')
    print(f"├── Product name (intent parser): {display_product_name}")
    
    # 2. Initial query or customs api data (invoice and BOL)
    if contextual_data:
        if contextual_data.get('user_query'):
            print(f"├── User query: {contextual_data['user_query']}")
        if contextual_data.get('invoice_data'):
            invoice = contextual_data['invoice_data']
            print(f"├── Invoice: {invoice.get('invoice_number', 'N/A')} - {invoice.get('supplier', 'N/A')}")
        if contextual_data.get('bill_of_lading'):
            bol = contextual_data['bill_of_lading']
            print(f"├── Bill of Lading: {bol.get('bol_number', 'N/A')} - {bol.get('vessel', 'N/A')}")
    else:
        print(f"├── No contextual data provided")
    
    # 3. Generated product data from stage 1
    if stage1_results:
        product_info = stage1_results.get('product_information', 'N/A')
        print(f"├── Generated product data (Stage 1): {product_info}")
    else:
        print(f"├── Generated product data (Stage 1): None")
    
    results = {
        'stage': 5,
        'status': 'context_displayed',
        'stage1_results': stage1_results,
        'contextual_data': contextual_data,
        'order_id': order_id,
        'original_query': original_query,
        'message': 'Context sources and Stage 1 data displayed'
    }
    
    return results

def stage6_llm_answer_questions(stage4_results: dict, stage5_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 6: Answer Questions with LLM
    Takes questions from Stage 4 and context info from Stage 5, then does actual 
    context resolution and LLM answering.
    """
    results = {}
    
    print(f"\n🤖 STAGE 6: CONTEXT PROCESSING & QUESTION ANSWERING")
    print("-" * 50)
    
    # Get context info from Stage 5
    contextual_data = stage5_results.get('contextual_data')
    order_id = stage5_results.get('order_id')
    original_query = stage5_results.get('original_query')
    
    for hs_code, stage4_data in stage4_results.items():
        print(f"\n├── {hs_code}: Processing questions with context")
        
        if stage4_data.get('status') == 'questions_generated':
            questions = stage4_data.get('questions', [])
            commodity_codes = stage4_data.get('commodity_codes', [])
            
            # Step 1: Show questions from Stage 4
            print(f"│   ├── Step 1: Questions from Stage 4")
            for i, question in enumerate(questions, 1):
                question_text = question.get('question', 'N/A')
                options = question.get('options', [])
                option_values = [opt.get('value', 'N/A') for opt in options]
                print(f"│   │   └── Q{i}: {question_text}")
                print(f"│   │       └── Options: {' / '.join(option_values)}")
            
            # Step 2: Show context from Stage 5
            print(f"│   ├── Step 2: Context from Stage 5")
            print(f"│   │   └── Product: {product_name}")
            if contextual_data:
                if contextual_data.get('user_query'):
                    print(f"│   │   └── User query: {contextual_data['user_query']}")
                if contextual_data.get('invoice_data'):
                    invoice = contextual_data['invoice_data']
                    print(f"│   │   └── Invoice: {invoice.get('invoice_number', 'N/A')} - {invoice.get('supplier', 'N/A')}")
                if contextual_data.get('bill_of_lading'):
                    bol = contextual_data['bill_of_lading']
                    print(f"│   │   └── Bill of Lading: {bol.get('bol_number', 'N/A')} - {bol.get('vessel', 'N/A')}")
            else:
                print(f"│   │   └── No contextual data provided")
            print(f"│   │   └── Product data: {product_info_text[:100]}...")
            
            # Step 3: Process context and answer questions
            print(f"│   ├── Step 3: LLM Processing")
            print(f"│   │   └── ✅ Analyzing context to answer questions")
            
            # Now do the actual context resolution
            resolved_context = resolve_context(
                product_name=product_name,
                contextual_data=contextual_data,
                order_id=order_id,
                original_query=original_query
            )
            
            # Try to map context to answers
            auto_answers = map_context_to_answers(questions, resolved_context)
            
            # Find unanswered questions
            unanswered_questions = []
            for i, question in enumerate(questions, 1):
                question_id = question.get('id', f'question_{i}')
                if question_id not in auto_answers:
                    unanswered_questions.append(question)
            
            if unanswered_questions:
                print(f"│   │   └── ✅ Using LLM to answer {len(unanswered_questions)} remaining questions")
                
                # Use LLM to answer remaining questions
                llm_answers = _generate_llm_answers_for_stage6(unanswered_questions, resolved_context, product_name, product_info_text)
                
                # Validate LLM answers - only accept answers with sufficient contextual evidence
                validated_llm_answers = _validate_llm_answers(llm_answers, unanswered_questions, resolved_context)
                
                # Combine auto-answers with validated LLM answers
                combined_answers = {**auto_answers, **validated_llm_answers}
                
                print(f"│   │   └── ✅ Generated {len(llm_answers)} LLM answers")
            else:
                combined_answers = auto_answers
                print(f"│   │   └── ✅ All questions answered automatically")
            
            # Step 4: Show final results
            print(f"│   └── Step 4: Results")
            print(f"│       └── ✅ All {len(questions)} questions answered")
            print(f"│       └── ✅ Ready for final classification")
            
            results[hs_code] = {
                'stage': 6,
                'status': 'questions_answered',
                'questions': questions,
                'auto_answers': auto_answers,
                'llm_answers': llm_answers if unanswered_questions else {},
                'combined_answers': combined_answers,
                'resolved_context': resolved_context,
                'commodity_codes': commodity_codes,
                'message': f'Answered {len(combined_answers)}/{len(questions)} questions (auto + LLM)'
            }
        else:
            print(f"│   └── [SKIP] No questions to answer (status: {stage4_data.get('status')})")
            results[hs_code] = {
                'stage': 6,
                'status': 'no_questions',
                'stage4_data': stage4_data,
                'message': 'No questions to answer with LLM'
            }
    
    return results

def stage7_list_unanswered(stage6_results: dict) -> dict:
    """
    Stage 7: List Unanswered Questions
    Takes all questions and answers and identifies which questions still need user input.
    """
    results = {}
    
    print(f"\n❓ STAGE 7: LIST UNANSWERED QUESTIONS")
    print("-" * 50)
    
    for hs_code, stage6_data in stage6_results.items():
        print(f"\n├── {hs_code}: Checking for unanswered questions")
        
        if stage6_data.get('status') in ['questions_answered', 'all_answered']:
            questions = stage6_data.get('questions', [])
            combined_answers = stage6_data.get('combined_answers', stage6_data.get('auto_answers', {}))
            
            # Find unanswered questions
            unanswered_questions = []
            for i, question in enumerate(questions, 1):
                question_id = question.get('id', f'question_{i}')
                if question_id not in combined_answers:
                    unanswered_questions.append(question)
            
            if unanswered_questions:
                print(f"│   └── [UNANSWERED] {len(unanswered_questions)} questions need user input")
                for i, q in enumerate(unanswered_questions, 1):
                    print(f"│       {i}. {q.get('question', 'N/A')}")
                
                results[hs_code] = {
                    'stage': 7,
                    'status': 'user_input_needed',
                    'unanswered_questions': unanswered_questions,
                    'all_questions': questions,
                    'answered_questions': combined_answers,
                    'commodity_codes': stage6_data.get('commodity_codes', []),
                    'message': f'{len(unanswered_questions)} questions need user input'
                }
            else:
                print(f"│   └── [COMPLETE] All questions answered - ready for final selection")
                results[hs_code] = {
                    'stage': 7,
                    'status': 'all_answered',
                    'all_questions': questions,
                    'answered_questions': combined_answers,
                    'commodity_codes': stage6_data.get('commodity_codes', []),
                    'message': 'All questions answered - ready for final selection'
                }
        else:
            print(f"│   └── [SKIP] No questions to check (status: {stage6_data.get('status')})")
            results[hs_code] = {
                'stage': 7,
                'status': 'no_questions',
                'stage6_data': stage6_data,
                'message': 'No questions to check for unanswered status'
            }
    
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPORTING FUNCTIONS FOR 10-STAGE WORKFLOW
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

def _generate_llm_answers_for_stage6(questions: List[Dict], resolved_context: Dict[str, Any], 
                                    product_name: str, product_info_text: str) -> Dict[str, str]:
    """
    Generate LLM answers for remaining questions in Stage 6.
    """
    try:
        # Build context summary for LLM
        context_summary = "AVAILABLE CONTEXT:\n\n"
        
        # Add resolved context
        for key, value in resolved_context.items():
            context_summary += f"- {key}: {value}\n"
        context_summary += "\n"
        
        # Add product information
        context_summary += f"PRODUCT INFORMATION:\n"
        context_summary += f"- Product Name: {product_name}\n"
        context_summary += f"- Product Details: {product_info_text}\n\n"
        
        # Build questions for LLM
        questions_text = "REMAINING QUESTIONS TO ANSWER:\n"
        for i, q in enumerate(questions, 1):
            questions_text += f"{i}. {q.get('question', 'N/A')}\n"
            questions_text += f"   Options: {q.get('options', [])}\n\n"
        
        # Create LLM prompt
        prompt = f"""You are a customs classification expert. Based on the available context and product information, answer the remaining clarification questions.

IMPORTANT: Only answer questions where you have CLEAR CONTEXTUAL EVIDENCE. If the context does not provide sufficient information to determine an answer, DO NOT guess or make assumptions.

{context_summary}

{questions_text}

INSTRUCTIONS:
1. Only answer questions where the available context provides clear evidence
2. If context is insufficient, DO NOT include that question in your response
3. Do not make assumptions or guesses beyond what the context explicitly indicates
4. If you cannot determine an answer from the context, omit that question entirely

Return ONLY a JSON object with question IDs as keys and selected option values as values.
Only include questions you can answer with confidence based on the available context.

Example format (only include questions you can answer):
{{
  "question_1": "Selected Option"
}}
Note: If question_2 cannot be answered from context, do not include it in the response."""
        
        print(f"│       └── [LLM] Analyzing remaining questions with LLM...")
        
        # Show the exact prompt being sent to LLM
        print(f"│       └── [LLM PROMPT]")
        print(f"│           └── {prompt}")
        
        response = reason_with_llm_fn(prompt)
        
        # Show the exact response from LLM
        print(f"│       └── [LLM RESPONSE]")
        print(f"│           └── {response}")
        
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
            print(f"│       └── [LLM] Generated {len(llm_answers)} additional answers")
            return llm_answers
            
        except json.JSONDecodeError as e:
            print(f"│       └── [ERROR] Failed to parse LLM response: {e}")
            return {}
            
        except Exception as e:
            print(f"│       └── [ERROR] LLM answering failed: {e}")
            return {}
            
    except Exception as e:
        print(f"│       └── [ERROR] LLM processing failed: {e}")
        return {}

def _validate_llm_answers(llm_answers: Dict[str, str], questions: List[Dict], resolved_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate LLM answers to ensure they have sufficient contextual evidence.
    Reject answers that are based on assumptions rather than clear context.
    """
    validated_answers = {}
    
    for question in questions:
        question_id = question.get('id', f'question_{questions.index(question) + 1}')
        question_text = question.get('question', '').lower()
        
        # Check if LLM provided an answer for this question
        if question_id in llm_answers:
            answer = llm_answers[question_id]
            
            # Define validation rules for different question types
            is_valid = False
            
            # Importer type questions - require explicit context
            if 'importer' in question_text or 'type' in question_text:
                # Only accept if there's explicit importer context
                if 'importer_type' in resolved_context:
                    is_valid = True
                else:
                    print(f"│       └── ❌ Rejected LLM answer for {question_id}: No importer context available")
            
            # Vehicle age questions - require year/age context
            elif 'age' in question_text or 'old' in question_text or 'year' in question_text:
                # Only accept if there's age context
                if 'product_age_category' in resolved_context:
                    is_valid = True
                else:
                    print(f"│       └── ❌ Rejected LLM answer for {question_id}: No age context available")
            
            # Propulsion questions - require propulsion context
            elif 'propulsion' in question_text or 'motor' in question_text or 'electric' in question_text:
                # Only accept if there's propulsion context
                if 'product_specifications' in resolved_context:
                    is_valid = True
                else:
                    print(f"│       └── ❌ Rejected LLM answer for {question_id}: No propulsion context available")
            
            # For other questions, be more permissive but still check for basic context
            else:
                # Accept if there's any relevant context
                if resolved_context:
                    is_valid = True
                else:
                    print(f"│       └── ❌ Rejected LLM answer for {question_id}: No context available")
            
            if is_valid:
                validated_answers[question_id] = answer
                print(f"│       └── ✅ Accepted LLM answer for {question_id}: {answer}")
            else:
                print(f"│       └── ❌ Rejected LLM answer for {question_id}: {answer} (insufficient context)")
    
    return validated_answers

def stage8_show_context(stage7_results: dict, original_query: str, order_id: str = None, user_answers: dict = None) -> dict:
    """
    Stage 8: User Input Interface
    Displays unanswered questions and provides interface for user to provide additional information.
    """
    results = {}
    
    print(f"\n📋 STAGE 8: USER INPUT INTERFACE")
    print("-" * 50)
    
    for hs_code, stage7_data in stage7_results.items():
        print(f"\n├── {hs_code}: User input interface")
        
        if stage7_data.get('status') == 'user_input_needed':
            unanswered_questions = stage7_data.get('unanswered_questions', [])
            answered_questions = stage7_data.get('answered_questions', {})
            
            # Check if user answers are provided
            if user_answers:
                print(f"│   └── [USER ANSWERS PROVIDED] Processing {len(user_answers)} answers:")
                
                # Process user answers
                processed_answers = {}
                for question in unanswered_questions:
                    question_id = question.get('id', f'question_{unanswered_questions.index(question) + 1}')
                    if question_id in user_answers:
                        answer = user_answers[question_id]
                        processed_answers[question_id] = answer
                        print(f"│       ✅ {question_id}: {answer}")
                
                # Combine with existing answers
                all_answers = {**answered_questions, **processed_answers}
                
                # Check if all questions are now answered
                remaining_unanswered = []
                for question in unanswered_questions:
                    question_id = question.get('id', f'question_{unanswered_questions.index(question) + 1}')
                    if question_id not in all_answers:
                        remaining_unanswered.append(question)
                
                if remaining_unanswered:
                    print(f"│   └── [PARTIAL ANSWERS] {len(remaining_unanswered)} questions still need answers")
                    results[hs_code] = {
                        'stage': 8,
                        'status': 'partial_answers',
                        'unanswered_questions': remaining_unanswered,
                        'answered_questions': all_answers,
                        'all_questions': stage7_data.get('all_questions', []),
                        'commodity_codes': stage7_data.get('commodity_codes', []),
                        'resolved_context': stage7_data.get('resolved_context', {}),
                        'original_query': original_query,
                        'order_id': order_id,
                        'message': f'{len(remaining_unanswered)} questions still need user input'
                    }
                else:
                    print(f"│   └── [ALL ANSWERS PROVIDED] All questions answered, proceeding to final classification")
                    results[hs_code] = {
                        'stage': 8,
                        'status': 'all_answers_provided',
                        'answered_questions': all_answers,
                        'unanswered_questions': unanswered_questions,
                        'all_questions': stage7_data.get('all_questions', []),
                        'commodity_codes': stage7_data.get('commodity_codes', []),
                        'resolved_context': stage7_data.get('resolved_context', {}),
                        'original_query': original_query,
                        'order_id': order_id,
                        'message': 'All questions answered - ready for final classification'
                    }
            else:
                print(f"│   └── [USER INPUT REQUIRED] {len(unanswered_questions)} questions need answers:")
                
                for i, question in enumerate(unanswered_questions, 1):
                    question_text = question.get('question', 'N/A')
                    options = question.get('options', [])
                    option_values = [opt.get('value', 'N/A') for opt in options]
                    print(f"│       {i}. {question_text}")
                    print(f"│          Options: {' / '.join(option_values)}")
                
                print(f"│   └── [INSTRUCTIONS] Please provide answers in user_answers field")
                print(f"│       Example: {{'question_1': 'Individual', 'question_2': 'Three years or less'}}")
                
                results[hs_code] = {
                    'stage': 8,
                    'status': 'user_input_required',
                    'unanswered_questions': unanswered_questions,
                    'answered_questions': answered_questions,
                    'all_questions': stage7_data.get('all_questions', []),
                    'commodity_codes': stage7_data.get('commodity_codes', []),
                    'resolved_context': stage7_data.get('resolved_context', {}),
                    'original_query': original_query,
                    'order_id': order_id,
                    'message': f'{len(unanswered_questions)} questions require user input'
                }
            
        elif stage7_data.get('status') == 'all_answered':
            print(f"│   └── [NO INPUT NEEDED] All questions already answered")
            print(f"│       Proceeding to final classification...")
            
            results[hs_code] = {
                'stage': 8,
                'status': 'no_input_needed',
                'answered_questions': stage7_data.get('answered_questions', {}),
                'all_questions': stage7_data.get('all_questions', []),
                'commodity_codes': stage7_data.get('commodity_codes', []),
                'resolved_context': stage7_data.get('resolved_context', {}),
                'original_query': original_query,
                'order_id': order_id,
                'message': 'All questions answered - no user input required'
            }
        else:
            print(f"│   └── [SKIP] No context to display (status: {stage7_data.get('status')})")
            results[hs_code] = {
                'stage': 8,
                'status': 'no_context',
                'stage7_data': stage7_data,
                'message': 'No context to display'
            }
    
    return results

def stage9_complete_loop(stage8_results: dict, stage5_results: dict = None, user_answers: dict = None) -> dict:
    """
    Stage 9: Complete the Loop
    Takes user answers and combines with existing context to provide LLM with 
    complete context for final analysis.
    """
    results = {}
    
    print(f"\n🔄 STAGE 9: COMPLETE THE LOOP")
    print("-" * 50)
    
    for hs_code, stage8_data in stage8_results.items():
        print(f"\n├── {hs_code}: Completing the loop with user answers")
        
        # Handle both 'context_displayed' and 'all_answers_provided' statuses
        if stage8_data.get('status') in ['context_displayed', 'all_answers_provided']:
            answered_questions = stage8_data.get('answered_questions', {})
            unanswered_questions = stage8_data.get('unanswered_questions', [])
            resolved_context = stage8_data.get('resolved_context', {})
            
            # Combine existing answers with user answers
            complete_answers = answered_questions.copy()
            
            if user_answers:
                print(f"│   └── [USER ANSWERS] Adding {len(user_answers)} user-provided answers")
                complete_answers.update(user_answers)
            else:
                print(f"│   └── [NO USER ANSWERS] Using only context-derived answers")
            
            # Display the complete context (Stage 5 + Stage 8 combined)
            print(f"│   └── [COMPLETE CONTEXT] Displaying full context:")
            
            # Stage 5 context (initial context)
            if stage5_results:
                print(f"│       ├── 📋 INITIAL CONTEXT (Stage 5):")
                stage5_context = stage5_results.get('contextual_data', {})
                stage1_results = stage5_results.get('stage1_results', {})
                
                if stage5_context:
                    if stage5_context.get('user_query'):
                        print(f"│       │   ├── User query: {stage5_context['user_query']}")
                    if stage5_context.get('invoice_data'):
                        invoice = stage5_context['invoice_data']
                        print(f"│       │   ├── Invoice: {invoice.get('invoice_number', 'N/A')} - {invoice.get('supplier', 'N/A')}")
                    if stage5_context.get('bill_of_lading'):
                        bol = stage5_context['bill_of_lading']
                        print(f"│       │   ├── Bill of Lading: {bol.get('bol_number', 'N/A')} - {bol.get('vessel', 'N/A')}")
                
                if stage1_results:
                    product_info = stage1_results.get('product_information', 'N/A')
                    print(f"│       │   └── Generated product data: {product_info}")
            else:
                print(f"│       ├── 📋 INITIAL CONTEXT (Stage 5): No initial context available")
            
            # Stage 8 context (user answers)
            print(f"│       └── 💬 USER ENHANCED CONTEXT (Stage 8):")
            if complete_answers:
                for q_id, answer in complete_answers.items():
                    # Find the question text
                    question_text = "Unknown question"
                    all_questions = stage8_data.get('all_questions', [])
                    for q in all_questions:
                        if q.get('id') == q_id:
                            question_text = q.get('question', 'Unknown question')
                            break
                    print(f"│           ├── Q: {question_text}")
                    print(f"│           └── A: {answer}")
            else:
                print(f"│           └── No user answers provided")
            
            # Check if we have answers for all questions
            all_questions = stage8_data.get('all_questions', [])
            missing_answers = []
            
            for i, question in enumerate(all_questions, 1):
                question_id = question.get('id', f'question_{i}')
                if question_id not in complete_answers:
                    missing_answers.append(question)
            
            if missing_answers:
                print(f"│   └── [INCOMPLETE] {len(missing_answers)} questions still unanswered")
                print(f"│       Missing answers for:")
                for q in missing_answers:
                    print(f"│           - {q.get('question', 'N/A')}")
                
                results[hs_code] = {
                    'stage': 9,
                    'status': 'incomplete_answers',
                    'complete_answers': complete_answers,
                    'missing_answers': missing_answers,
                    'resolved_context': resolved_context,
                    'commodity_codes': stage8_data.get('commodity_codes', []),
                    'message': f'Still missing {len(missing_answers)} answers'
                }
            else:
                print(f"│   └── [COMPLETE] All questions answered - ready for final selection")
                
                # Build complete context for final analysis (combining Stage 5 + Stage 8)
                complete_context = {
                    'stage5_context': stage5_results,
                    'stage8_context': stage8_data,
                    'resolved_context': resolved_context,
                    'answered_questions': complete_answers,
                    'original_query': stage8_data.get('original_query', ''),
                    'order_id': stage8_data.get('order_id')
                }
                
                results[hs_code] = {
                    'stage': 9,
                    'status': 'complete',
                    'complete_answers': complete_answers,
                    'complete_context': complete_context,
                    'resolved_context': resolved_context,
                    'commodity_codes': stage8_data.get('commodity_codes', []),
                    'stage5_context': stage5_results,
                    'message': 'All questions answered - ready for final selection'
                }
        else:
            print(f"│   └── [SKIP] No context to complete (status: {stage8_data.get('status')})")
            results[hs_code] = {
                'stage': 9,
                'status': 'no_completion_needed',
                'stage8_data': stage8_data,
                'message': 'No completion needed'
            }
    
    return results

def stage10_final_selection(stage9_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 10: Final Code Selection
    Takes all commodity codes, complete context, and answered questions and uses 
    LLM to select the best commodity code.
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=True)
    results = {}
    
    print(f"\n🎯 STAGE 10: FINAL CODE SELECTION")
    print("-" * 50)
    
    for hs_code, stage9_data in stage9_results.items():
        print(f"\n├── {hs_code}: Performing final code selection")
        
        if stage9_data.get('status') == 'complete':
            commodity_codes = stage9_data.get('commodity_codes', [])
            complete_context = stage9_data.get('complete_context', {})
            complete_answers = stage9_data.get('complete_answers', {})
            
            print(f"│   └── [SELECTION] Selecting from {len(commodity_codes)} commodity codes")
            print(f"│       └── Using Stage 9 complete context:")
            print(f"│           ├── Stage 3: {len(commodity_codes)} commodity codes")
            print(f"│           ├── Stage 4: Classification questions and context")
            print(f"│           └── Stage 9: Complete context with {len(complete_answers)} answered questions")
            
            # Filter codes based on answers if needed
            filtered_codes = commodity_codes.copy()
            
            # Apply filters based on answers
            if complete_answers:
                print(f"│       └── [FILTERING] Applying filters based on answers...")
                
                # Extract filter criteria from answers
                importer_filter = None
                age_filter = None
                
                for q_id, answer in complete_answers.items():
                    # Find the question to get its text
                    question_text = ""
                    for q in stage9_data.get('all_questions', []):
                        if q.get('id') == q_id:
                            question_text = q.get('question', '').lower()
                            break
                    
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
                
                # Apply filters
                if importer_filter or age_filter:
                    original_count = len(filtered_codes)
                    filtered_codes = [
                        code for code in filtered_codes
                        if (not importer_filter or importer_filter in code['description'].lower()) and
                           (not age_filter or age_filter in code['description'].lower())
                    ]
                    print(f"│           └── Filtered from {original_count} to {len(filtered_codes)} codes")
            
            # Select final code
            if len(filtered_codes) == 1:
                print(f"│       └── [DIRECT] Only one code remaining - selecting directly")
                final_code = filtered_codes[0]
                selection_method = 'direct_selection'
            else:
                print(f"│       └── [LLM] Using enhanced LLM prompt with comprehensive context from {len(filtered_codes)} codes")
                
                # Use LLM to select best match
                final_code = lookup.select_best_commodity_code(
                    hs_code, filtered_codes, product_name, product_info_text, complete_context
                )
                selection_method = 'llm_selection'
            
            if final_code:
                print(f"│       └── ✅ SELECTED: {final_code['tariff_code']}")
                print(f"│           └── Description: {final_code['description']}")
                
                results[hs_code] = {
                    'stage': 10,
                    'status': 'selected',
                    'final_code': final_code,
                    'selection_method': selection_method,
                    'complete_context': complete_context,
                    'complete_answers': complete_answers,
                    'filtered_codes': filtered_codes,
                    'message': f'Selected {final_code["tariff_code"]} using {selection_method}'
                }
            else:
                print(f"│       └── ❌ REJECTED: LLM rejected all codes as inappropriate")
                results[hs_code] = {
                    'stage': 10,
                    'status': 'rejected',
                    'complete_context': complete_context,
                    'complete_answers': complete_answers,
                    'filtered_codes': filtered_codes,
                    'message': 'LLM rejected all codes as inappropriate'
                }
        else:
            print(f"│   └── [SKIP] No complete context for selection (status: {stage9_data.get('status')})")
            results[hs_code] = {
                'stage': 10,
                'status': 'no_selection_needed',
                'stage9_data': stage9_data,
                'message': 'No final selection needed'
            }
    
    return results

def run_10_stage_workflow(hs_codes: list[str], product_name: str, product_info_text: str, 
                         original_question: str = "", order_id: str = None, 
                         contextual_data: Dict[str, Any] = None, user_answers: dict = None,
                         stage1_results: dict = None) -> dict:
    """
    Run the complete 10-stage commodity code workflow.
    
    Args:
        hs_codes: List of HS codes (may have dots like ["0706.10"])
        product_name: Name of the product
        product_info_text: Additional product information
        original_question: The original user question
        order_id: Order ID for context lookup
        contextual_data: Direct contextual data from request
        user_answers: User-provided answers to unanswered questions
        
    Returns:
        Dictionary with final results from all stages
    """
    print(f"\n🚀 RUNNING 10-STAGE COMMODITY CODE WORKFLOW")
    print("=" * 70)
    
    # Stage 3: Simple commodity code lookup
    stage3_results = stage3_commodity_lookup(hs_codes)
    
    # Stage 4: Generate classification questions
    stage4_results = stage4_generate_questions(stage3_results, product_name, product_info_text)
    
    # Stage 5: Context resolution
    stage5_results = stage5_resolve_context(stage1_results, original_question, order_id, contextual_data, product_name)
    
    # Stage 6: Answer questions with LLM
    stage6_results = stage6_llm_answer_questions(stage4_results, stage5_results, product_name, product_info_text)
    
    # Stage 7: List unanswered questions
    stage7_results = stage7_list_unanswered(stage6_results)
    
    # Check if we need user input
    needs_user_input = False
    for hs_code, stage7_data in stage7_results.items():
        if stage7_data.get('status') == 'user_input_needed':
            needs_user_input = True
            break
    
    if needs_user_input and not user_answers:
        # Pause workflow - return results up to Stage 7 for user input
        print(f"\n⏸️  WORKFLOW PAUSED - USER INPUT REQUIRED")
        print("=" * 50)
        print("Please provide answers to the unanswered questions")
        print("Use the /classify/continue endpoint with user_answers parameter")
        
        # Convert to clarification format (consistent with normal return)
        final_results = {}
        for hs_code in hs_codes:
            stage7_data = stage7_results.get(hs_code, {})
            if stage7_data.get('status') == 'user_input_needed':
                final_results[hs_code] = {
                    'requires_clarification': True,
                    'reasoning': 'User input needed for clarification questions',
                    'missing_info': [q['question'] for q in stage7_data.get('unanswered_questions', [])],
                    'questions': stage7_data.get('unanswered_questions', []),
                    'available_codes': stage7_data.get('commodity_codes', []),
                    'original_question': original_question,
                    'code_count': len(stage7_data.get('commodity_codes', []))
                }
            else:
                final_results[hs_code] = []
        
        return final_results
    
    # Stage 8: Show additional context (only if no user input needed or user answers provided)
    stage8_results = stage8_show_context(stage7_results, original_question, order_id, user_answers)
    
    # Stage 9: Complete the loop
    stage9_results = stage9_complete_loop(stage8_results, stage5_results, user_answers)
    
    # Stage 10: Final code selection
    stage10_results = stage10_final_selection(stage9_results, product_name, product_info_text)
    
    # Compile final results
    final_results = {}
    for hs_code in hs_codes:
        stage10_data = stage10_results.get(hs_code, {})
        
        if stage10_data.get('status') == 'selected':
            final_results[hs_code] = [stage10_data['final_code']]
        elif stage10_data.get('status') == 'rejected':
            final_results[hs_code] = []
        else:
            # Check if we need clarification
            stage7_data = stage7_results.get(hs_code, {})
            if stage7_data.get('status') == 'user_input_needed':
                final_results[hs_code] = {
                    'requires_clarification': True,
                    'reasoning': 'User input needed for clarification questions',
                    'missing_info': [q['question'] for q in stage7_data.get('unanswered_questions', [])],
                    'questions': stage7_data.get('unanswered_questions', []),
                    'available_codes': stage7_data.get('commodity_codes', []),
                    'original_question': original_question,
                    'code_count': len(stage7_data.get('commodity_codes', []))
                }
            else:
                # Pass through other results
                final_results[hs_code] = stage10_data
    
    print(f"\n🎉 10-STAGE WORKFLOW COMPLETED")
    print("=" * 70)
    
    return final_results

# ═══════════════════════════════════════════════════════════════════════════════
# CORE SUPPORTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _process_direct_context(contextual_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process direct contextual data into standardized format for classification.
    """
    print(f"\n🔄 PROCESSING DIRECT CONTEXTUAL DATA")
    print("-" * 50)
    
    processed_context = {}
    
    # Process user query (for individual user requests)
    user_query = contextual_data.get('user_query', '')
    if user_query:
        print(f"✅ Processing user query: {user_query}")
        # Extract context from user query using the same logic as extract_context_from_query
        query_context = extract_context_from_query(user_query, "", "")
        processed_context.update(query_context)
        print(f"✅ Extracted context from user query: {list(query_context.keys())}")
    
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

def map_context_to_answers(questions: List[Dict], extracted_context: Dict[str, Any]) -> Dict[str, str]:
    """
    Map extracted context directly to question answers using predefined mappings.
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
        # Extract option values for comparison (handle both string and dict formats)
        option_values = []
        for option in question_options:
            if isinstance(option, dict):
                option_values.append(option.get('value', option.get('label', '')))
            else:
                option_values.append(option)
        
        if answer and answer in option_values:
            # Find the matching option and use its value
            for option in question_options:
                if isinstance(option, dict):
                    if option.get('value') == answer or option.get('label') == answer:
                        answers[question_id] = option.get('value', answer)
                        break
                else:
                    if option == answer:
                        answers[question_id] = answer
                        break
            print(f"   ✅ Mapped to: {answer}")
        elif answer:
            # Try to find partial match
            for option in question_options:
                option_text = option.get('value', option.get('label', '')) if isinstance(option, dict) else option
                if answer.lower() in option_text.lower() or option_text.lower() in answer.lower():
                    answers[question_id] = option.get('value', option_text) if isinstance(option, dict) else option
                    print(f"   ✅ Partial match: {option_text}")
                    break
            else:
                print(f"   ❌ No match found for: {answer}")
        else:
            print(f"   ❌ No context mapping available")
    
    print(f"\n📊 MAPPING RESULTS: {len(answers)}/{len(questions)} questions answered")
    return answers

def extract_context_from_query(original_question: str, product_name: str, product_info_text: str) -> Dict[str, Any]:
    """
    Extract context information from user query and product information for auto-answering clarification questions.
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

def get_order_context_by_id(order_id: int) -> Dict[str, Any]:
    """
    Retrieve order context (BOL and invoice data) by order ID and extract structured context.
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

def chat_completion(messages, model_alias="mistral_small"):
    """
    Handle LLM API calls for single model classification.
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

def call_llm(messages, model_alias, config, models):
    """
    Make the actual HTTP request to the LLM API.
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

# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT CONTEXT EXTRACTOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentContextExtractor:
    """
    Extract structured context from BOL and invoice documents for auto-answering clarification questions.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_context_from_documents(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured context from BOL and invoice data.
        """
        context = {}
        
        print(f"\n📋 EXTRACTING CONTEXT FROM DOCUMENTS")
        print("-" * 50)
        
        # Extract importer type from invoice buyer information
        importer_type = self._extract_importer_type(invoice_data)
        if importer_type:
            context['importer_type'] = importer_type
            print(f"✅ Extracted importer type: {importer_type}")
        
        # Extract vehicle age from BOL commodity description
        vehicle_age = self._extract_vehicle_age(bol_data)
        if vehicle_age:
            context['product_age_category'] = vehicle_age
            print(f"✅ Extracted vehicle age: {vehicle_age}")
        
        # Extract propulsion type from commodity description
        propulsion_type = self._extract_propulsion_type(bol_data, invoice_data)
        if propulsion_type:
            context['product_specifications'] = {'battery_type': propulsion_type}
            print(f"✅ Extracted propulsion type: {propulsion_type}")
        
        # Extract usage purpose from buyer information
        usage_purpose = self._extract_usage_purpose(invoice_data)
        if usage_purpose:
            context['usage_purpose'] = usage_purpose
            print(f"✅ Extracted usage purpose: {usage_purpose}")
        
        # Extract value category from invoice totals
        value_category = self._extract_value_category(invoice_data)
        if value_category:
            context['value_category'] = value_category
            print(f"✅ Extracted value category: {value_category}")
        
        # Extract quantity information
        quantity_info = self._extract_quantity_info(bol_data, invoice_data)
        if quantity_info:
            context['quantity_category'] = quantity_info
            print(f"✅ Extracted quantity category: {quantity_info}")
        
        print(f"\n📊 EXTRACTED CONTEXT: {context}")
        return context
    
    def _extract_importer_type(self, invoice_data: Dict[str, Any]) -> Optional[str]:
        """Extract importer type from invoice buyer information."""
        try:
            buyer = invoice_data.get('buyer', {})
            buyer_name = buyer.get('name', '').upper()
            
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
            
        except Exception as e:
            self.logger.error(f"Error extracting importer type: {e}")
            return None
    
    def _extract_vehicle_age(self, bol_data: Dict[str, Any]) -> Optional[str]:
        """Extract vehicle age from BOL commodity description."""
        try:
            commodity = bol_data.get('commodity', '').upper()
            
            # Look for year patterns in commodity description
            year_match = re.search(r'\b(20\d{2})\b', commodity)
            if year_match:
                year = int(year_match.group(1))
                current_year = datetime.now().year
                age_years = current_year - year
                
                if age_years <= 3:
                    return 'three_years_and_less'
                else:
                    return 'exceeding_three_years'
            
            # Look for age indicators in text
            if any(keyword in commodity for keyword in ['NEW', 'CURRENT', 'LATEST']):
                return 'three_years_and_less'
            elif any(keyword in commodity for keyword in ['OLD', 'USED', 'SECOND']):
                return 'exceeding_three_years'
            
            return 'three_years_and_less'  # Default for new purchases
            
        except Exception as e:
            self.logger.error(f"Error extracting vehicle age: {e}")
            return None
    
    def _extract_propulsion_type(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> Optional[str]:
        """Extract propulsion type from commodity description and invoice details."""
        try:
            # Check BOL commodity description
            commodity = bol_data.get('commodity', '').lower()
            
            # Check invoice product details
            invoice_items = invoice_data.get('items', [])
            product_descriptions = []
            for item in invoice_items:
                description = item.get('description', '').lower()
                product_descriptions.append(description)
            
            combined_text = commodity + " " + " ".join(product_descriptions)
            
            # Look for electric vehicle indicators
            electric_indicators = [
                'electric', 'battery', 'tesla', 'ev', 'electric motor',
                'lithium', 'lfp', 'solar', 'hybrid'
            ]
            
            if any(indicator in combined_text for indicator in electric_indicators):
                return 'lithium_ion'
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting propulsion type: {e}")
            return None
    
    def _extract_usage_purpose(self, invoice_data: Dict[str, Any]) -> Optional[str]:
        """Extract usage purpose from buyer information."""
        try:
            buyer = invoice_data.get('buyer', {})
            buyer_address = buyer.get('address', '').lower()
            
            # Check for residential vs commercial address patterns
            if any(word in buyer_address for word in ['st', 'street', 'ave', 'avenue', 'rd', 'road']):
                return 'personal'
            
            # Check for commercial indicators
            commercial_indicators = ['business', 'commercial', 'industrial', 'office', 'company']
            if any(indicator in buyer_address for indicator in commercial_indicators):
                return 'commercial'
            
            return 'personal'  # Default assumption
            
        except Exception as e:
            self.logger.error(f"Error extracting usage purpose: {e}")
            return None
    
    def _extract_value_category(self, invoice_data: Dict[str, Any]) -> Optional[str]:
        """Extract value category from invoice totals."""
        try:
            totals = invoice_data.get('totals', {})
            total_amount = totals.get('total_amount', 0)
            
            if total_amount < 500:
                return 'low_value'
            elif total_amount < 2000:
                return 'medium_value'
            elif total_amount < 10000:
                return 'high_value'
            else:
                return 'very_high_value'
                
        except Exception as e:
            self.logger.error(f"Error extracting value category: {e}")
            return None
    
    def _extract_quantity_info(self, bol_data: Dict[str, Any], invoice_data: Dict[str, Any]) -> Optional[str]:
        """Extract quantity information from BOL and invoice."""
        try:
            # Try to get quantity from BOL first
            bol_packages = bol_data.get('packages', [])
            total_quantity = 0
            
            for package in bol_packages:
                quantity = package.get('quantity', 0)
                try:
                    total_quantity += int(quantity)
                except (ValueError, TypeError):
                    continue
            
            # If no BOL quantity, try invoice
            if total_quantity == 0:
                invoice_items = invoice_data.get('items', [])
                for item in invoice_items:
                    quantity = item.get('quantity', 0)
                    try:
                        total_quantity += int(quantity)
                    except (ValueError, TypeError):
                        continue
            
            # Categorize quantity
            if total_quantity == 0:
                return 'single_unit'  # Default
            elif total_quantity == 1:
                return 'single_unit'
            elif total_quantity <= 5:
                return 'small_quantity'
            elif total_quantity <= 20:
                return 'medium_quantity'
            else:
                return 'bulk_quantity'
                
        except Exception as e:
            self.logger.error(f"Error extracting quantity info: {e}")
            return 'single_unit'

# ═══════════════════════════════════════════════════════════════════════════════
# COMMODITY CODE LOOKUP CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class CommodityCodeLookup:
    """
    Main class for commodity code lookup and LLM-based selection.
    """
    
    def __init__(self, supabase_url: str, supabase_key: str, use_llm_selection: bool = True):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.use_llm_selection = use_llm_selection
        self.logger = logging.getLogger(__name__)
    
    def find_matching_codes(self, hs_code: str) -> List[Dict[str, Any]]:
        """
        Find all commodity codes that start with the given HS code.
        """
        try:
            # Clean the HS code (remove dots, ensure 6 digits)
            clean_hs_code = hs_code.replace('.', '').zfill(6)
            
            # Query Supabase for matching codes
            response = self.supabase.table('tariff_codes').select('*').ilike('tariff_code', f'{clean_hs_code}%').execute()
            
            if response.data:
                self.logger.info(f"Found {len(response.data)} matching codes for HS {hs_code}")
                return response.data
            else:
                self.logger.warning(f"No matching codes found for HS {hs_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error finding matching codes for {hs_code}: {e}")
            return []
    
    def find_single_code(self, hs_code: str) -> Optional[Dict[str, Any]]:
        """
        Find a single commodity code that exactly matches the HS code.
        """
        try:
            # Clean the HS code (remove dots, ensure 6 digits)
            clean_hs_code = hs_code.replace('.', '').zfill(6)
            
            # Query Supabase for exact match
            response = self.supabase.table('tariff_codes').select('*').eq('tariff_code', clean_hs_code).execute()
            
            if response.data:
                self.logger.info(f"Found exact match for HS {hs_code}")
                return response.data[0]
            else:
                self.logger.warning(f"No exact match found for HS {hs_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error finding single code for {hs_code}: {e}")
            return None
    
    def extract_classification_attributes(self, commodity_codes: List[Dict[str, Any]]) -> List[str]:
        """
        Extract distinguishing attributes from commodity codes for question generation.
        """
        attributes = set()
        
        for code in commodity_codes:
            description = code.get('description', '').lower()
            
            # Check for importer type indicators
            if any(keyword in description for keyword in ['individual', 'dealer']):
                attributes.add('importer_type')
            
            # Check for age indicators
            if any(keyword in description for keyword in ['three years', 'exceeding three years']):
                attributes.add('vehicle_age')
            
            # Check for propulsion type indicators
            if any(keyword in description for keyword in ['electric', 'motor', 'propulsion']):
                attributes.add('propulsion_type')
            
            # Check for usage purpose indicators
            if any(keyword in description for keyword in ['personal', 'commercial', 'use']):
                attributes.add('usage_purpose')
            
            # Check for value indicators
            if any(keyword in description for keyword in ['value', 'price', 'cost']):
                attributes.add('value_category')
            
            # Check for quantity indicators
            if any(keyword in description for keyword in ['single', 'bulk', 'quantity']):
                attributes.add('quantity_category')
        
        return list(attributes)
    
    def generate_questions_for_attributes(self, attributes: List[str], product_name: str, product_info_text: str) -> List[Dict[str, Any]]:
        """
        Generate clarification questions based on distinguishing attributes.
        """
        questions = []
        
        for i, attribute in enumerate(attributes, 1):
            if attribute == 'importer_type':
                questions.append({
                    'id': f'question_{i}',
                    'question': 'What type of importer are you?',
                    'type': 'choice',
                    'options': [
                        {'value': 'Individual', 'label': 'Individual'},
                        {'value': 'Dealer', 'label': 'Dealer'}
                    ],
                    'attribute': attribute
                })
            
            elif attribute == 'vehicle_age':
                questions.append({
                    'id': f'question_{i}',
                    'question': 'How old is the vehicle since manufacture?',
                    'type': 'choice',
                    'options': [
                        {'value': 'Three years or less since manufacture', 'label': 'Three years or less since manufacture'},
                        {'value': 'Exceeding three years since manufacture', 'label': 'Exceeding three years since manufacture'}
                    ],
                    'attribute': attribute
                })
            
            elif attribute == 'propulsion_type':
                questions.append({
                    'id': f'question_{i}',
                    'question': 'What type of propulsion system does the vehicle have?',
                    'type': 'choice',
                    'options': [
                        {'value': 'Only electric motor', 'label': 'Only electric motor'},
                        {'value': 'Other propulsion system', 'label': 'Other propulsion system'}
                    ],
                    'attribute': attribute
                })
            
            elif attribute == 'usage_purpose':
                questions.append({
                    'id': f'question_{i}',
                    'question': 'What is the intended usage of the vehicle?',
                    'type': 'choice',
                    'options': [
                        {'value': 'Personal use', 'label': 'Personal use'},
                        {'value': 'Commercial use', 'label': 'Commercial use'}
                    ],
                    'attribute': attribute
                })
            
            elif attribute == 'value_category':
                questions.append({
                    'id': f'question_{i}',
                    'question': 'What is the approximate value of the vehicle?',
                    'type': 'choice',
                    'options': [
                        {'value': 'Low value (under $500)', 'label': 'Low value (under $500)'},
                        {'value': 'Medium value ($500-$2000)', 'label': 'Medium value ($500-$2000)'},
                        {'value': 'High value ($2000-$10000)', 'label': 'High value ($2000-$10000)'},
                        {'value': 'Very high value (over $10000)', 'label': 'Very high value (over $10000)'}
                    ],
                    'attribute': attribute
                })
            
            elif attribute == 'quantity_category':
                questions.append({
                    'id': f'question_{i}',
                    'question': 'How many units are you importing?',
                    'type': 'choice',
                    'options': [
                        {'value': 'Single unit', 'label': 'Single unit'},
                        {'value': 'Small quantity (2-5 units)', 'label': 'Small quantity (2-5 units)'},
                        {'value': 'Medium quantity (6-20 units)', 'label': 'Medium quantity (6-20 units)'},
                        {'value': 'Bulk quantity (20+ units)', 'label': 'Bulk quantity (20+ units)'}
                    ],
                    'attribute': attribute
                })
        
        return questions
    
    def select_best_commodity_code(self, hs_code: str, commodity_codes: List[Dict[str, Any]], 
                                 product_name: str, product_info_text: str, 
                                 context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Use LLM to select the best commodity code from the available options.
        """
        if not self.use_llm_selection:
            # Return first code if LLM selection is disabled
            return commodity_codes[0] if commodity_codes else None
        
        try:
            # Build context information using Stage 9 complete context
            context_info = ""
            
            if context:
                # Resolved Context (Processed Business Data from Stage 9 Complete Context)
                resolved_context = context.get('resolved_context', {})
                if resolved_context:
                    context_info += f"\n\n🔍 BUSINESS CONTEXT (Stage 9 Complete Context):\n"
                    for key, value in resolved_context.items():
                        context_info += f"- {key.replace('_', ' ').title()}: {value}\n"
                
                # Complete Answers (User + LLM Responses from Stage 9)
                answered_questions = context.get('answered_questions', {})
                if answered_questions:
                    context_info += f"\n\n✅ CLASSIFICATION ANSWERS (Stage 9 Complete Context):\n"
                    for q_id, answer in answered_questions.items():
                        # Find the question text for better context
                        question_text = "Unknown question"
                        stage8_context = context.get('stage8_context', {})
                        if stage8_context:
                            all_questions = stage8_context.get('all_questions', [])
                            for q in all_questions:
                                if q.get('id') == q_id:
                                    question_text = q.get('question', 'Unknown question')
                                    break
                        context_info += f"- Q: {question_text}\n"
                        context_info += f"  A: {answer}\n"
                
                # Additional Context
                if context.get('original_query'):
                    context_info += f"\n\n📝 Original Query: {context['original_query']}\n"
                if context.get('order_id'):
                    context_info += f"📋 Order ID: {context['order_id']}\n"
            
            # Create the enhanced prompt with complete structured data
            prompt = f"""
You are an expert HS Code classification specialist for Jamaican customs. You have access to comprehensive business context and user responses to make the most accurate classification decision.

🎯 CLASSIFICATION TASK:
HS Code: {hs_code}
Product: {product_name}
Product Information: {product_info_text}
{context_info}

📋 AVAILABLE COMMODITY CODES (Stage 3 Database Lookup Results):
"""
            
            for i, code in enumerate(commodity_codes, 1):
                prompt += f"{i}. {code['tariff_code']} - {code['description']}\n"
            
            # Add the classification questions from Stage 9 complete context
            stage8_context = context.get('stage8_context', {})
            all_questions = stage8_context.get('all_questions', [])
            if all_questions:
                prompt += f"""

❓ CLASSIFICATION QUESTIONS (From Stage 9 Complete Context):
The following questions were generated to distinguish between the commodity codes above:
"""
                for i, question in enumerate(all_questions, 1):
                    question_text = question.get('question', 'N/A')
                    options = question.get('options', [])
                    attribute = question.get('attribute', 'unknown')
                    option_text = ', '.join([opt.get('value', 'N/A') for opt in options])
                    prompt += f"{i}. {question_text}\n"
                    prompt += f"   Attribute: {attribute}\n"
                    prompt += f"   Options: {option_text}\n\n"
            
            prompt += f"""

🎯 ANALYSIS REQUIREMENTS:
Analyze the complete business context and user responses to select the most appropriate commodity code. Consider:

1. **Business Context**: Invoice details, shipping information, supplier data
2. **Product Characteristics**: Specific features, specifications, and usage  
3. **User Classification Answers**: Importer type, usage purpose, age restrictions
4. **Classification Questions**: The specific questions generated to distinguish between codes
5. **Regulatory Compliance**: Most precise and accurate classification
6. **Customs Requirements**: Jamaican customs regulations and requirements

🔍 DECISION CRITERIA:
- Match the product description with the most specific commodity code
- Apply user-provided classification answers (importer type, age, etc.)
- Consider the business context (supplier, shipping, invoice details)
- Use the classification questions to understand the distinguishing factors
- Ensure regulatory compliance and accuracy
- Select the most precise classification available

📤 RESPONSE FORMAT:
Respond with ONLY the number (1, 2, 3, etc.) of the most appropriate commodity code, or "REJECT" if none of the codes are appropriate for this product based on the comprehensive context provided.
"""
            
            # Call LLM
            response = reason_with_llm_fn(prompt, hs_code)
            
            if not response:
                self.logger.error("Empty response from LLM")
                return None
            
            # Parse response
            response = response.strip()
            
            if response.upper() == "REJECT":
                self.logger.info("LLM rejected all commodity codes as inappropriate")
                return None
            
            try:
                # Try to extract number from response
                import re
                number_match = re.search(r'\b(\d+)\b', response)
                if number_match:
                    selected_index = int(number_match.group(1)) - 1
                    if 0 <= selected_index < len(commodity_codes):
                        selected_code = commodity_codes[selected_index]
                        self.logger.info(f"LLM selected commodity code: {selected_code['tariff_code']}")
                        return selected_code
                    else:
                        self.logger.error(f"LLM selected invalid index: {selected_index}")
                        return None
                else:
                    self.logger.error(f"Could not parse number from LLM response: {response}")
                    return None
                    
            except (ValueError, IndexError) as e:
                self.logger.error(f"Error parsing LLM response: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in LLM selection: {e}")
            return None
    
    def _retry_with_alternative_llm(self, prompt: str, hs_code: str) -> Optional[Dict[str, Any]]:
        """
        Retry with alternative LLM if primary selection fails.
        """
        try:
            # Try with different model
            messages = [
                {"role": "system", "content": "You are an expert in HS Code classification. Always respond with just a number or 'REJECT'."},
                {"role": "user", "content": prompt}
            ]
            
            response = chat_completion(messages, model_alias="gpt4o_mini")
            
            if not response:
                return None
            
            response = response.strip()
            
            if response.upper() == "REJECT":
                return None
            
            # Parse response
            import re
            number_match = re.search(r'\b(\d+)\b', response)
            if number_match:
                selected_index = int(number_match.group(1)) - 1
                return selected_index
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error in alternative LLM retry: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY API FUNCTIONS (for backward compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def lookup_commodity_code(hs_codes: list[str], product_name: str, product_info_text: str, 
                         original_question: str = "", order_id: str = None, 
                         contextual_data: Dict[str, Any] = None, stage1_results: dict = None, user_answers: dict = None) -> dict:
    """
    Legacy function for commodity code lookup.
    Now uses the 10-stage workflow internally.
    """
    print(f"\n🔄 LEGACY API: lookup_commodity_code")
    print("=" * 50)
    
    # Use the new 10-stage workflow
    results = run_10_stage_workflow(
        hs_codes=hs_codes,
        product_name=product_name,
        product_info_text=product_info_text,
        original_question=original_question,
        order_id=order_id,
        contextual_data=contextual_data,
        stage1_results=stage1_results,
        user_answers=user_answers
    )
    
    # Convert results to legacy format
    legacy_results = {}
    for hs_code, result in results.items():
        if isinstance(result, list) and result:
            # Direct commodity code result
            legacy_results[hs_code] = result
        elif isinstance(result, dict) and result.get('requires_clarification'):
            # Clarification needed
            legacy_results[hs_code] = result
        else:
            # No results or other status
            legacy_results[hs_code] = []
    
    return legacy_results

def interactive_commodity_lookup(hs_codes: list[str], product_name: str, product_info_text: str, 
                               original_question: str = "", order_id: str = None, 
                               contextual_data: Dict[str, Any] = None) -> dict:
    """
    Legacy function for interactive commodity code lookup.
    Now uses the 10-stage workflow internally.
    """
    print(f"\n🔄 LEGACY API: interactive_commodity_lookup")
    print("=" * 50)
    
    # Use the new 10-stage workflow
    results = run_10_stage_workflow(
        hs_codes=hs_codes,
        product_name=product_name,
        product_info_text=product_info_text,
        original_question=original_question,
        order_id=order_id,
        contextual_data=contextual_data
    )
    
    # Convert results to legacy format
    legacy_results = {}
    for hs_code, result in results.items():
        if isinstance(result, list) and result:
            # Direct commodity code result
            legacy_results[hs_code] = result
        elif isinstance(result, dict) and result.get('requires_clarification'):
            # Clarification needed
            legacy_results[hs_code] = result
        else:
            # No results or other status
            legacy_results[hs_code] = []
    
    return legacy_results

def lookup_commodity_code_with_answers(hs_codes: list[str], product_name: str, product_info_text: str, 
                                     original_question: str = "", order_id: str = None, 
                                     contextual_data: Dict[str, Any] = None, user_answers: dict = None) -> dict:
    """
    Legacy function for commodity code lookup with user answers.
    Now uses the 10-stage workflow internally.
    """
    print(f"\n🔄 LEGACY API: lookup_commodity_code_with_answers")
    print("=" * 50)
    
    # Use the new 10-stage workflow with user answers
    results = run_10_stage_workflow(
        hs_codes=hs_codes,
        product_name=product_name,
        product_info_text=product_info_text,
        original_question=original_question,
        order_id=order_id,
        contextual_data=contextual_data,
        user_answers=user_answers
    )
    
    # Convert results to legacy format
    legacy_results = {}
    for hs_code, result in results.items():
        if isinstance(result, list) and result:
            # Direct commodity code result
            legacy_results[hs_code] = result
        elif isinstance(result, dict) and result.get('requires_clarification'):
            # Clarification needed
            legacy_results[hs_code] = result
        else:
            # No results or other status
            legacy_results[hs_code] = []
    
    return legacy_results

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commodity Code Lookup with LLM Selection")
    parser.add_argument("hs_codes", nargs="+", help="HS codes to look up (e.g., 8703.80)")
    parser.add_argument("--product-name", required=True, help="Name of the product")
    parser.add_argument("--product-info", default="", help="Additional product information")
    parser.add_argument("--original-question", default="", help="Original user question")
    parser.add_argument("--order-id", type=int, help="Order ID for context lookup")
    parser.add_argument("--use-10-stage", action="store_true", help="Use the new 10-stage workflow")
    parser.add_argument("--user-answers", help="JSON string of user answers")
    
    args = parser.parse_args()
    
    # Parse user answers if provided
    user_answers = None
    if args.user_answers:
        try:
            user_answers = json.loads(args.user_answers)
        except json.JSONDecodeError as e:
            print(f"Error parsing user answers: {e}")
            sys.exit(1)
    
    if args.use_10_stage:
        # Use the new 10-stage workflow
        results = run_10_stage_workflow(
            hs_codes=args.hs_codes,
            product_name=args.product_name,
            product_info_text=args.product_info,
            original_question=args.original_question,
            order_id=args.order_id,
            user_answers=user_answers
        )
    else:
        # Use legacy function
        results = lookup_commodity_code(
            hs_codes=args.hs_codes,
            product_name=args.product_name,
            product_info_text=args.product_info,
            original_question=args.original_question,
            order_id=args.order_id
        )
    
    # Print results
    print(f"\n🎉 FINAL RESULTS:")
    print("=" * 50)
    for hs_code, result in results.items():
        print(f"\nHS Code: {hs_code}")
        if isinstance(result, list) and result:
            print(f"✅ Found {len(result)} commodity code(s):")
            for code in result:
                print(f"   - {code['tariff_code']}: {code['description']}")
        elif isinstance(result, dict) and result.get('requires_clarification'):
            print(f"❓ Clarification needed:")
            print(f"   - {result['reasoning']}")
            print(f"   - Missing info: {result['missing_info']}")
        else:
            print(f"❌ No results found")
    
    # Save results to file
    output_file = f"commodity_lookup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")
