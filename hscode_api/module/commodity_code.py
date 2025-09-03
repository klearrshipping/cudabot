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
from typing import List, Dict, Optional

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
# MAIN ENTRY POINTS (Called by app.py or external systems)
# ═══════════════════════════════════════════════════════════════════════════════

def interactive_commodity_lookup(hs_codes: list[str], product_name: str, product_info_text: str, 
                               original_question: str = "") -> dict:
    """
    Interactive version for terminal testing - handles the full question/answer cycle.
    
    Args:
        hs_codes: List of HS codes
        product_name: Name of the product  
        product_info_text: Additional product information
        original_question: The original user question
        
    Returns:
        Final commodity code selection
    """
    
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
                                      original_question: str, user_answers: dict) -> dict:
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
            print(f"│   └── 🤖 Running LLM analysis with user answers...")
            
            # Check if sufficient information for analysis
            info_analysis = lookup.analyze_if_sufficient_info(
                original_question, all_matches, product_name, enhanced_product_info
            )
            
            if info_analysis['sufficient']:
                # Select best match with extracted context if available
                best_match = lookup.select_best_commodity_code(
                    hs_code, all_matches, product_name, enhanced_product_info, 
                    info_analysis.get('extracted_context', {})
                )
                if best_match:
                    results[hs_code] = [best_match]
                else:
                    results[hs_code] = []
            else:
                # Still need more clarification
                questions = lookup.generate_clarification_questions(
                    original_question, all_matches, product_name, 
                    enhanced_product_info, info_analysis['missing_info']
                )
                
                results[hs_code] = {
                    'requires_clarification': True,
                    'reasoning': info_analysis['reasoning'],
                    'missing_info': info_analysis['missing_info'],
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
                         original_question: str = "") -> dict:
    """
    Main function called by app.py to lookup commodity codes with LLM selection.
    
    Args:
        hs_codes: List of HS codes (may have dots like ["0706.10"])
        product_name: Name of the product
        product_info_text: Additional product information
        original_question: The original user question for context
        
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
                print(f"├── {hs_code}: ❌ No commodity codes found")
                results[hs_code] = None
                continue
            
            print(f"├── {hs_code}: Found {len(all_matches)} commodity codes, analyzing with LLM...")
            
            # Print found commodity codes for debugging
            print(f"\n📋 Found {len(all_matches)} commodity codes:")
            for match in all_matches:
                print(f"   • {match['tariff_code']}: {match['description']}")
            
            # STEP 1: Check if we have sufficient information to proceed
            print(f"\n🔍 ANALYZING INFORMATION SUFFICIENCY")
            print("-" * 50)
            
            info_analysis = lookup.analyze_if_sufficient_info(
                original_question, all_matches, product_name, product_info_text
            )
            
            print(f"Analysis: {info_analysis['reasoning']}")
            
            if info_analysis['sufficient']:
                print(f"✅ Sufficient information available - proceeding with selection")
                
                # Use LLM to select best match with extracted context if available
                best_match = lookup.select_best_commodity_code(
                    hs_code, all_matches, product_name, product_info_text,
                    info_analysis.get('extracted_context', {})
                )
                
                if best_match:
                    confidence_emoji = {
                        'llm_selected': '🤖',
                        'single_match': '✅'
                    }.get(best_match.get('selection_method', 'unknown'), '🤖')
                    
                    print(f"│   └── Selected: {best_match['tariff_code']} {confidence_emoji}")
                    print(f"│       └── {best_match['description']}")
                    print(f"│       └── Reasoning: {best_match.get('reasoning', 'No reasoning')}")
                    
                    results[hs_code] = [best_match]  # Return as list for consistency
                else:
                    print(f"│   └── ❌ LLM rejected all commodity codes as inappropriate")
                    results[hs_code] = []
            else:
                print(f"❌ Insufficient information - clarification needed")
                print(f"Missing information: {', '.join(info_analysis['missing_info'])}")
                
                # Generate specific questions using LLM
                print(f"\n🤖 GENERATING CLARIFICATION QUESTIONS")
                print("-" * 50)
                
                questions = lookup.generate_clarification_questions(
                    original_question, all_matches, product_name, 
                    product_info_text, info_analysis['missing_info']
                )
                
                print(f"Generated {len(questions)} questions:")
                for i, q in enumerate(questions, 1):
                    print(f"{i}. {q['question']} ({q['type']})")
                    if 'help_text' in q:
                        print(f"   Help: {q['help_text']}")
                
                # Return clarification request with generated questions
                results[hs_code] = {
                    'requires_clarification': True,
                    'reasoning': info_analysis['reasoning'],
                    'missing_info': info_analysis['missing_info'],
                    'questions': questions,
                    'available_codes': all_matches,
                    'original_question': original_question,
                    'code_count': len(all_matches)  # Add explicit count for debugging
                }
                
        except Exception as e:
            logger.error(f"Error processing {hs_code}: {str(e)}")
            results[hs_code] = []
    
    # Debug: Print what we're returning
    print(f"\n🔍 DEBUG: Returning results:")
    for hs_code, result in results.items():
        if isinstance(result, dict) and result.get('requires_clarification'):
            print(f"   {hs_code}: Clarification needed ({result.get('code_count', 0)} codes available)")
        elif isinstance(result, list):
            print(f"   {hs_code}: {len(result)} selected codes")
        else:
            print(f"   {hs_code}: {result}")
    
    return results

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

    def analyze_if_sufficient_info(self, original_question: str, commodity_matches: List[Dict], 
                                  product_name: str, product_info_text: str) -> Dict:
        """
        Determine if we have sufficient information to make a definitive commodity code selection.
        
        Args:
            original_question: The original user question
            commodity_matches: List of matching commodity codes with descriptions
            product_name: Name of the product
            product_info_text: Additional product information available
            
        Returns:
            Dictionary with:
            - 'sufficient': bool (True/False)
            - 'reasoning': str (explanation)
            - 'missing_info': List[str] (what information is needed if insufficient)
        """
        
        if len(commodity_matches) == 1:
            return {
                'sufficient': True,
                'reasoning': 'Only one commodity code match found',
                'missing_info': []
            }
        
        # Enhanced analysis: Try to extract obvious information from context
        print(f"\n🔍 ANALYZING INFORMATION SUFFICIENCY")
        print("-" * 50)
        
        # Extract context information
        extracted_context = {}
        
        # Try to extract manufacturing year
        year = self._extract_year_from_context(original_question, product_name, product_info_text)
        if year:
            extracted_context['manufacturing_year'] = year
            print(f"Extracted context:")
            print(f"   • Manufacturing year: {year} (from \"{product_name}\")")
        
        # Try to determine importer type
        importer_type = self._can_determine_importer_from_context(original_question, product_name)
        if importer_type:
            extracted_context['importer_type'] = importer_type
            print(f"   • Importer type: {importer_type} (assumed for consumer vehicle)")
        
        # Check if we have enough context to proceed
        if extracted_context:
            print(f"\nAnalysis: Sufficient information available from context")
            return {
                'sufficient': True,
                'reasoning': f'Sufficient information available from context: {", ".join(f"{k}={v}" for k, v in extracted_context.items())}',
                'missing_info': [],
                'extracted_context': extracted_context
            }
        
        # If no context could be extracted, need clarification
        print(f"Analysis: Need additional information to distinguish between codes")
        return {
            'sufficient': False,
            'reasoning': 'Need additional information to distinguish between codes',
            'missing_info': ['Additional context required to select specific commodity code']
        }

    def _extract_year_from_context(self, original_question: str, product_name: str, product_info_text: str) -> Optional[str]:
        """Extract manufacturing year from available context"""
        import re
        
        # Method 1: Look for 4-digit year in product name
        year_matches = re.findall(r'\b(20\d{2})\b', product_name)
        if year_matches:
            return year_matches[0]  # "2022"
        
        # Method 2: Look in original query
        year_matches = re.findall(r'\b(20\d{2})\b', original_question)
        if year_matches:
            return year_matches[0]
        
        # Method 3: Parse collected information for year references
        year_matches = re.findall(r'\b(20\d{2})\b', product_info_text)
        if year_matches:
            return year_matches[0]
        
        return None

    def _can_determine_importer_from_context(self, original_question: str, product_name: str) -> Optional[str]:
        """Try to infer importer type from context"""
        
        # Look for hints in the query
        query_lower = original_question.lower()
        name_lower = product_name.lower()
        
        # Individual indicators
        if any(word in query_lower for word in ['my', 'personal', 'buy', 'purchase', 'individual']):
            return 'individual'
        
        # Dealer indicators  
        if any(word in query_lower for word in ['import', 'dealer', 'business', 'resale', 'inventory']):
            return 'dealer'
        
        # Default assumption for consumer products
        if any(word in name_lower for word in ['tesla', 'bmw', 'mercedes', 'car', 'suv']):
            return 'individual'  # Most personal vehicles are imported by individuals
        
        return None

    def generate_clarification_questions(self, original_question: str, commodity_matches: List[Dict], 
                                        product_name: str, product_info_text: str, missing_info: List[str]) -> List[Dict]:
        """
        Use LLM to generate specific, user-friendly questions based on missing information.
        
        Args:
            original_question: The original user question
            commodity_matches: List of matching commodity codes
            product_name: Name of the product
            product_info_text: Available product information
            missing_info: List of missing information categories
            
        Returns:
            List of question dictionaries with question text, type, options, etc.
        """
        


        # Generate simple questions based on product type
        questions = []
        
        # Check if this is a vehicle-related product
        if any(keyword in product_name.lower() for keyword in ['tesla', 'vehicle', 'car', 'truck', 'motor']):
            questions.append({
                "id": "importer_type",
                "question": "Who is importing this vehicle?",
                "type": "choice",
                "options": [
                    {"value": "individual", "label": "An individual for personal use"},
                    {"value": "dealer", "label": "A dealer for resale"}
                ],
                "help_text": "This helps determine the correct tariff classification."
            })
            
            questions.append({
                "id": "manufacture_year",
                "question": "What year was this vehicle manufactured?",
                "type": "number",
                "unit": "year",
                "help_text": "You can find this on the vehicle's VIN plate or documentation.",
                "validation": {
                    "min": 2000,
                    "max": 2025
                }
            })
        
        # Check if this is a food/agricultural product
        elif any(keyword in product_name.lower() for keyword in ['banana', 'fruit', 'vegetable', 'food']):
            questions.append({
                "id": "processing_state",
                "question": "What is the processing state of this product?",
                "type": "choice",
                "options": [
                    {"value": "fresh", "label": "Fresh/raw"},
                    {"value": "dried", "label": "Dried"},
                    {"value": "frozen", "label": "Frozen"},
                    {"value": "processed", "label": "Processed/cooked"}
                ],
                "help_text": "This helps determine the correct commodity code."
            })
        
        # Default generic question if no specific type detected
        if not questions:
            questions.append({
                "id": "additional_info",
                "question": "Please provide additional details about this product",
                "type": "text",
                "help_text": "Any additional information that might help classify this product correctly."
            })
        
        return questions
    
    def _fallback_questions(self, missing_info: List[str], product_name: str) -> List[Dict]:
        """Generate basic fallback questions if LLM fails."""
        fallback = []
        for i, info in enumerate(missing_info):
            fallback.append({
                'id': f'question_{i+1}',
                'question': f'Please provide information about: {info}',
                'type': 'text',
                'help_text': f'This information is needed to classify {product_name} correctly.'
            })
        return fallback

    def select_best_commodity_code(self, hs_code: str, commodity_matches: List[Dict], 
                                  product_name: str, product_info_text: str, 
                                  extracted_context: Dict = None) -> Optional[Dict]:
        """
        Use LLM to select the most appropriate commodity code from matches.
        """
        if not commodity_matches or not self.use_llm_selection:
            return None
            
        if len(commodity_matches) == 1:
            # Only one match, return it with high confidence
            selected = {
                **commodity_matches[0],
                'confidence': 0.95,
                'reasoning': 'Only one commodity code match found',
                'selection_method': 'single_match',
                'selected': True  # Mark as selected
            }
            return selected
        
        # Build options for LLM
        option_lines = []
        for idx, match in enumerate(commodity_matches[:10]):  # Limit to top 10 for LLM
            option_lines.append(f"{idx+1}. {match['tariff_code']}")
            option_lines.append(f"   Description: {match['description']}")
            option_lines.append("")

        options_text = "\n".join(option_lines)

        # Build context information for the prompt
        context_info = ""
        if extracted_context:
            context_info = "\n\nExtracted Context Information:\n"
            for key, value in extracted_context.items():
                context_info += f"- {key.replace('_', ' ').title()}: {value}\n"

        prompt = f"""You are an expert in tariff classification and commodity codes.

Product: {product_name}
Product Information: {product_info_text}
HS Code: {hs_code}{context_info}

The following commodity codes (10-digit tariff codes) were found that start with this HS code. Please select the most appropriate and specific commodity code for this product.

{options_text}

Consider:
- The product's specific characteristics and use
- The level of detail and specificity in each description
- Which description most accurately matches the actual product
- The intended use and market for this product
- Use the extracted context information to make more informed decisions

Please provide your analysis in this EXACT JSON format:
{{
    "selected_code": "0706101000",  // The exact tariff code you selected, or "NONE" if none are suitable
    "reasoning": "Explanation of why this code is most appropriate",
    "confidence": "high"  // Must be one of: "high", "medium", "low"
}}

If none of the codes are appropriate, respond with:
{{
    "selected_code": "NONE",
    "reasoning": "Explanation of why none are suitable",
    "confidence": "low"
}}"""

        # Print the prompt for debugging
        print(f"\n🤖 LLM Prompt:")
        print("-" * 50)
        print(prompt)
        print("-" * 50)

        try:
            response = reason_with_llm_for_commodity(prompt, model_alias="mistral_small")
            
            # Print LLM response for debugging
            print(f"\n🤖 LLM Response:")
            print("-" * 50)
            print(response)
            print("-" * 50)

            # Parse JSON response
            try:
                # Clean the response - remove markdown code blocks if present
                cleaned_response = response.strip()
                
                # Handle markdown code blocks more robustly
                if '```json' in cleaned_response:
                    # Extract content between ```json and ```
                    start_marker = '```json'
                    end_marker = '```'
                    start_idx = cleaned_response.find(start_marker) + len(start_marker)
                    end_idx = cleaned_response.rfind(end_marker)
                    if end_idx > start_idx:
                        cleaned_response = cleaned_response[start_idx:end_idx].strip()
                elif cleaned_response.startswith('```') and cleaned_response.endswith('```'):
                    # Handle generic code blocks
                    cleaned_response = cleaned_response[3:-3].strip()
                
                # Debug: Print the cleaned response
                print(f"🔍 DEBUG: Cleaned JSON response: '{cleaned_response}'")
                
                result = json.loads(cleaned_response)
                selected_code = result.get('selected_code')
                reasoning = result.get('reasoning', '')
                confidence = result.get('confidence', 'medium')

                if selected_code == 'NONE':
                    return None

                # Find the matching commodity code
                for match in commodity_matches:
                    if match['tariff_code'] == selected_code:
                        # Convert confidence to score
                        confidence_scores = {'high': 0.95, 'medium': 0.7, 'low': 0.4}
                        selected = {
                            **match,
                            'confidence': confidence_scores.get(confidence, 0.7),
                            'reasoning': reasoning,
                            'selection_method': 'llm_selected',
                            'selected': True  # Mark as selected
                        }
                        return selected

                logger.warning(f"Selected code {selected_code} not found in matches")
                return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"Error in commodity code selection with context: {str(e)}")
            return None



# ═══════════════════════════════════════════════════════════════════════════════
# LLM UTILITIES (Supporting functions for AI reasoning)
# ═══════════════════════════════════════════════════════════════════════════════

def reason_with_llm_for_commodity(prompt: str, model_alias: str = "mistral_small") -> str:
    """
    Send a reasoning prompt to the LLM for commodity code selection.
    
    Args:
        prompt: The prompt to send to the LLM
        model_alias: Which model to use (defaults to mistral_small)
        
    Returns:
        The LLM's response as a string
    """
    messages = [
        {"role": "system", "content": "You are an expert in tariff classification and commodity codes. You MUST respond with valid JSON only, with no additional text or explanation. Your response should be parseable by json.loads()."},
        {"role": "user", "content": prompt}
    ]
    return chat_completion(messages, model_alias=model_alias)

def chat_completion(messages, model_alias="mistral_small"):
    """
    Handle LLM API calls for single model classification.
    
    Args:
        messages: List of message objects for the chat completion
        model_alias: Which model configuration to use
        
    Returns:
        The completion response content
    """
    return call_llm(messages, model_alias, OPENROUTER_CONFIG, OPENROUTER_MODELS)

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
        logger.error(f"LLM response has empty choices array: {result}")
        return ""
    
    choice = result["choices"][0]
    if "message" not in choice:
        logger.error(f"LLM response choice missing 'message' key: {choice}")
        return ""
    
    if "content" not in choice["message"]:
        logger.error(f"LLM response message missing 'content' key: {choice['message']}")
        return ""
    
    content = choice["message"]["content"]
    logger.info(f"LLM response content: '{content}'")
    return content

# ═══════════════════════════════════════════════════════════════════════════════
# CLI INTERFACE (Only used when running as a standalone script)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    """Parse command line arguments for CLI usage."""
    parser = argparse.ArgumentParser(description="Lookup commodity codes with LLM selection.")
    parser.add_argument(
        "--product", "-p", help="Product name (free text)", default=None
    )
    parser.add_argument(
        "--hs-codes",
        "-c",
        help="Comma-separated list of 6-digit HS codes",
        default=None,
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to JSON file produced by hs_code.py (overrides other flags)",
        default=None,
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM selection, return all matches"
    )
    return parser.parse_args()

def read_input(args: argparse.Namespace) -> tuple[str | None, List[str]]:
    """
    Read input from various sources based on CLI arguments.
    
    Returns (product_name, [hs_codes]).
    Precedence: --input file > --hs-codes flag > STDIN.
    """
    # 1. JSON file
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                payload = json.load(f)
            product = payload.get("product")
            hs_codes = payload.get("hs_codes", "")
            return product, _split_codes(hs_codes)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to read %s: %s", args.input, exc)
            sys.exit(1)

    # 2. Command-line codes
    if args.hs_codes:
        return args.product, _split_codes(args.hs_codes)

    # 3. STDIN fallback
    try:
        stdin_data = sys.stdin.read().strip()
        if not stdin_data:
            raise ValueError("No input provided.")
        payload = json.loads(stdin_data)
        product = payload.get("product")
        hs_codes = payload.get("hs_codes", "")
        return product, _split_codes(hs_codes)
    except Exception as exc:  # noqa: BLE001
        logger.error("Missing or invalid input: %s", exc)
        sys.exit(1)

def _split_codes(raw: str) -> List[str]:
    """Split comma-separated HS codes into a list."""
    return [code.strip() for code in raw.split(",") if code.strip()]

def main() -> None:
    """Main CLI entry point with interactive question/answer support."""
    args = parse_args()
    product_name, hs_codes = read_input(args)

    if not hs_codes:
        logger.error("At least one HS code is required.")
        sys.exit(1)

    # Use interactive lookup for CLI
    if not args.no_llm:
        print("🚀 Starting interactive commodity code lookup...")
        original_question = f"What is the commodity code for {product_name}" if product_name else "Find commodity codes"
        
        matches = interactive_commodity_lookup(
            hs_codes, 
            product_name or "Unknown Product", 
            "", 
            original_question
        )
        
        print(f"\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        
        for hs_code, result in matches.items():
            if isinstance(result, list) and result:
                selected = result[0]
                print(f"\n✅ {hs_code}: {selected['tariff_code']}")
                print(f"   Description: {selected['description']}")
                print(f"   Confidence: {selected.get('confidence', 'N/A')}")
                print(f"   Reasoning: {selected.get('reasoning', 'N/A')}")
            elif isinstance(result, dict) and result.get('requires_clarification'):
                print(f"\n❌ {hs_code}: Still requires clarification")
            else:
                print(f"\n❌ {hs_code}: No suitable commodity code found")
    else:
        # Original non-LLM mode
        lookup = CommodityCodeLookup(SUPABASE_URL, SUPABASE_KEY, use_llm_selection=False)
        matches = lookup.find_matching_codes(hs_codes)

        output = {
            "product": product_name,
            "matches": {
                hs: {"count": len(codes), "codes": codes} for hs, codes in matches.items()
            },
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

# ═══════════════════════════════════════════════════════════════════════════════
# SCRIPT EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()