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
            
            # Check if sufficient information for analysis
            info_analysis = lookup.analyze_if_sufficient_info(
                original_question, all_matches, product_name, enhanced_product_info, order_id
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
                    enhanced_product_info, info_analysis['missing_attributes']
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
                         original_question: str = "", order_id: str = None) -> dict:
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
                print(f"├── {hs_code}: [X] No commodity codes found")
                results[hs_code] = None
                continue
            
            print(f"├── {hs_code}: Found {len(all_matches)} commodity codes, analyzing with LLM...")
            
            # Print found commodity codes for debugging
            print(f"\n📋 Found {len(all_matches)} commodity codes:")
            for match in all_matches:
                print(f"   • {match['tariff_code']}: {match['description']}")
            
            # STEP 1: Check if we have sufficient information to proceed
            print(f"\n[ANALYZING] INFORMATION SUFFICIENCY")
            print("-" * 50)
            
            info_analysis = lookup.analyze_if_sufficient_info(
                original_question, all_matches, product_name, product_info_text, order_id
            )
            
            print(f"Analysis: {info_analysis['reasoning']}")
            
            if info_analysis['sufficient']:
                print(f"[OK] Sufficient information available - proceeding with selection")
                
                # Use LLM to select best match with extracted context if available
                best_match = lookup.select_best_commodity_code(
                    hs_code, all_matches, product_name, product_info_text,
                    info_analysis.get('extracted_context', {})
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
                print(f"[X] Insufficient information - clarification needed")
                print(f"Missing information: {', '.join(info_analysis['missing_info'])}")
                
                # Generate specific questions using LLM
                print(f"\n[LLM] GENERATING CLARIFICATION QUESTIONS")
                print("-" * 50)
                
                questions = lookup.generate_clarification_questions(
                    original_question, all_matches, product_name, 
                    product_info_text, info_analysis['missing_attributes']
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

    def analyze_if_sufficient_info(self, original_question: str, commodity_matches: List[Dict], 
                                  product_name: str, product_info_text: str, order_id: str = None) -> Dict:
        """
        Determine if we have sufficient information to make a definitive commodity code selection.
        Completely generic approach that discovers attributes dynamically from descriptions.
        """
        
        if len(commodity_matches) == 1:
            return {
                'sufficient': True,
                'reasoning': 'Only one commodity code match found',
                'missing_info': [],
                'extracted_context': {}
            }
        
        print(f"\n[EXTRACTING] DISTINGUISHING ATTRIBUTES")
        print("-" * 50)
        
        # STEP 1: Use LLM to extract contextual attributes that distinguish codes
        print(f"[STEP 1] Analyzing commodity code descriptions to find distinguishing attributes...")
        distinguishing_attributes = self._extract_contextual_attributes_with_llm(commodity_matches)
        print(f"[RESULT] Found {len(distinguishing_attributes)} distinguishing attribute(s): {distinguishing_attributes}")
        
        if not distinguishing_attributes:
            print(f"[DECISION] No distinguishing attributes found - treating as sufficient")
            return {
                'sufficient': True,
                'reasoning': 'No distinguishing attributes found between commodity codes',
                'missing_info': [],
                'missing_attributes': [],
                'extracted_context': {},
                'distinguishing_attributes': []
            }
        
        # STEP 2: Check product context for those specific attributes
        print(f"\n[STEP 2] Checking product context for each attribute...")
        print(f"[CONTEXT] Product: '{product_name}'")
        print(f"[CONTEXT] Info: '{product_info_text}'")
        print(f"[CONTEXT] Question: '{original_question}'")
        
        found_context = self._check_product_context_for_attributes(
            distinguishing_attributes, product_name, product_info_text, original_question, order_id
        )
        
        print(f"[RESULT] Found context for {len(found_context)} attribute(s):")
        for attr, value in found_context.items():
            print(f"   - {attr}: '{value}'")
        
        # STEP 3: Decide sufficiency
        print(f"\n[STEP 3] Determining information sufficiency...")
        missing_attributes = [attr for attr in distinguishing_attributes if attr not in found_context]
        
        print(f"[ANALYSIS] Distinguishing attributes: {distinguishing_attributes}")
        print(f"[ANALYSIS] Found in context: {list(found_context.keys())}")
        print(f"[ANALYSIS] Missing from context: {missing_attributes}")
        
        if not missing_attributes:
            print(f"\n[DECISION] SUFFICIENT: All distinguishing attributes found in product context")
            print(f"[REASONING] We have enough information to distinguish between the commodity codes")
            return {
                'sufficient': True,
                'reasoning': f'Found all distinguishing attributes: {list(found_context.keys())}',
                'missing_info': [],
                'missing_attributes': [],
                'extracted_context': found_context,
                'distinguishing_attributes': distinguishing_attributes
            }
        
        # Generate questions for missing attributes
        print(f"\n[DECISION] INSUFFICIENT: Missing {len(missing_attributes)} distinguishing attribute(s)")
        print(f"[REASONING] Cannot distinguish between commodity codes without: {', '.join(missing_attributes)}")
        
        questions = self._generate_targeted_questions(missing_attributes)
        print(f"[QUESTIONS] Generated {len(questions)} clarification question(s):")
        for i, question in enumerate(questions, 1):
            print(f"   {i}. {question}")
        
        return {
            'sufficient': False,
            'reasoning': f'Missing attributes: {", ".join(missing_attributes)}',
            'missing_info': questions,
            'missing_attributes': missing_attributes,
            'extracted_context': found_context,
            'distinguishing_attributes': distinguishing_attributes
        }

    def _extract_contextual_attributes_with_llm(self, commodity_matches: List[Dict]) -> List[str]:
        """Use LLM to identify contextual attributes that distinguish between tariff codes."""
        if len(commodity_matches) < 2:
            return []
        
        # Prepare descriptions for LLM analysis
        descriptions = []
        for i, match in enumerate(commodity_matches):
            descriptions.append(f"{i+1}. {match['tariff_code']}: {match['description']}")
        
        descriptions_text = "\n".join(descriptions)
        
        # Improved prompt with clear examples and format
        prompt = f"""You are a tariff classification expert. Analyze these commodity code descriptions and identify the key attributes that distinguish between them for customs classification purposes.

TARIFF CODES:
{descriptions_text}

Your task is to identify the distinguishing attributes that differentiate these codes. Look for patterns like:
- Importer type (individuals, dealers, companies)
- Product age/condition (new, used, years since manufacture)
- Usage purpose (commercial, personal, industrial)
- Physical characteristics (size, weight, capacity, material)
- Origin or destination requirements
- Licensing or permit requirements

EXAMPLE:
For codes about vehicles imported by individuals vs dealers with different age limits, the attributes would be:
- importer_type
- vehicle_age_category

OUTPUT FORMAT:
List only the distinguishing attribute names, one per line, using lowercase with underscores for multi-word attributes:

importer_type
vehicle_age_category
usage_purpose

DISTINGUISHING ATTRIBUTES:"""
        
        try:
            print(f"[LLM] Sending improved prompt to extract attributes...")
            response = reason_with_llm_fn(prompt)
            print(f"[LLM] Raw response: {response}")
            
            # Simplified parsing - extract lines that look like attribute names
            attributes = []
            lines = response.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines, headers, and explanatory text
                if not line or line.startswith('#') or line.startswith('DISTINGUISHING') or line.startswith('OUTPUT'):
                    continue
                    
                # Remove any numbering, bullets, or markdown
                clean_line = line.lstrip('0123456789. -•*')
                
                # Remove quotes and extra formatting
                clean_line = clean_line.replace('"', '').replace("'", '').replace('`', '').strip()
                
                # Check if it looks like an attribute name (lowercase, underscores, reasonable length)
                if (clean_line and 
                    len(clean_line) > 2 and 
                    clean_line.islower() and 
                    '_' in clean_line and
                    clean_line.replace('_', '').replace(' ', '').isalpha()):
                    
                    attributes.append(clean_line)
                    print(f"[PARSING] Added attribute: '{clean_line}'")
                
                # Also handle space-separated attributes that need conversion
                elif (clean_line and 
                      len(clean_line) > 2 and 
                      ' ' in clean_line and
                      clean_line.replace(' ', '').isalpha()):
                    
                    # Convert spaces to underscores
                    converted = clean_line.lower().replace(' ', '_')
                    attributes.append(converted)
                    print(f"[PARSING] Converted and added: '{clean_line}' -> '{converted}'")
            
            print(f"[RESULT] Extracted {len(attributes)} attributes: {attributes}")
            
            # If we didn't get any attributes, try a more direct approach
            if not attributes:
                print("[FALLBACK] No attributes found, trying direct extraction...")
                return self._direct_attribute_extraction(commodity_matches)
            
            # Remove duplicates while preserving order
            unique_attributes = []
            seen = set()
            for attr in attributes:
                if attr not in seen:
                    unique_attributes.append(attr)
                    seen.add(attr)
            
            return unique_attributes
            
        except Exception as e:
            print(f"[ERROR] Error extracting attributes with LLM: {e}")
            return self._direct_attribute_extraction(commodity_matches)

    def _direct_attribute_extraction(self, commodity_matches: List[Dict]) -> List[str]:
        """Fallback method to extract attributes using text analysis patterns."""
        print("[FALLBACK] Using direct text analysis to extract attributes...")
        
        descriptions = [match['description'].lower() for match in commodity_matches]
        attributes = []
        
        # Common patterns in tariff classifications
        patterns = {
            'importer_type': ['individual', 'dealer', 'company', 'commercial', 'business'],
            'vehicle_age': ['year', 'old', 'new', 'age', 'manufacture'],
            'usage_purpose': ['commercial', 'personal', 'industrial', 'domestic'],
            'weight_category': ['kg', 'ton', 'gram', 'weight', 'heavy', 'light'],
            'size_category': ['large', 'small', 'medium', 'size', 'dimension'],
            'material_type': ['steel', 'aluminum', 'plastic', 'wood', 'metal'],
            'power_type': ['electric', 'manual', 'hydraulic', 'pneumatic'],
            'capacity_range': ['capacity', 'volume', 'liter', 'gallon']
        }
        
        # Check which patterns appear in the descriptions
        for pattern_name, keywords in patterns.items():
            pattern_found = False
            for desc in descriptions:
                if any(keyword in desc for keyword in keywords):
                    # Check if there's variation in this attribute across descriptions
                    variations = set()
                    for desc in descriptions:
                        for keyword in keywords:
                            if keyword in desc:
                                variations.add(keyword)
                    
                    # If we have multiple variations, it's a distinguishing attribute
                    if len(variations) > 1:
                        attributes.append(pattern_name)
                        pattern_found = True
                        print(f"[PATTERN] Found distinguishing attribute: {pattern_name} with variations: {variations}")
                        break
            
            if pattern_found:
                continue
        
        # Also look for numeric patterns (age ranges, weight limits, etc.)
        numeric_pattern_found = False
        for desc in descriptions:
            if any(char.isdigit() for char in desc):
                if not numeric_pattern_found:
                    # Check if numbers vary across descriptions
                    numbers_in_descriptions = []
                    for d in descriptions:
                        import re
                        numbers = re.findall(r'\d+', d)
                        numbers_in_descriptions.extend(numbers)
                    
                    if len(set(numbers_in_descriptions)) > 1:
                        attributes.append('numeric_specification')
                        numeric_pattern_found = True
                        print(f"[PATTERN] Found numeric variations: {set(numbers_in_descriptions)}")
        
        print(f"[FALLBACK] Extracted {len(attributes)} attributes using pattern matching: {attributes}")
        return attributes

    def _retry_llm_attribute_extraction(self, commodity_matches: List[Dict]) -> List[str]:
        """Retry LLM attribute extraction with a more structured prompt."""
        if len(commodity_matches) < 2:
            return []
        
        # Create a more structured comparison
        comparison_text = "TARIFF CODE COMPARISON:\n"
        for i, match in enumerate(commodity_matches):
            comparison_text += f"Code {i+1}: {match['tariff_code']}\n"
            comparison_text += f"Description: {match['description']}\n\n"
        
        # More direct prompt
        retry_prompt = f"""{comparison_text}

Identify what makes these tariff codes different from each other. What are the key distinguishing factors?

Output only the attribute names that differentiate these codes, one per line, using this format:
- Use lowercase letters only
- Use underscores instead of spaces
- Examples: importer_type, vehicle_age, usage_purpose

ATTRIBUTES:"""
        
        try:
            print(f"[RETRY] Sending structured prompt to LLM...")
            response = reason_with_llm_fn(retry_prompt)
            print(f"[RETRY] LLM response: {response}")
            
            # Simple parsing for the retry
            attributes = []
            for line in response.strip().split('\n'):
                line = line.strip().lower()
                
                # Remove common prefixes and clean up
                line = line.lstrip('- •*0123456789. ')
                line = line.replace('"', '').replace("'", '')
                
                # Check if it's a valid attribute name
                if (line and len(line) > 2 and 
                    line.replace('_', '').isalpha() and
                    ('_' in line or ' ' not in line)):
                    
                    # Convert spaces to underscores if needed
                    if ' ' in line:
                        line = line.replace(' ', '_')
                    
                    attributes.append(line)
                    print(f"[RETRY] Extracted: {line}")
            
            return attributes
            
        except Exception as e:
            print(f"[RETRY] Error in retry attempt: {e}")
            return self._direct_attribute_extraction(commodity_matches)

    def _check_product_context_for_attributes(self, attributes: List[str], product_name: str, 
                                            product_info: str, original_question: str, 
                                            order_id: str = None) -> Dict:
        """Look for specific attributes in product context, using order documents if available."""
        found_context = {}
        
        # Try to load order-specific context if order_id is provided
        order_context = None
        if order_id:
            order_context = self._load_order_context(order_id)
        
        if order_context:
            print(f"[CONTEXT] Using order-specific context for order {order_id}")
            # Use document-based context extraction
            found_context = self._extract_attributes_from_order_context(attributes, order_context)
        else:
            print(f"[CONTEXT] Using basic text analysis (no order context available)")
            # Fallback to basic text analysis
            found_context = self._extract_attributes_from_text(attributes, product_name, product_info, original_question)
        
        return found_context
    
    def _load_order_context(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Load context from order documents."""
        try:
            # Construct file paths
            base_path = f"processed_data/orders/{order_id}/primary_process"
            bol_path = f"{base_path}/bill_of_lading_{order_id}_primary_extract.json"
            invoice_path = f"{base_path}/invoice_{order_id}_primary_extract.json"
            
            # Check if files exist
            if not os.path.exists(bol_path) or not os.path.exists(invoice_path):
                print(f"[WARNING] Order documents not found for {order_id}")
                return None
            
            # Load documents
            with open(bol_path, 'r') as f:
                bill_of_lading = json.load(f)
            
            with open(invoice_path, 'r') as f:
                invoice = json.load(f)
            
            # Extract context using DocumentContextExtractor
            extractor = DocumentContextExtractor()
            context = extractor.extract_context_from_documents(bill_of_lading, invoice)
            
            print(f"[CONTEXT] Loaded order context: {list(context.keys())}")
            return context
            
        except Exception as e:
            print(f"[ERROR] Failed to load order context for {order_id}: {e}")
            return None
    
    def _extract_attributes_from_order_context(self, attributes: List[str], order_context: Dict[str, Any]) -> Dict[str, str]:
        """Extract specific attributes from order document context."""
        found_context = {}
        
        # Map LLM-extracted attributes to document context attributes
        attribute_mapping = {
            'importer_type': 'importer_type',
            'vehicle_age_category': 'product_age_category',
            'usage_purpose': 'usage_purpose',
            'value_category': 'value_category',
            'quantity_category': 'quantity_category',
            'size_weight_category': 'size_weight_category',
            'origin_country': 'origin_country'
        }
        
        for attr in attributes:
            print(f"\n[ATTRIBUTE] Checking '{attr}' in order context...")
            
            # Check if we have a direct mapping
            if attr in attribute_mapping:
                mapped_attr = attribute_mapping[attr]
                if mapped_attr in order_context:
                    found_context[attr] = str(order_context[mapped_attr])
                    print(f"   [MATCH] Found '{attr}' -> '{mapped_attr}': {order_context[mapped_attr]}")
                else:
                    print(f"   [NO MATCH] Mapped attribute '{mapped_attr}' not found in order context")
            else:
                # Check if the attribute exists directly in order context
                if attr in order_context:
                    found_context[attr] = str(order_context[attr])
                    print(f"   [MATCH] Found '{attr}': {order_context[attr]}")
                else:
                    print(f"   [NO MATCH] Attribute '{attr}' not found in order context")
        
        return found_context
    
    def _extract_attributes_from_text(self, attributes: List[str], product_name: str, 
                                    product_info: str, original_question: str) -> Dict[str, str]:
        """Fallback method: extract attributes from basic text analysis."""
        found_context = {}
        all_text = f"{original_question} {product_name} {product_info}".lower()
        
        print(f"[CONTEXT] Analyzing text: '{all_text[:100]}{'...' if len(all_text) > 100 else ''}'")
        
        for attr in attributes:
            print(f"\n[ATTRIBUTE] Checking '{attr}'...")
            attr_lower = attr.lower()
            found = False
            reason = ""
            
            # Check if the attribute name itself appears in the text
            if attr.replace('_', ' ') in all_text or attr in all_text:
                found_context[attr] = 'found'
                found = True
                reason = f"Attribute name '{attr}' found in text"
                print(f"   [MATCH] {reason}")
            
            # Generic pattern matching - look for words that might relate to this attribute
            else:
                # Extract the core word from the attribute name
                core_word = attr_lower.replace('_', ' ').split()[-1]  # Get the last word
                
                # Look for the core word or related terms in the text
                if core_word in all_text:
                    found_context[attr] = 'detected'
                    found = True
                    reason = f"Core word '{core_word}' found in text"
                    print(f"   [MATCH] {reason}")
                else:
                    print(f"   [NO MATCH] Core word '{core_word}' not found in text")
            
            if not found:
                print(f"   [NO MATCH] No patterns matched for attribute '{attr}'")
        
        return found_context

    def _generate_targeted_questions(self, missing_attributes: List[str]) -> List[str]:
        """Generate questions only for missing attributes."""
        questions = []
        
        for attr in missing_attributes:
            # Convert attribute name to a human-readable question
            attr_display = attr.replace('_', ' ').title()
            
            # Generate context-appropriate questions based on attribute name patterns
            if 'type' in attr.lower():
                questions.append(f"What {attr_display.lower()} applies to this product?")
            elif 'age' in attr.lower() or 'year' in attr.lower():
                questions.append(f"What {attr_display.lower()} applies to this product?")
            elif 'class' in attr.lower():
                questions.append(f"What {attr_display.lower()} applies to this product?")
            elif 'size' in attr.lower() or 'weight' in attr.lower() or 'capacity' in attr.lower():
                questions.append(f"What {attr_display.lower()} applies to this product?")
            else:
                # Generic question for any attribute
                questions.append(f"What {attr_display.lower()} applies to this product?")
        
        return questions

    def generate_clarification_questions(self, original_question: str, commodity_matches: List[Dict], 
                                        product_name: str, product_info_text: str, missing_attributes: List[str]) -> List[Dict]:
        """
        Generate questions based on missing attributes, not product type detection.
        
        Args:
            original_question: The original user question
            commodity_matches: List of matching commodity codes
            product_name: Name of the product
            product_info_text: Available product information
            missing_attributes: List of missing attribute names
            
        Returns:
            List of question dictionaries with question text, type, options, etc.
        """
        return self._generate_targeted_questions(missing_attributes)
    
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
        print(f"\n[LLM] PROMPT:")
        print("-" * 50)
        print(prompt)
        print("-" * 50)

        try:
            response = reason_with_llm_for_commodity(prompt, model_alias="mistral_small")
            
            # Print LLM response for debugging
            print(f"\n[LLM] RESPONSE:")
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
                print(f"[DEBUG] Cleaned JSON response: '{cleaned_response}'")
                
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
                print(f"\n[OK] {hs_code}: {selected['tariff_code']}")
                print(f"   Description: {selected['description']}")
                print(f"   Confidence: {selected.get('confidence', 'N/A')}")
                print(f"   Reasoning: {selected.get('reasoning', 'N/A')}")
            elif isinstance(result, dict) and result.get('requires_clarification'):
                print(f"\n[X] {hs_code}: Still requires clarification")
            else:
                print(f"\n[X] {hs_code}: No suitable commodity code found")
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

def test_context_extraction():
    """Test the context extraction with sample data."""
    
    # Sample data from your files
    bill_of_lading = {
        "consignee_name": "RAFER JOHNSON",
        "shipper": "AMAZON",
        "weight": "78.93 KGM",
        "commodity": "2 CTNS STC: SOLAR GENERATOR X20250109665963 MARKS:",
        "port_of_origin": "MIAMI, UNITED STATES OF AMERICA",
        "reported_date": "13/01/2025"
    }
    
    invoice = {
        "supplier": {"name": "EcoFlow Inc."},
        "buyer": {"name": "Andria Scott"},
        "invoice_details": {"date": "2024-10-10"},
        "items": [{
            "description": "EF ECOFLOW Solar Generator DELTA 2 Max 2048Wh with 4X100W 12V Solar Panels, High Efficiency Monocrystalline PV Modules, 2400W LFP Portable Power Station, AC + Solar Fast Dual Charging For Camping RV",
            "quantity": 1.0
        }],
        "totals": {"total_amount": 1496.93}
    }
    
    extractor = DocumentContextExtractor()
    context = extractor.extract_context_from_documents(bill_of_lading, invoice)
    
    print("Extracted Context:")
    for key, value in context.items():
        print(f"  {key}: {value}")
    
    return context

if __name__ == "__main__":
    main()