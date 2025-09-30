#!/usr/bin/env python3
"""
Commodity Code Lookup with LLM Selection - 10-Stage Workflow
------------------------------------------------------------

Look up Jamaican 10-digit tariff codes that start with the supplied 6-digit HS codes,
then use LLM reasoning to select the most appropriate commodity code for the product.

10-Stage Workflow:
- Stage 4: Commodity code lookup (list matching commodity codes)
- Stage 6: Generate classification questions  
- Stage 3: Context resolution
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

# Ensure stdout uses UTF-8 to avoid Windows console encoding errors
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 10-STAGE COMMODITY CODE WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

def lookup_commodity_codes(hs_codes: list[str]) -> dict:
    """
    Stage 4: Commodity code lookup - list all matching commodity codes.
    
    Args:
        hs_codes: List of HS codes (may have dots like ["0706.10"])
        
    Returns:
        Dictionary mapping HS codes to list of all matching commodity codes
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=False)
    results = {}
    
    print(f"\n📋 STAGE 4: COMMODITY CODE LOOKUP")
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

def generate_questions_from_codes(code_lookup_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 6: Generate Classification Questions
    Takes the commodity codes from Stage 5 as input and uses LLM to analyze 
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
    
    print(f"\n❓ STAGE 6: GENERATE CLASSIFICATION QUESTIONS")
    print("-" * 50)
    
    for hs_code, commodity_codes in code_lookup_results.items():
        print(f"\n├── {hs_code}: Analyzing {len(commodity_codes)} commodity codes")
        
        if not commodity_codes:
            print(f"│   └── [SKIP] No commodity codes to analyze")
            results[hs_code] = {
                'stage': 4,
                'status': 'no_codes',
                'message': 'No commodity codes found from lookup'
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
        
        # Use LLM to analyze codes and generate questions
        print(f"│   └── [LLM] Analyzing commodity codes to generate relevant questions...")
        questions = lookup.generate_classification_questions_with_llm(
            commodity_codes, product_name, product_info_text
        )
        
        if not questions:
            print(f"│   └── [DIRECT SELECTION] No distinguishing questions needed")
            # Use LLM to select best match directly
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
            print(f"│       └── Generated {len(questions)} relevant questions:")
            for i, q in enumerate(questions, 1):
                print(f"│           {i}. {q['question']} ({q.get('attribute', 'unknown')})")
            
            results[hs_code] = {
                'stage': 4,
                'status': 'questions_generated',
                'questions': questions,
                'commodity_codes': commodity_codes,
                'message': f'Generated {len(questions)} relevant classification questions'
            }
    
    return results

def resolve_context(stage1_results: dict, original_query: str, order_id: str = None, 
                          contextual_data: Dict[str, Any] = None, product_name: str = None) -> dict:
    """
    Stage 3: Context Resolution
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
    
    print(f"\n🔍 STAGE 3: CONTEXT")
    print("-" * 50)
    print(f"🔍 DEBUG: contextual_data = {contextual_data}")
    print(f"🔍 DEBUG: product_name = {product_name}")
    print(f"🔍 DEBUG: original_query = {original_query}")
    
    # 1. Product name (from intent parser)
    display_product_name = product_name if product_name else (stage1_results.get('product_name', 'N/A') if stage1_results else 'N/A')
    print(f"├── Product name (intent parser): {display_product_name}")
    
    # 2. Contextual data display (streamlined structure)
    if contextual_data:
        # Display streamlined structure fields first
        if contextual_data.get('consignee_name'):
            print(f"├── Consignee: {contextual_data['consignee_name']}")
        if contextual_data.get('shipper'):
            print(f"├── Shipper: {contextual_data['shipper']}")
        if contextual_data.get('port_of_origin'):
            print(f"├── Origin: {contextual_data['port_of_origin']}")
        if contextual_data.get('port_of_destination'):
            print(f"├── Destination: {contextual_data['port_of_destination']}")
        if contextual_data.get('commodity'):
            commodity_preview = contextual_data['commodity'][:60] + "..." if len(contextual_data['commodity']) > 60 else contextual_data['commodity']
            print(f"├── Commodity: {commodity_preview}")
        if contextual_data.get('weight'):
            print(f"├── Weight: {contextual_data['weight']}")
        if contextual_data.get('vessel'):
            print(f"├── Vessel: {contextual_data['vessel']}")
        if contextual_data.get('bill_of_lading'):
            print(f"├── BOL: {contextual_data['bill_of_lading']}")
        
        # Legacy support for nested structure
        if contextual_data.get('user_query'):
            print(f"├── User query: {contextual_data['user_query']}")
        if contextual_data.get('invoice_data'):
            invoice = contextual_data['invoice_data']
            print(f"├── Invoice: {invoice.get('invoice_number', 'N/A')} - {invoice.get('supplier', 'N/A')}")
        if contextual_data.get('bill_of_lading') and isinstance(contextual_data.get('bill_of_lading'), dict):
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

def gather_context(stage1_results: dict, original_query: str, order_id: str = None,
                          contextual_data: Dict[str, Any] = None, product_name: str = None) -> dict:
    """
    Stage 3: Context Resolution (moved from previous Stage 5)
    Wrapper that reuses the existing context display/processing.
    """
    res = resolve_context(stage1_results, original_query, order_id, contextual_data, product_name)
    res['stage'] = 3
    print(f"\n🔍 STAGE 3: CONTEXT")
    print("-" * 50)
    return res

def filter_codes_with_llm(code_lookup_results: dict, context_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 5: LLM-based filtering of commodity codes using Stage 3 context.
    Output mirrors Stage 4 structure but with filtered codes.
    """
    results = {}
    print(f"\n🧹 STAGE 5: LLM FILTER CODES")
    print("-" * 50)
    contextual_data = context_results.get('contextual_data') if isinstance(context_results, dict) else None
    original_query = context_results.get('original_query') if isinstance(context_results, dict) else None
    context_summary = _build_context_summary(contextual_data, product_name, product_info_text, original_query)

    for hs_code, data in code_lookup_results.items():
        codes = data if isinstance(data, list) else data.get('commodity_codes', [])
        if not codes:
            results[hs_code] = { 'stage': 5, 'status': 'no_codes', 'commodity_codes': [], 'message': 'No codes to filter' }
            continue

        # Build prompt for filtering
        codes_text = "\n".join([f"{i+1}. {c['tariff_code']} - {c['description']}" for i, c in enumerate(codes)])
        prompt = f"""
You are a customs classification expert. Filter the commodity codes based on the product and business context.

PRODUCT: {product_name}
ADDITIONAL INFO: {product_info_text}

CONTEXT:
{context_summary}

AVAILABLE CODES:
{codes_text}

CRITICAL: EXCLUDE codes that contradict the provided context above.

Filtering Constraints:
1. Match product types in context to appropriate code categories
   - If context states "SUV", select motor vehicle codes, not limousine/hearse codes
   - If context states "laptop", select computer/electronic codes, not furniture codes

2. Apply explicit specifications from context 
   - Use stated engine sizes, weights, capacities when codes specify ranges
   - Use stated importer type (individual vs dealer) when codes distinguish this
   - Use stated assembly state (complete vs CKD) when codes specify this

3. Exclude codes that clearly contradict the stated product type
   - Do not select specialty vehicle codes for standard vehicles
   - Do not select codes for different product categories than stated

Output: JSON format {{"keep": [1,3,5]}} with 1-based indices only
If none suitable, return {{"keep": []}}.
"""
        try:
            response = reason_with_llm_fn(prompt, hs_code)
            import json
            raw = response or ""
            cleaned = raw.strip()
            # Remove markdown code fences if present
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            # Extract the first JSON object if extra text exists
            start_idx = cleaned.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = None
                for i, ch in enumerate(cleaned[start_idx:], start_idx):
                    if ch == '{':
                        brace_count += 1
                    elif ch == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                if end_idx:
                    cleaned = cleaned[start_idx:end_idx]
            data_json = json.loads(cleaned) if cleaned else {"keep": list(range(1, len(codes)+1))}
            keep = data_json.get('keep', list(range(1, len(codes)+1)))
            filtered = [codes[i-1] for i in keep if isinstance(i, int) and 1 <= i <= len(codes)]
            status = 'filtered' if len(filtered) < len(codes) else 'no_filter_applied'
            # Debug: show filtered commodity codes count and preview
            try:
                preview_codes = ", ".join([c.get('tariff_code', 'N/A') for c in filtered[:5]])
                print(f"│   ├── FILTERED CODES: {len(filtered)} (preview: {preview_codes})")
            except Exception:
                print(f"│   ├── FILTERED CODES: {len(filtered)}")

            results[hs_code] = {
                'stage': 5,
                'status': status,
                'commodity_codes': filtered,
                'message': f"Filtered {len(codes)} -> {len(filtered)} codes"
            }
            print(f"├── {hs_code}: kept {len(filtered)}/{len(codes)}")
        except Exception as e:
            print(f"│ └── [FILTER ERROR] {e}. Passing through all codes.")
            results[hs_code] = {
                'stage': 5,
                'status': 'filter_error_passthrough',
                'commodity_codes': codes,
                'message': 'Filter failed; using original codes'
            }

    return results

def generate_questions_from_filtered_codes(filtered_code_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 6: Generate classification questions from filtered codes (LLM).
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=True)
    results = {}
    print(f"\n❓ STAGE 6: GENERATE QUESTIONS (from filtered codes)")
    print("-" * 50)
    for hs_code, data in filtered_code_results.items():
        commodity_codes = data.get('commodity_codes', [])
        # Debug: show Stage 6 input commodity codes
        try:
            preview_codes = ", ".join([c.get('tariff_code', 'N/A') for c in commodity_codes[:5]])
            print(f"├── {hs_code}: STAGE 6 INPUT CODES: {len(commodity_codes)} (preview: {preview_codes})")
        except Exception:
            print(f"├── {hs_code}: STAGE 6 INPUT CODES: {len(commodity_codes)}")
        print(f"\n├── {hs_code}: Analyzing {len(commodity_codes)} commodity codes")
        if not commodity_codes:
            results[hs_code] = { 'stage': 6, 'status': 'no_codes', 'message': 'No codes to analyze' }
            continue
        if len(commodity_codes) == 1:
            results[hs_code] = {
                'stage': 6,
                'status': 'single_code',
                'selected_code': commodity_codes[0],
                'message': 'Only one commodity code available'
            }
            continue
        print(f"│ └── [LLM] Generating questions...")
        questions = lookup.generate_classification_questions_with_llm(commodity_codes, product_name, product_info_text)
        if not questions:
            results[hs_code] = {
                'stage': 6,
                'status': 'no_questions',
                'commodity_codes': commodity_codes,
                'message': 'LLM returned no questions'
            }
        else:
            for i, q in enumerate(questions, 1):
                print(f"│ {i}. {q.get('question','')} ({q.get('attribute','')})")
            results[hs_code] = {
                'stage': 6,
                'status': 'questions_generated',
                'questions': questions,
                'commodity_codes': commodity_codes,
                'message': f"Generated {len(questions)} questions"
            }
    return results

def answer_questions_with_llm(question_results: dict, context_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 7: Answer questions using Stage 3 context (wrapper over existing answering).
    """
    return answer_questions_core(question_results, context_results, product_name, product_info_text)

def detect_unanswered_questions(answer_results: dict) -> dict:
    """
    Stage 8: Detect whether all questions were answered or list unanswered.
    Wrapper over existing Stage 7 listing to preserve logic.
    """
    return list_unanswered_questions(answer_results)

# Stage 7: Answer questions using context
def answer_questions_core(stage4_results: dict, stage5_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 6: Answer Questions with LLM
    Streamlined flow: questions + context + LLM prompts
    """
    results = {}
    
    print(f"\n🤖 STAGE 7: QUESTION ANSWERING")
    print("=" * 60)
    
    # Get context info from Stage 5
    contextual_data = stage5_results.get('contextual_data')
    order_id = stage5_results.get('order_id')
    original_query = stage5_results.get('original_query')
    
    for hs_code, stage4_data in stage4_results.items():
        print(f"\n📋 HS CODE: {hs_code}")
        print("-" * 40)
        
        if stage4_data.get('status') == 'questions_generated':
            questions = stage4_data.get('questions', [])
            commodity_codes = stage4_data.get('commodity_codes', [])
            # Debug: show Stage 7 input commodity codes
            try:
                preview_codes = ", ".join([c.get('tariff_code', 'N/A') for c in commodity_codes[:5]])
                print(f"│   ├── STAGE 7 INPUT CODES: {len(commodity_codes)} (preview: {preview_codes})")
            except Exception:
                print(f"│   ├── STAGE 7 INPUT CODES: {len(commodity_codes)}")
            
            # Display questions clearly
            print(f"\n❓ CLASSIFICATION QUESTIONS ({len(questions)} questions):")
            for i, question in enumerate(questions, 1):
                question_text = question.get('question', 'N/A')
                options = question.get('options', [])
                print(f"\n   {i}. {question_text}")
                for j, option in enumerate(options, 1):
                    if isinstance(option, dict):
                        label = option.get('label', option.get('value', 'N/A'))
                        print(f"      {j}) {label}")
                    else:
                        print(f"      {j}) {option}")
            
            # Display context summary
            print(f"\n📊 AVAILABLE CONTEXT:")
            context_summary = _build_context_summary(contextual_data, product_name, product_info_text, original_query)
            print(f"   {context_summary.replace(chr(10), chr(10) + '   ')}")
            
            # Process with LLM
            print(f"\n🤖 PROCESSING WITH LLM...")
            prompt = _create_classification_prompt(questions, context_summary, product_name, product_info_text)
            llm_answers = _process_llm_classification(prompt, questions)
            
            # Display results clearly
            print(f"\n✅ LLM ANSWERS:")
            for i, question in enumerate(questions, 1):
                question_id = question.get('id', f'question_{i}')
                question_text = question.get('question', 'N/A')
                answer = llm_answers.get(question_id, 'Not answered')
                print(f"   {i}. {question_text}")
                print(f"      → {answer}")
            
            answered_count = len([q for q in questions if q.get('id', f'question_{questions.index(q)+1}') in llm_answers])
            print(f"\n📈 SUMMARY: {answered_count}/{len(questions)} questions answered")
            
            results[hs_code] = {
                'stage': 6,
                'status': 'questions_answered',
                'questions': questions,
                'llm_answers': llm_answers,
                'commodity_codes': commodity_codes,
                'context_summary': context_summary,
                'message': f'Answered {answered_count}/{len(questions)} questions via LLM'
            }
        else:
            print(f"   [SKIP] No questions to answer (status: {stage4_data.get('status')})")
            results[hs_code] = {
                'stage': 6,
                'status': 'no_questions',
                'stage4_data': stage4_data,
                'message': 'No questions to answer with LLM'
            }
    
    return results

## Stage 8: Detect unanswered questions
def list_unanswered_questions(stage6_results: dict) -> dict:
    """
    Takes all questions and answers and identifies which questions still need user input.
    """
    results = {}
    
    print(f"\n❓ STAGE 8: LIST UNANSWERED QUESTIONS")
    print("-" * 50)
    
    for hs_code, stage6_data in stage6_results.items():
        print(f"\n├── {hs_code}: Checking for unanswered questions")
        # Debug: show Stage 8 input commodity codes
        commodity_codes_dbg = stage6_data.get('commodity_codes', [])
        try:
            preview_codes = ", ".join([c.get('tariff_code', 'N/A') for c in commodity_codes_dbg[:5]])
            print(f"│   ├── STAGE 8 INPUT CODES: {len(commodity_codes_dbg)} (preview: {preview_codes})")
        except Exception:
            print(f"│   ├── STAGE 8 INPUT CODES: {len(commodity_codes_dbg)}")
        
        if stage6_data.get('status') in ['questions_answered', 'all_answered']:
            questions = stage6_data.get('questions', [])
            # Get answers from Stage 6 - check both old and new formats
            combined_answers = stage6_data.get('combined_answers', stage6_data.get('auto_answers', stage6_data.get('llm_answers', {})))
            
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


def _build_context_summary(contextual_data: Dict[str, Any], product_name: str, 
                          product_info_text: str, original_query: str) -> str:
    """
    Build a comprehensive context summary for LLM processing.
    """
    context_parts = []
    
    # Product information
    context_parts.append(f"Product: {product_name}")
    context_parts.append(f"Details: {product_info_text}")
    if original_query:
        context_parts.append(f"Query: {original_query}")
    
    # Contextual data from Stage 5 - Enhanced to handle nested structure
    if contextual_data:
        # Buyer/Consignee information
        buyer_info = contextual_data.get('buyer_info', {})
        if buyer_info.get('name'):
            context_parts.append(f"Buyer: {buyer_info['name']}")
        if buyer_info.get('address'):
            context_parts.append(f"Buyer Address: {buyer_info['address']}")
        
        # Supplier/Shipper information  
        supplier_info = contextual_data.get('supplier_info', {})
        if supplier_info.get('name'):
            context_parts.append(f"Supplier: {supplier_info['name']}")
        if supplier_info.get('address'):
            context_parts.append(f"Supplier Address: {supplier_info['address']}")
        
        # Product details
        product_details = contextual_data.get('product_details', {})
        if product_details.get('description'):
            context_parts.append(f"Product Description: {product_details['description']}")
        if product_details.get('quantity'):
            context_parts.append(f"Quantity: {product_details['quantity']}")
        if product_details.get('year_of_manufacture'):
            context_parts.append(f"Year of Manufacture: {product_details['year_of_manufacture']}")
        
        # Shipping information
        shipping_info = contextual_data.get('shipping_info', {})
        if shipping_info.get('delivery_terms'):
            context_parts.append(f"Delivery Terms: {shipping_info['delivery_terms']}")
        if shipping_info.get('port_of_loading'):
            context_parts.append(f"Port of Loading: {shipping_info['port_of_loading']}")
        if shipping_info.get('port_of_discharge'):
            context_parts.append(f"Port of Discharge: {shipping_info['port_of_discharge']}")
        if shipping_info.get('vessel_name'):
            context_parts.append(f"Vessel: {shipping_info['vessel_name']}")
        if shipping_info.get('carrier'):
            context_parts.append(f"Carrier: {shipping_info['carrier']}")
        
        # Cargo information
        cargo_info = contextual_data.get('cargo_info', {})
        if cargo_info.get('year_of_manufacture'):
            context_parts.append(f"Vehicle Year: {cargo_info['year_of_manufacture']}")
        if cargo_info.get('vin'):
            context_parts.append(f"VIN: {cargo_info['vin']}")
        if cargo_info.get('color'):
            context_parts.append(f"Color: {cargo_info['color']}")
        
        # Legacy support for old flat structure
        if contextual_data.get('consignee_name'):
            context_parts.append(f"Consignee: {contextual_data['consignee_name']}")
        if contextual_data.get('shipper'):
            context_parts.append(f"Shipper: {contextual_data['shipper']}")
        if contextual_data.get('port_of_origin'):
            context_parts.append(f"Origin: {contextual_data['port_of_origin']}")
        if contextual_data.get('port_of_destination'):
            context_parts.append(f"Destination: {contextual_data['port_of_destination']}")
        if contextual_data.get('commodity'):
            commodity = contextual_data['commodity']
            if len(commodity) > 60:
                commodity = commodity[:60] + "..."
            context_parts.append(f"Commodity: {commodity}")
        if contextual_data.get('weight'):
            context_parts.append(f"Weight: {contextual_data['weight']}")
        if contextual_data.get('vessel'):
            context_parts.append(f"Vessel: {contextual_data['vessel']}")
        if contextual_data.get('bill_of_lading'):
            context_parts.append(f"BOL: {contextual_data['bill_of_lading']}")
        
        # Additional legacy support
        if contextual_data.get('user_query'):
            context_parts.append(f"User Query: {contextual_data['user_query']}")
        if contextual_data.get('invoice_data'):
            invoice = contextual_data['invoice_data']
            context_parts.append(f"Invoice: {invoice.get('invoice_number', 'N/A')} - {invoice.get('supplier', 'N/A')}")
        if contextual_data.get('bill_of_lading') and isinstance(contextual_data.get('bill_of_lading'), dict):
            bol = contextual_data['bill_of_lading']
            context_parts.append(f"Bill of Lading: {bol.get('bol_number', 'N/A')} - {bol.get('vessel', 'N/A')}")
    else:
        context_parts.append("Contextual Data: None provided")
    
    return " | ".join(context_parts)

def _create_classification_prompt(questions: List[Dict], context_summary: str, 
                                 product_name: str, product_info_text: str) -> str:
    """
    Create a focused LLM prompt for answering classification questions from context.
    """
    # Build questions section
    questions_text = "CLASSIFICATION QUESTIONS:\n"
    for i, question in enumerate(questions, 1):
        question_id = question.get('id', f'question_{i}')
        question_text = question.get('question', 'N/A')
        options = question.get('options', [])
        
        questions_text += f"\n{i}. {question_text}\n"
        questions_text += f"   Question ID: {question_id}\n"
        questions_text += f"   Options:\n"
        for j, option in enumerate(options, 1):
            if isinstance(option, dict):
                value = option.get('value', 'N/A')
                label = option.get('label', value)
                questions_text += f"      {j}. {label} (value: {value})\n"
            else:
                questions_text += f"      {j}. {option}\n"
    
    # Create the prompt to ANSWER questions, not generate them
    prompt = f"""Answer the classification questions based on the available context.

CONTEXT:
{context_summary}

{questions_text}

INSTRUCTIONS:
- Answer EACH question based on the context provided
- Use the exact "value" from the options for each answer
- Return ONLY a JSON object with question IDs as keys and option values as answers
- NO explanations, reasoning, or additional text

EXAMPLE OUTPUT FORMAT:
{{
  "question_1": "option_value_1",
  "question_2": "option_value_2",
  "question_3": "option_value_3"
}}

Return your answers now:"""
    
    return prompt

def _process_llm_classification(prompt: str, questions: List[Dict]) -> Dict[str, str]:
    """
    Process LLM classification and return answers.
    """
    try:
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
            return llm_answers
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse LLM response: {e}")
            print(f"   📝 Raw response: {response[:200]}...")
            
            # Try to extract partial JSON if response was truncated
            try:
                # Look for incomplete JSON and try to complete it
                if '"question_3": "Three years or less' in response:
                    # Complete the truncated response
                    fixed_response = response.replace('"question_3": "Three years or less', '"question_3": "Three years or less since manufacture"')
                    if fixed_response.count('{') > fixed_response.count('}'):
                        # Add missing closing brace
                        fixed_response += '}'
                    llm_answers = json.loads(fixed_response)
                    print(f"   ✅ Fixed truncated JSON response")
                    return llm_answers
            except:
                pass
                
            return {}
            
    except Exception as e:
        print(f"   ❌ LLM processing failed: {e}")
        return {}



## (Deprecated) user input interface retained for compatibility
def show_context(stage7_results: dict, original_query: str, order_id: str = None, user_answers: dict = None) -> dict:
    """
    Displays unanswered questions and provides interface for user to provide additional information.
    """
    results = {}
    
    print(f"\n📋 USER INPUT INTERFACE")
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

## Finalize context and answers before selection
def complete_loop(stage8_results: dict, stage5_results: dict = None, user_answers: dict = None) -> dict:
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
        
        # Handle 'context_displayed', 'all_answers_provided', and 'no_input_needed' statuses
        if stage8_data.get('status') in ['context_displayed', 'all_answers_provided', 'no_input_needed', 'all_answered']:
            answered_questions = stage8_data.get('answered_questions', {})
            unanswered_questions = stage8_data.get('unanswered_questions', [])
            resolved_context = stage8_data.get('resolved_context', {})
            # Debug: show Stage 9 input commodity codes
            commodity_codes_dbg = stage8_data.get('commodity_codes', [])
            try:
                preview_codes = ", ".join([c.get('tariff_code', 'N/A') for c in commodity_codes_dbg[:5]])
                print(f"│   ├── STAGE 9 INPUT CODES: {len(commodity_codes_dbg)} (preview: {preview_codes})")
            except Exception:
                print(f"│   ├── STAGE 9 INPUT CODES: {len(commodity_codes_dbg)}")
            
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
                    # Display streamlined structure fields first
                    if stage5_context.get('consignee_name'):
                        print(f"│       │   ├── Consignee: {stage5_context['consignee_name']}")
                    if stage5_context.get('shipper'):
                        print(f"│       │   ├── Shipper: {stage5_context['shipper']}")
                    if stage5_context.get('port_of_origin'):
                        print(f"│       │   ├── Origin: {stage5_context['port_of_origin']}")
                    if stage5_context.get('port_of_destination'):
                        print(f"│       │   ├── Destination: {stage5_context['port_of_destination']}")
                    if stage5_context.get('commodity'):
                        commodity_preview = stage5_context['commodity'][:50] + "..." if len(stage5_context['commodity']) > 50 else stage5_context['commodity']
                        print(f"│       │   ├── Commodity: {commodity_preview}")
                    if stage5_context.get('weight'):
                        print(f"│       │   ├── Weight: {stage5_context['weight']}")
                    if stage5_context.get('vessel'):
                        print(f"│       │   ├── Vessel: {stage5_context['vessel']}")
                    if stage5_context.get('bill_of_lading'):
                        print(f"│       │   ├── BOL: {stage5_context['bill_of_lading']}")
                    
                    # Legacy support for nested structure
                    if stage5_context.get('user_query'):
                        print(f"│       │   ├── User query: {stage5_context['user_query']}")
                    if stage5_context.get('invoice_data'):
                        invoice = stage5_context['invoice_data']
                        print(f"│       │   ├── Invoice: {invoice.get('invoice_number', 'N/A')} - {invoice.get('supplier', 'N/A')}")
                    if stage5_context.get('bill_of_lading') and isinstance(stage5_context.get('bill_of_lading'), dict):
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
                    'all_questions': all_questions,
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

## LLM-based final selection of a single code
def final_selection_with_llm(stage9_results: dict, product_name: str, product_info_text: str) -> dict:
    """
    Stage 10: LLM-based final code selection using Claude Sonnet 4
    Uses LLM to analyze all context and select the most appropriate commodity code.
    """
    lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=True)
    results = {}
    
    print(f"\n🎯 STAGE 10: FINAL CODE SELECTION (LLM)")
    print("-" * 50)
    
    for hs_code, stage9_data in stage9_results.items():
        print(f"\n├── {hs_code}: LLM-based selection")
        
        if stage9_data.get('status') not in ['complete', 'no_input_needed']:
            results[hs_code] = {
                'stage': 10,
                'status': 'no_selection_needed',
                'message': f"Status: {stage9_data.get('status')}"
            }
            continue
        
        commodity_codes = stage9_data.get('commodity_codes', [])
        # Debug: show Stage 10 input commodity codes
        try:
            preview_codes = ", ".join([c.get('tariff_code', 'N/A') for c in commodity_codes[:5]])
            print(f"│   ├── STAGE 10 INPUT CODES: {len(commodity_codes)} (preview: {preview_codes})")
        except Exception:
            print(f"│   ├── STAGE 10 INPUT CODES: {len(commodity_codes)}")
        complete_answers = stage9_data.get('complete_answers', {})
        all_questions = stage9_data.get('all_questions', [])
        complete_context = stage9_data.get('complete_context', {})
        
        print(f"│   ├── Starting: {len(commodity_codes)} commodity codes")
        print(f"│   ├── Context: {len(complete_answers)} answered questions")
        print(f"│   └── Using Claude Sonnet 4 for final selection")
        
        # Use LLM to select best match
        final_code = lookup.select_best_commodity_code(
            hs_code, commodity_codes, product_name, product_info_text, complete_context
        )
        
        if final_code:
            print(f"│   └── ✅ SELECTED: {final_code['tariff_code']}")
            print(f"│       └── {final_code['description']}")
            
            results[hs_code] = {
                'stage': 10,
                'status': 'selected',
                'final_code': final_code,
                'selection_method': 'llm_selection_claude_sonnet_4',
                'complete_answers': complete_answers,
                'complete_context': complete_context,
                'message': f"Selected {final_code['tariff_code']} using Claude Sonnet 4"
            }
        else:
            print(f"│   └── ❌ REJECTED: LLM rejected all codes as inappropriate")
            results[hs_code] = {
                'stage': 10,
                'status': 'rejected',
                'complete_answers': complete_answers,
                'complete_context': complete_context,
                'message': 'Claude Sonnet 4 rejected all codes as inappropriate'
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
    try:
        print(f"\n🚀 RUNNING 10-STAGE COMMODITY CODE WORKFLOW")
        print("=" * 70)
        
        # Context gathered early
        # Stage 3: Context
        stage3_results = gather_context(stage1_results, original_question, order_id, contextual_data, product_name)

        # Lookup codes
        # Stage 4: Lookup
        stage4_results = lookup_commodity_codes(hs_codes)

        # LLM-based filtering
        # Stage 5: Filter with LLM
        stage5_results = filter_codes_with_llm(stage4_results, stage3_results, product_name, product_info_text)

        # Generate questions from filtered codes
        # Stage 6: Generate questions
        stage6_results = generate_questions_from_filtered_codes(stage5_results, product_name, product_info_text)

        # Answer questions using context
        # Stage 7: Answer questions
        stage7_results = answer_questions_with_llm(stage6_results, stage3_results, product_name, product_info_text)
    
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

        # Stage 8: Detect unanswered vs all answered (report only)
        # Stage 8: Detect unanswered
        stage8_results = detect_unanswered_questions(stage7_results)

        # Complete the loop and final selection remain unchanged in numbering
        # Stage 9: Complete loop
        stage9_results = complete_loop(stage8_results, stage3_results, user_answers)
        
        # Stage 10: Final selection
        stage10_results = final_selection_with_llm(stage9_results, product_name, product_info_text)
        
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
        
    except Exception as e:
        # Return error result instead of None
        print(f"❌ ERROR in run_10_stage_workflow: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            hs_code: {
                'error': str(e),
                'status': 'failed',
                'message': 'Workflow failed with exception'
            } for hs_code in hs_codes
        }

# ═══════════════════════════════════════════════════════════════════════════════
# CORE SUPPORTING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _process_direct_context(contextual_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process direct contextual data into standardized format for classification.
    Now handles clean, flat structure directly.
    """
    processed_context = {}
    
    # Direct mapping from clean structure - no complex processing needed
    if contextual_data.get('consignee_name'):
        processed_context['importer_type'] = _determine_importer_type_from_name(contextual_data['consignee_name'])
        processed_context['usage_purpose'] = _determine_usage_purpose_from_name(contextual_data['consignee_name'])
    
    if contextual_data.get('shipper'):
        processed_context['supplier_name'] = contextual_data['shipper']
    
    if contextual_data.get('shipper_address'):
        processed_context['supplier_address'] = contextual_data['shipper_address']
    
    if contextual_data.get('commodity'):
        processed_context['product_specifications'] = contextual_data['commodity']
    
    if contextual_data.get('port_of_origin'):
        processed_context['origin_country'] = _extract_country_from_port(contextual_data['port_of_origin'])
    
    if contextual_data.get('weight'):
        processed_context['size_weight_category'] = _determine_weight_category(contextual_data['weight'])
    
    if contextual_data.get('extraction_confidence'):
        processed_context['extraction_confidence'] = contextual_data['extraction_confidence']
    
    # Handle nested structure for backward compatibility
    buyer_info = contextual_data.get('buyer_info', {})
    if buyer_info:
        processed_context['importer_type'] = _determine_importer_type_from_buyer(buyer_info)
        processed_context['usage_purpose'] = _determine_usage_purpose_from_buyer(buyer_info)
    
    supplier_info = contextual_data.get('supplier_info', {})
    if supplier_info:
        processed_context['supplier_name'] = supplier_info.get('name', '')
        processed_context['supplier_address'] = supplier_info.get('address', '')
    
    product_details = contextual_data.get('product_details', {})
    if product_details:
        processed_context['product_specifications'] = _extract_product_specs_from_details(product_details)
        processed_context['value_category'] = _determine_value_category_from_details(product_details)
        processed_context['quantity_category'] = _determine_quantity_category_from_details(product_details)
    
    shipping_info = contextual_data.get('shipping_info', {})
    if shipping_info:
        processed_context['origin_country'] = _extract_origin_country_from_shipping(shipping_info)
        processed_context['size_weight_category'] = _determine_size_weight_from_shipping(shipping_info)
    
    doc_metadata = contextual_data.get('document_metadata', {})
    if doc_metadata:
        processed_context['product_age_category'] = _determine_age_from_metadata(doc_metadata)
        processed_context['extraction_confidence'] = doc_metadata.get('extraction_confidence', 'unknown')
    
    return processed_context

def _determine_importer_type_from_name(name: str) -> str:
    """Determine importer type from name string."""
    name_upper = name.upper()
    
    # Check for commercial indicators
    commercial_patterns = [
        r'(INC|LLC|LTD|CORP|COMPANY|CO\.|ENTERPRISE)',
        r'(IMPORT|EXPORT|TRADING|WHOLESALE|RETAIL)',
    ]
    
    for pattern in commercial_patterns:
        if re.search(pattern, name_upper):
            return 'dealer'
    
    # Check for individual name patterns
    individual_patterns = [
        r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # First Last
        r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$',  # First M. Last
    ]
    
    for pattern in individual_patterns:
        if re.match(pattern, name.title()):
            return 'individual'
    
    return 'unknown'

def _determine_usage_purpose_from_name(name: str) -> str:
    """Determine usage purpose from name string."""
    name_upper = name.upper()
    
    # Check for commercial/resale indicators
    commercial_patterns = [
        r'(INC|LLC|LTD|CORP|COMPANY|CO\.|ENTERPRISE)',
        r'(IMPORT|EXPORT|TRADING|WHOLESALE|RETAIL|DEALER)',
    ]
    
    for pattern in commercial_patterns:
        if re.search(pattern, name_upper):
            return 'commercial'
    
    return 'personal'

def _extract_country_from_port(port_string: str) -> str:
    """Extract country from port string like 'Port of Miami, USA'."""
    if ',' in port_string:
        return port_string.split(',')[-1].strip()
    return ''

def _determine_weight_category(weight_string: str) -> str:
    """Determine weight category from weight string like '2,003 KGS'."""
    import re
    
    # Extract numeric value
    weight_match = re.search(r'([\d,]+)', weight_string.replace(',', ''))
    if weight_match:
        try:
            weight_kg = float(weight_match.group(1))
            if weight_kg < 100:
                return 'light'
            elif weight_kg < 1000:
                return 'medium'
            else:
                return 'heavy'
        except:
            pass
    
    return 'unknown'

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
    Fetch order context from customs_api via HTTP request.
    
    Args:
        order_id: The order ID to fetch context for
        
    Returns:
        Dictionary with contextual_data for Stage 5, or empty dict if error
    """
    try:
        import requests
        import json
        
        # Configuration
        from config import CUSTOMS_API_BASE_URL, CUSTOMS_API_TIMEOUT
        timeout = CUSTOMS_API_TIMEOUT
        
        # Make HTTP request
        url = f"{CUSTOMS_API_BASE_URL}/api/orders/{order_id}/context"
        
        print(f"🌐 Fetching order context from: {url}")
        
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        # Handle response
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully fetched context for order {order_id}")
            return data
            
        elif response.status_code == 404:
            print(f"❌ Order {order_id} not found in customs_api")
            return {}
            
        else:
            print(f"❌ Error fetching order context: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return {}
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout fetching order context for {order_id}")
        return {}
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to customs_api at {CUSTOMS_API_BASE_URL}")
        return {}
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error fetching order context: {e}")
        return {}
        
    except Exception as e:
        print(f"❌ Unexpected error fetching order context: {e}")
        return {}

def reason_with_llm_fn(prompt: str, hs_code: str = None) -> str:
    """
    Simple wrapper function for LLM reasoning calls.
    Updated to prevent verbose reasoning responses.
    """
    lower_prompt = prompt.lower()
    # Route Stage 5 filtering to Gemini Pro
    if "stage 5" in lower_prompt or "filter the commodity codes" in lower_prompt or "filter codes" in lower_prompt:
        system_prompt = "You are a tariff classification expert. Generate only the requested JSON output with no explanations, reasoning, or additional text. Be concise and direct."
        model_alias = "gemini_pro"
    # Check if this is a question generation prompt
    elif "generate classification questions" in lower_prompt:
        system_prompt = "You are a tariff classification expert. Generate only the requested JSON output with no explanations, reasoning, or additional text. Be concise and direct."
        model_alias = "claude_sonnet_4"
    # Check if this is a final selection prompt (Stage 10)
    elif "analysis requirements" in lower_prompt and "available commodity codes" in lower_prompt:
        system_prompt = "You are an expert in HS Code classification and customs regulations. Analyze the complete context and select the most appropriate commodity code. Always respond in the exact JSON format requested."
        model_alias = "claude_sonnet_4"
    else:
        system_prompt = "You are an expert in HS Code classification. Always respond in the exact format requested."
        model_alias = "gpt_5"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    return chat_completion(messages, model_alias=model_alias)

def chat_completion(messages, model_alias="gpt_5"):
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
        "temperature": 0.1,  # Lower temperature for consistent output
        "max_tokens": 3000,  # Increased token limit to prevent truncation
        # Remove response_format to allow more flexible parsing
    }
    
    print(f"[DEBUG] Making LLM request to model: {model}")
    print(f"[DEBUG] Payload: {payload}")
    
    response = requests.post(
        config["api_url"],
        headers=config["headers"],
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    
    print(f"[DEBUG] LLM API response: {result}")
    
    # Check if response has expected structure
    if "choices" not in result or not result["choices"]:
        logger.error(f"Invalid LLM response structure: {result}")
        return ""
    
    choice = result["choices"][0]
    if "message" not in choice or "content" not in choice["message"]:
        logger.error(f"Invalid choice structure: {choice}")
        return ""
    
    content = choice["message"]["content"]
    print(f"[DEBUG] Extracted content: {content[:200]}...")
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
            return {}
    
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
            return {}
    
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
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error extracting propulsion type: {e}")
            return {}
    
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
            return {}
    
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
            return {}
    
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
                return {}
                
        except Exception as e:
            self.logger.error(f"Error finding single code for {hs_code}: {e}")
            return {}
    
    def generate_classification_questions_with_llm(self, commodity_codes: List[Dict[str, Any]], 
                                                 product_name: str, product_info_text: str) -> List[Dict[str, Any]]:
        """
        Use LLM to analyze commodity codes and generate appropriate classification questions.
        """
        if not commodity_codes or len(commodity_codes) <= 1:
            return []
        
        # Build commodity codes text for LLM analysis
        codes_text = "COMMODITY CODES:\n"
        for i, code in enumerate(commodity_codes, 1):
            codes_text += f"{i}. {code['tariff_code']}: {code['description']}\n"
        
        # Much simpler, direct prompt that discourages reasoning
        prompt = f"""Analyze these commodity codes and generate classification questions.

COMMODITY CODES:
{codes_text}

TASK: Generate the COMPLETE set of questions needed to distinguish between ALL codes above.

REQUIREMENTS:
- Compare all code descriptions to identify every distinguishing characteristic
- Create one question for each characteristic that differentiates between codes
- Continue generating questions until EVERY code can be uniquely identified
- There is NO maximum limit on the number of questions
- Each question must use terminology from the actual code descriptions

OUTPUT FORMAT: Return only valid JSON (no explanations or additional text):

{{
  "questions": [
    {{
      "id": "question_N",
      "question": "Clear question text based on code descriptions",
      "type": "choice",
      "options": [
        {{"value": "option_value", "label": "Option label from codes"}}
      ],
      "attribute": "descriptive_name"
    }}
  ]
}}"""

        try:
            print(f"│ └── [DEBUG] Calling LLM with prompt length: {len(prompt)}")
            response = reason_with_llm_fn(prompt)
            print(f"[DEBUG] Full LLM response: {repr(response)}")
            print(f"[DEBUG] Response length: {len(response) if response else 0}")
            print(f"│ └── [DEBUG] LLM response length: {len(response) if response else 0}")
            print(f"│ └── [DEBUG] LLM response preview: {response[:200] if response else 'EMPTY RESPONSE'}...")
            
            if not response or not response.strip():
                print(f"│ └── [ERROR] Empty LLM response")
                return []
            
            import json
            try:
                # Clean response and extract JSON
                cleaned_response = self._extract_json_from_response(response)
                print(f"│ └── [DEBUG] Cleaned response: {cleaned_response[:200]}...")
                
                result = json.loads(cleaned_response)
                questions = result.get('questions', [])
                
                # Validate and clean up questions
                valid_questions = []
                for i, q in enumerate(questions, 1):
                    if q.get('question') and q.get('options'):
                        q['id'] = f'question_{i}'  # Ensure consistent ID format
                        valid_questions.append(q)
                
                print(f"│ └── [SUCCESS] Generated {len(valid_questions)} valid questions")
                return valid_questions
                
            except json.JSONDecodeError as e:
                print(f"│ └── [ERROR] Failed to parse LLM response: {e}")
                print(f"│ └── [ERROR] Raw response: {response[:500]}...")
                print(f"│ └── [ERROR] Cleaned response: {cleaned_response[:500]}...")
                return []
                
        except Exception as e:
            print(f"│ └── [ERROR] LLM question generation failed: {e}")
            return []

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response, handling markdown and truncation."""
        cleaned = response.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        # Find JSON object boundaries
        start = cleaned.find('{')
        if start == -1:
            return cleaned
        
        # Count braces to find complete JSON
        brace_count = 0
        end = start
        for i, char in enumerate(cleaned[start:], start):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        return cleaned[start:end]
    
    def select_best_commodity_code(self, hs_code: str, commodity_codes: List[Dict[str, Any]], 
                                 product_name: str, product_info_text: str, 
                                 context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Use LLM to select the best commodity code from the available options.
        """
        if not self.use_llm_selection:
            # Return first code if LLM selection is disabled
            return commodity_codes[0] if commodity_codes else {}
        
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
Respond with a JSON object containing your selection:
{{"selection": "1"}} for option 1
{{"selection": "2"}} for option 2
{{"selection": "REJECT"}} if none are appropriate

Examples:
{{"selection": "2"}}
{{"selection": "REJECT"}}
"""
            
            # Call LLM
            response = reason_with_llm_fn(prompt, hs_code)
            
            if not response:
                self.logger.error("Empty response from LLM")
                return {}
            
            # Parse JSON response (handle fenced/verbose outputs)
            try:
                import json
                cleaned_response = self._extract_json_from_response(response)
                print(f"│   └── [DEBUG] Cleaned selection response: {cleaned_response[:200]}...")
                response_data = json.loads(cleaned_response.strip())
                selection = response_data.get('selection', '').strip()
                
                if selection.upper() == "REJECT":
                    self.logger.info("LLM rejected all commodity codes as inappropriate")
                    return {}
                
                # Try to parse the selection as a number
                try:
                    selected_index = int(selection) - 1
                    if 0 <= selected_index < len(commodity_codes):
                        selected_code = commodity_codes[selected_index]
                        self.logger.info(f"LLM selected commodity code: {selected_code['tariff_code']}")
                        return selected_code
                    else:
                        self.logger.error(f"LLM selected invalid index: {selected_index}")
                        return {}
                        
                except ValueError:
                    self.logger.error(f"Could not parse selection as number: {selection}")
                    return {}
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Could not parse LLM JSON response: {e}")
                # Fallback: attempt to extract selection via regex
                try:
                    import re
                    match = re.search(r'\{\s*"selection"\s*:\s*"(REJECT|\d+)"\s*\}', response)
                    if match:
                        sel = match.group(1)
                        if sel.upper() == 'REJECT':
                            self.logger.info("LLM rejected all commodity codes as inappropriate")
                            return {}
                        selected_index = int(sel) - 1
                        if 0 <= selected_index < len(commodity_codes):
                            selected_code = commodity_codes[selected_index]
                            self.logger.info(f"LLM selected commodity code: {selected_code['tariff_code']}")
                            return selected_code
                except Exception:
                    pass
                return {}
                
        except Exception as e:
            self.logger.error(f"Error in LLM selection: {e}")
            return {}
    
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
            
            response = chat_completion(messages, model_alias="gpt_5")
            
            if not response:
                return {}
            
            response = response.strip()
            
            if response.upper() == "REJECT":
                return {}
            
            # Parse response
            import re
            number_match = re.search(r'\b(\d+)\b', response)
            if number_match:
                selected_index = int(number_match.group(1)) - 1
                return selected_index
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Error in alternative LLM retry: {e}")
            return {}

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
    
    # Ensure results is never None
    if results is None:
        results = {}
    
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
    
    # Ensure results is never None
    if results is None:
        results = {}
    
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
    
    # Ensure results is never None
    if results is None:
        results = {}
    
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
    
    # Results processing completed (file saving disabled)
