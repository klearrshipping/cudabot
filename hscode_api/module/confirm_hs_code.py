import sys
import os
import logging
import requests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
# Import config from the hscode_api directory
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
hscode_api_dir = os.path.dirname(current_dir)
sys.path.insert(0, hscode_api_dir)

from config import SUPABASE_URL, SUPABASE_KEY, OPENROUTER_API_KEY, OPENROUTER_CONFIG, OPENROUTER_MODELS
import re
import json
from datetime import datetime

# Import LLM function with error handling
try:
    from .commodity_code import reason_with_llm_fn
    COMMODITY_LLM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import reason_with_llm_fn: {e}")
    COMMODITY_LLM_AVAILABLE = False

# ───────────────────────────── LLM Helper ──────────────────────────────
def call_llm(messages, model_alias, config, models):
    model = models[model_alias]["name"]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": models[model_alias].get("temperature", 0.7),
        "max_tokens": models[model_alias].get("max_tokens", 1000),
    }
    response = requests.post(
        config["api_url"],
        headers=config["headers"],
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]

def chat_completion(messages, model_alias="gpt-4o-mini"):
    return call_llm(messages, model_alias, OPENROUTER_CONFIG, OPENROUTER_MODELS)

# ───────────────────────────── Reasoning Function ──────────────────────────────

class HSCodeReconciler:
    def __init__(self, supabase_client: Client, reason_with_llm_fn, verbose=True):
        """
        reason_with_llm_fn → function(prompt_text) → returns LLM response (string)
        """
        self.supabase = supabase_client
        self.reason_with_llm = reason_with_llm_fn
        self.verbose = verbose

    def reconcile_hs_code(self, model_hs_code: str, product_name: str, product_info_text: str) -> dict:
        print(f"🔍 DEBUG: Starting reconcile_hs_code for {model_hs_code}")
        
        try:
            if self.verbose:
                print(f"\n🔍 Reconciling HS code: {model_hs_code}")
                print(f"📦 Product: {product_name}")

            # Format HS code for lookup → 851712 → '8517.12'
            formatted_hs_code = self._format_hs_code(model_hs_code)
            heading_prefix = model_hs_code[:4]

            # COMPREHENSIVE PARALLEL QUERIES
            if self.verbose:
                print(f"\n{'='*60}")
                print("📊 QUERYING ALL DATABASES")
                print(f"{'='*60}")

            # Query 1: Comprehensive Tariff Codes Search
            tariff_results = self._comprehensive_tariff_search(model_hs_code, heading_prefix)
            
            # Query 2: Comprehensive HS Codes 2022 Search
            hs_results = self._comprehensive_hs_search(formatted_hs_code, heading_prefix)
            
            # Display findings based on verbosity
            if self.verbose:
                self._display_all_findings(tariff_results, hs_results)
            else:
                self._display_compact_findings(model_hs_code, tariff_results, hs_results)

            # DEBUG: Check if we reach this point
            print(f"🔍 DEBUG: About to start verification process for {model_hs_code}")

            # Now proceed with verification based on what was found
            if self.verbose:
                print(f"\n{'='*60}")
                print("🔍 VERIFICATION PROCESS")
                print(f"{'='*60}")

            # Collect all options for LLM evaluation
            all_options = []
            
            # DEBUG: Check options collection
            print(f"🔍 DEBUG: Starting options collection...")
            
            # Add tariff options (use ALL matches for LLM processing)
            if tariff_results['exact_matches'] or tariff_results['heading_matches']:
                tariff_matches = (tariff_results['exact_matches'] or []) + (tariff_results['heading_matches'] or [])
                for match in tariff_matches:
                    all_options.append({
                        'code': match['tariff_code'],
                        'formatted_code': match['tariff_code'][:4] + "." + match['tariff_code'][4:6],
                        'description': match['description'],
                        'source': 'tariff_codes',
                        'match_type': 'exact' if match in (tariff_results['exact_matches'] or []) else 'heading'
                    })
            
            # Add HS code options
            if hs_results['exact_match'] or hs_results['heading_matches']:
                if hs_results['exact_match']:
                    all_options.append({
                        'code': hs_results['exact_match']['hs_code'],
                        'formatted_code': hs_results['exact_match']['hs_code'],
                        'description': hs_results['exact_match']['description'],
                        'source': 'hs_codes_2022',
                        'match_type': 'exact'
                    })
                for match in (hs_results['heading_matches'] or []):
                    # Avoid duplicates
                    if not any(opt['formatted_code'] == match['hs_code'] for opt in all_options):
                        all_options.append({
                            'code': match['hs_code'],
                            'formatted_code': match['hs_code'],
                            'description': match['description'],
                            'source': 'hs_codes_2022',
                            'match_type': 'heading'
                        })

            # DEBUG: Check all_options
            print(f"🔍 DEBUG: Collected {len(all_options)} total options")
            for i, opt in enumerate(all_options):
                print(f"   Option {i+1}: {opt['formatted_code']} from {opt['source']}")
                print(f"      Description: {opt.get('description', 'No description available')}")

            if not all_options:
                # No matches found anywhere
                print(f"🔍 DEBUG: No options found, returning no match result")
                return {
                    "input_hs_code": model_hs_code,
                    "resolved_source": "none",
                    "resolved_tariff_code": None,
                    "resolved_hs_code": None,
                    "description": None,
                    "match_score": 0.0,
                    "confidence_level": "none",
                    "reasoning": "No valid HS code could be determined.",
                    "notes": "No matches found in tariff_codes or hs_codes_2022 databases.",
                    "warnings": [],
                    "errors": ["No database matches found"]
                }

            # Use LLM to select the best option
            if self.verbose:
                print(f"\n📋 Evaluating {len(all_options)} total option(s) found across databases...")
            
            print(f"🔍 DEBUG: About to call LLM selection with {len(all_options)} options...")
            
            best_match = self._select_best_code_with_llm(
                model_hs_code, product_name, product_info_text, all_options
            )
            
            # DEBUG: Print LLM selection result
            print(f"🔍 DEBUG: LLM selection result for {model_hs_code}:")
            print(f"   best_match: {best_match}")
            if best_match:
                print(f"   best_match keys: {list(best_match.keys())}")
            
            if best_match:
                # Determine if this came from tariff_codes
                tariff_code = None
                if best_match['source'] == 'tariff_codes':
                    tariff_code = best_match['code']
                
                # Generate warnings
                warnings = self._generate_warnings(best_match, product_name, model_hs_code)
                
                confidence_level = self._get_confidence_level(best_match.get('confidence', 0.95))
                
                result = {
                    "input_hs_code": model_hs_code,
                    "resolved_source": f"{best_match['source']}_verified",
                    "resolved_tariff_code": tariff_code,
                    "resolved_hs_code": best_match['formatted_code'],
                    "description": best_match['description'],
                    "match_score": best_match.get('confidence', 0.95),
                    "confidence_level": confidence_level,
                    "reasoning": best_match.get('reasoning', ''),
                    "notes": f"Selected from {len(all_options)} options found across databases.",
                    "warnings": warnings,
                    "errors": []
                }
                
                # DEBUG: Print final result being returned
                print(f"🔍 DEBUG: Final result being returned:")
                print(f"   resolved_hs_code: {result.get('resolved_hs_code')}")
                
                return result
            else:
                result = {
                    "input_hs_code": model_hs_code,
                    "resolved_source": "none",
                    "resolved_tariff_code": None,
                    "resolved_hs_code": None,
                    "description": None,
                    "match_score": 0.0,
                    "confidence_level": "none",
                    "reasoning": "Options found but none were appropriate for the product.",
                    "notes": f"LLM rejected all {len(all_options)} options found.",
                    "warnings": [],
                    "errors": ["LLM failed to select appropriate code"]
                }
                
                # DEBUG: Print final result being returned (no selection)
                print(f"🔍 DEBUG: Final result being returned (no selection):")
                print(f"   resolved_hs_code: {result.get('resolved_hs_code')}")
                
                return result
                
        except Exception as e:
            print(f"🔍 DEBUG: EXCEPTION in reconcile_hs_code for {model_hs_code}: {str(e)}")
            import traceback
            print(f"🔍 DEBUG: Full traceback:\n{traceback.format_exc()}")
            
            # Return error result
            return {
                "input_hs_code": model_hs_code,
                "resolved_source": "error",
                "resolved_tariff_code": None,
                "resolved_hs_code": None,
                "description": None,
                "match_score": 0.0,
                "confidence_level": "none",
                "reasoning": f"Error during reconciliation: {str(e)}",
                "notes": "Exception occurred during processing.",
                "warnings": [],
                "errors": [f"Exception: {str(e)}"]
            }

    def _comprehensive_tariff_search(self, model_hs_code: str, heading_prefix: str):
        """
        Comprehensive search in tariff_codes:
        1. First try exact 6-digit match
        2. If not found, automatically search by 4-digit heading
        """
        results = {
            'exact_matches': None,
            'heading_matches': None
        }
        
        try:
            # Try exact match first (6-digit)
            exact_response = self.supabase.table('tariff_codes') \
                .select('tariff_code, description') \
                .like('tariff_code', f'{model_hs_code}%') \
                .execute()
            
            if exact_response.data and len(exact_response.data) > 0:
                results['exact_matches'] = exact_response.data
                if self.verbose:
                    print(f"✅ Tariff Codes: Found {len(exact_response.data)} exact match(es) for {model_hs_code}")
            else:
                # No exact match, try heading (4-digit)
                if self.verbose:
                    print(f"❌ Tariff Codes: No exact match for {model_hs_code}, searching heading {heading_prefix}...")
                
                heading_response = self.supabase.table('tariff_codes') \
                    .select('tariff_code, description') \
                    .like('tariff_code', f'{heading_prefix}%') \
                    .execute()
                
                if heading_response.data and len(heading_response.data) > 0:
                    results['heading_matches'] = heading_response.data
                    if self.verbose:
                        print(f"✅ Tariff Codes: Found {len(heading_response.data)} match(es) under heading {heading_prefix}")
                else:
                    if self.verbose:
                        print(f"❌ Tariff Codes: No matches found even under heading {heading_prefix}")
                    
        except Exception as e:
            print(f"Error querying tariff_codes: {str(e)}")
            
        return results

    def _comprehensive_hs_search(self, formatted_hs_code: str, heading_prefix: str):
        """
        Comprehensive search in hs_codes_2022:
        1. First try exact 6-digit match
        2. If not found, automatically search by 4-digit heading
        """
        results = {
            'exact_match': None,
            'heading_matches': None
        }
        
        try:
            # Try exact match first
            exact_response = self.supabase.table('hs_codes_2022') \
                .select('hs_code, description') \
                .eq('hs_code', formatted_hs_code) \
                .execute()
            
            if exact_response.data and len(exact_response.data) > 0:
                results['exact_match'] = exact_response.data[0]
                if self.verbose:
                    print(f"✅ HS Codes 2022: Found exact match for {formatted_hs_code}")
            else:
                # No exact match, try heading
                heading_query = f"{heading_prefix[:2]}.{heading_prefix[2:]}"
                if self.verbose:
                    print(f"❌ HS Codes 2022: No exact match for {formatted_hs_code}, searching heading {heading_query}...")
                
                heading_response = self.supabase.table('hs_codes_2022') \
                    .select('hs_code, description') \
                    .like('heading', f'{heading_query}%') \
                    .execute()
                
                if heading_response.data and len(heading_response.data) > 0:
                    results['heading_matches'] = heading_response.data
                    if self.verbose:
                        print(f"✅ HS Codes 2022: Found {len(heading_response.data)} match(es) under heading {heading_query}")
                else:
                    if self.verbose:
                        print(f"❌ HS Codes 2022: No matches found even under heading {heading_query}")
                    
        except Exception as e:
            print(f"Error querying hs_codes_2022: {str(e)}")
            
        return results

    def _display_compact_findings(self, model_hs_code, tariff_results, hs_results):
        """Display compact findings for non-verbose mode"""
        tariff_status = "❌"
        hs_status = "❌"
        
        if tariff_results['exact_matches']:
            tariff_status = f"✅ {len(tariff_results['exact_matches'])} exact"
        elif tariff_results['heading_matches']:
            tariff_status = f"✅ {len(tariff_results['heading_matches'])} heading"
            
        if hs_results['exact_match']:
            hs_status = "✅ 1 exact"
        elif hs_results['heading_matches']:
            hs_status = f"✅ {len(hs_results['heading_matches'])} heading"
            
        print(f"├── {model_hs_code}: Tariff {tariff_status}, HS {hs_status}")

    def _display_all_findings(self, tariff_results, hs_results):
        """Display all database query results in a clear format"""
        
        # Tariff Codes Results
        print(f"\n📁 TARIFF CODES DATABASE RESULTS:")
        print("-" * 50)
        
        if tariff_results['exact_matches']:
            print(f"✅ Exact matches for 6-digit code:")
            for match in tariff_results['exact_matches'][:10]:  # Show first 10
                print(f"   • {match['tariff_code']} → {match['description']}")
            if len(tariff_results['exact_matches']) > 10:
                print(f"   ... and {len(tariff_results['exact_matches']) - 10} more options")
        elif tariff_results['heading_matches']:
            print(f"✅ Heading matches (4-digit fallback):")
            for match in tariff_results['heading_matches'][:10]:  # Show first 10
                print(f"   • {match['tariff_code']} → {match['description']}")
            if len(tariff_results['heading_matches']) > 10:
                print(f"   ... and {len(tariff_results['heading_matches']) - 10} more options")
        else:
            print("❌ No matches found")

        # HS Codes 2022 Results
        print(f"\n📁 HS CODES 2022 DATABASE RESULTS:")
        print("-" * 50)
        
        if hs_results['exact_match']:
            print(f"✅ Exact match found:")
            print(f"   • {hs_results['exact_match']['hs_code']} → {hs_results['exact_match']['description']}")
        elif hs_results['heading_matches']:
            print(f"✅ Heading matches (4-digit fallback):")
            for match in hs_results['heading_matches'][:10]:  # Show first 10
                print(f"   • {match['hs_code']} → {match['description']}")
            if len(hs_results['heading_matches']) > 10:
                print(f"   ... and {len(hs_results['heading_matches']) - 10} more options")
        else:
            print("❌ No matches found")

    def _select_best_code_with_llm(self, model_hs_code, product_name, product_info_text, all_options):
        """Use LLM to select the best code from all available options - FIXED VERSION"""
        
        # Build options text
        option_lines = []
        for idx, opt in enumerate(all_options):
            source_tag = f"[{opt['source']} - {opt['match_type']}]"
            option_lines.append(f"{idx+1}. {opt['formatted_code']} {source_tag}")
            option_lines.append(f"   Description: {opt['description']}")
            option_lines.append("")

        options_text = "\n".join(option_lines)

        prompt = f"""You are an expert in HS Code classification.

Product: {product_name}
Product Information: {product_info_text}

The following HS codes were found in our databases. Please select the most appropriate code for this product.

{options_text}

Please provide your analysis in this EXACT format:
Selected Code: [number]
Reasoning: [explain why this code is most appropriate]
Confidence: [high/medium/low]

IMPORTANT: For "Selected Code", provide ONLY the option number (1, 2, 3, etc.), not the actual HS code.

Consider:
- The product's primary function and use
- Its material composition and construction
- Any special features or characteristics
- The most specific classification that accurately covers the product"""

        try:
            response = self.reason_with_llm(prompt)
            
            if self.verbose:
                print(f"\n🤖 LLM Response for {model_hs_code}:")
                print(f"Raw response: {response}")
            
            # FIXED PARSING LOGIC - Handle both option numbers and direct codes
            selected_code = None
            reasoning = ""
            confidence = "medium"
            
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('Selected Code:'):
                    code_part = line.split(':', 1)[1].strip()
                    
                    # METHOD 1: Try to parse as option number (original logic)
                    match = re.search(r'\b(\d+)\b', code_part)
                    if match:
                        selected_num = int(match.group(1))
                        if 1 <= selected_num <= len(all_options):
                            selected_code = all_options[selected_num - 1]
                            if self.verbose:
                                print(f"✅ Parsed option number: {selected_num}")
                    
                    # METHOD 2: If option number failed, try direct code matching
                    if not selected_code:
                        # Extract digits/dots from the response
                        raw_code = re.sub(r'[^\d.]', '', code_part)
                        
                        # Try to match against available options
                        for opt in all_options:
                            # Check multiple formats: 8517130000, 851713, 8517.13
                            opt_variations = [
                                opt['code'],  # Full 10-digit or original code
                                opt['formatted_code'],  # 8517.13 format
                                opt['formatted_code'].replace('.', ''),  # 851713 format
                                opt['code'][:6] if len(opt['code']) >= 6 else opt['code']  # First 6 digits
                            ]
                            
                            if raw_code in opt_variations:
                                selected_code = opt
                                if self.verbose:
                                    print(f"✅ Matched direct code: {raw_code} → {opt['formatted_code']}")
                                break
                    
                    # METHOD 3: Last resort - fuzzy matching on description
                    if not selected_code and len(code_part) > 3:
                        # If LLM mentioned part of a description, try to match
                        for opt in all_options:
                            if any(word.lower() in opt['description'].lower() 
                                  for word in code_part.split() 
                                  if len(word) > 3):
                                selected_code = opt
                                if self.verbose:
                                    print(f"✅ Fuzzy matched description: {code_part}")
                                break
                    
                    if not selected_code:
                        if self.verbose:
                            print(f"❌ Could not parse Selected Code: '{code_part}'")
                            print(f"   Available options count: {len(all_options)}")
                            
                elif line.startswith('Reasoning:'):
                    reasoning = line.split(':', 1)[1].strip()
                elif line.startswith('Confidence:'):
                    conf = line.split(':', 1)[1].strip().lower()
                    if conf in ['high', 'medium', 'low']:
                        confidence = conf

            # ENHANCED FALLBACK: If structured parsing completely failed
            if not selected_code:
                if self.verbose:
                    print("⚠️  Structured parsing failed, trying fallback extraction...")
                
                # Look for any valid codes mentioned in the entire response
                for opt in all_options:
                    opt_patterns = [
                        opt['code'],
                        opt['formatted_code'],
                        opt['formatted_code'].replace('.', '')
                    ]
                    
                    for pattern in opt_patterns:
                        if pattern in response:
                            selected_code = opt
                            reasoning = "Extracted from unstructured LLM response"
                            if self.verbose:
                                print(f"✅ Fallback extraction found: {pattern}")
                            break
                            
                    if selected_code:
                        break
            
            if selected_code:
                # Convert confidence to a score
                confidence_scores = {'high': 0.95, 'medium': 0.7, 'low': 0.4}
                selected_code['confidence'] = confidence_scores.get(confidence, 0.7)
                selected_code['reasoning'] = reasoning if reasoning else "No reasoning provided"
                
                if self.verbose:
                    print(f"🎯 Final selection: {selected_code['formatted_code']}")
                    print(f"   Confidence: {confidence} ({selected_code['confidence']})")
                    print(f"   Reasoning: {reasoning}")
                
                return selected_code
            else:
                if self.verbose:
                    print("❌ All parsing methods failed")
                    print(f"Full LLM Response:\n{response}")
                return None
                
        except Exception as e:
            print(f"Error in LLM selection: {str(e)}")
            return None

    def _generate_warnings(self, selected_match, product_name, input_code):
        """Generate warnings based on the selected match and product characteristics"""
        warnings = []
        
        # Category mismatch warnings
        if "passenger" in product_name.lower() or "suv" in product_name.lower() or "car" in product_name.lower():
            if selected_match['formatted_code'].startswith('8704'):
                warnings.append("Category mismatch: Selected goods transport code for passenger vehicle")
            elif "pick-up" in selected_match['description'].lower() or "truck" in selected_match['description'].lower():
                warnings.append("Description mismatch: Selected commercial vehicle description for passenger vehicle")
        
        # Confidence warnings
        if selected_match.get('confidence', 1.0) < 0.5:
            warnings.append("Low confidence selection - manual review recommended")
            
        # Source warnings
        if selected_match['match_type'] == 'heading':
            warnings.append("Selected from heading matches - not exact code match")
            
        return warnings

    def _get_confidence_level(self, score):
        """Convert numerical confidence to text level"""
        if score >= 0.9:
            return "high"
        elif score >= 0.7:
            return "medium"
        elif score >= 0.4:
            return "low"
        else:
            return "very_low"

    def determine_final_hs_code(self, reconciliation_results, product_name):
        """Determine the final HS code based on reconciliation results with enhanced analysis"""
        
        # DEBUG: Print what we received
        if self.verbose:
            print(f"\n🔍 DEBUG: determine_final_hs_code called with {len(reconciliation_results) if reconciliation_results else 0} results")
            for i, result in enumerate(reconciliation_results or []):
                print(f"   Result {i+1}: input_hs_code={result.get('input_hs_code')}, resolved_hs_code={result.get('resolved_hs_code')}")
        
        if not reconciliation_results:
            if self.verbose:
                print("🔍 DEBUG: No reconciliation_results - returning NO_MATCH")
            return {
                'confirmed_hs_code': 'NO_MATCH',
                'summary_text': f"No valid HS code could be determined for {product_name}.",
                'description': None,
                'consensus': 'none',
                'consensus_count': 0,
                'total_inputs': 0,
                'quality_score': 0.0,
                'requires_manual_review': True,
                'overall_warnings': ["No valid codes found"],
                'overall_errors': ["All reconciliation attempts failed"]
            }
        
        # Count occurrences of each resolved code
        code_counts = {}
        valid_results = []
        
        for result in reconciliation_results:
            resolved_code = result.get('resolved_hs_code')
            if resolved_code and resolved_code != 'NO_MATCH':  # Added NO_MATCH check
                code_counts[resolved_code] = code_counts.get(resolved_code, 0) + 1
                valid_results.append(result)
        
        # DEBUG: Print code_counts
        if self.verbose:
            print(f"🔍 DEBUG: code_counts = {code_counts}")
            print(f"🔍 DEBUG: valid_results count = {len(valid_results)}")
        
        if not code_counts:
            if self.verbose:
                print("🔍 DEBUG: code_counts is empty - returning NO_MATCH")
            return {
                'confirmed_hs_code': 'NO_MATCH',
                'summary_text': f"No valid HS code could be determined for {product_name}.",
                'description': None,
                'consensus': 'none',
                'consensus_count': 0,
                'total_inputs': len(reconciliation_results),
                'quality_score': 0.0,
                'requires_manual_review': True,
                'overall_warnings': ["No valid codes resolved"],
                'overall_errors': [f"All {len(reconciliation_results)} inputs failed to resolve"]
            }
        
        # DEBUG: Print what we're about to compare
        if self.verbose:
            print(f"🔍 DEBUG: About to compare {len(valid_results)} valid results:")
            for i, result in enumerate(valid_results):
                print(f"   Result {i+1}: {result.get('resolved_hs_code')} - {result.get('description', 'No description')}")
        
        # Use LLM to compare all valid results and select the best match
        try:
            confirmed_code, count, reasoning = self._llm_compare_results(valid_results, product_name)
        except Exception as e:
            print(f"🔍 DEBUG: Error in _llm_compare_results: {str(e)}")
            # Fall back to old logic
            most_common = max(code_counts.items(), key=lambda x: x[1])
            confirmed_code = most_common[0]
            count = most_common[1]
            reasoning = "Fallback selection due to LLM error"
        
        total = len(reconciliation_results)
        

        
        # DEBUG: Print final selection
        if self.verbose:
            print(f"🔍 DEBUG: Final confirmed_code = {confirmed_code} (LLM selected from {len(valid_results)} options)")
        
        # Determine consensus type
        if count == total:
            consensus = 'unanimous'
            summary = f"All {total} inputs resolved to HS code {confirmed_code} for {product_name}."
        elif count > total / 2:
            consensus = 'majority'
            summary = f"{count} out of {total} inputs resolved to HS code {confirmed_code} for {product_name}."
        else:
            consensus = 'weak'
            summary = f"Only {count} out of {total} inputs resolved to HS code {confirmed_code} for {product_name} (weak consensus)."
        
        # Get description and calculate quality metrics
        description = None
        total_confidence = 0
        all_warnings = []
        all_errors = []
        
        for result in reconciliation_results:
            if result.get('resolved_hs_code') == confirmed_code:
                description = result.get('description')
                total_confidence += result.get('match_score', 0)
            
            # Collect warnings and errors
            all_warnings.extend(result.get('warnings', []))
            all_errors.extend(result.get('errors', []))
        
        # Calculate quality score (0-10)
        consensus_score = count / total  # 0-1
        avg_confidence = total_confidence / max(count, 1)  # 0-1
        warning_penalty = min(len(set(all_warnings)) * 0.1, 0.5)  # Up to 0.5 penalty
        error_penalty = min(len(set(all_errors)) * 0.2, 0.8)  # Up to 0.8 penalty
        
        quality_score = max(0, (consensus_score * 0.4 + avg_confidence * 0.6 - warning_penalty - error_penalty) * 10)
        
        # Determine if manual review is required
        requires_manual_review = (
            quality_score < 6.0 or 
            consensus == 'weak' or 
            len(all_errors) > 0 or
            any("mismatch" in warning.lower() for warning in all_warnings)
        )
        
        return {
            'confirmed_hs_code': confirmed_code,
            'summary_text': summary,
            'description': description,
            'reasoning': reasoning,
            'consensus': consensus,
            'consensus_count': count,
            'total_inputs': total,
            'quality_score': round(quality_score, 1),
            'requires_manual_review': requires_manual_review,
            'overall_warnings': list(set(all_warnings)),
            'overall_errors': list(set(all_errors))
        }
    
    def _llm_compare_results(self, valid_results, product_name):
        """Use LLM to compare all valid results and select the best match for the product"""
        
        print(f"\n🔍 DEBUG: _llm_compare_results called with {len(valid_results)} results")
        
        if len(valid_results) == 1:
            # Only one result, but still show the reasoning
            result = valid_results[0]
            selected_code = result.get('resolved_hs_code')
            reasoning = result.get('reasoning', 'No reasoning provided')
            
            print(f"\n🤖 STAGE 2 FINAL SELECTION:")
            print(f"   Selected: {selected_code}")
            print(f"   Reasoning: {reasoning}")
            
            return selected_code, 1, reasoning
        
        # Build comparison prompt
        options_text = ""
        for i, result in enumerate(valid_results, 1):
            code = result.get('resolved_hs_code')
            description = result.get('description', 'No description available')
            confidence = result.get('match_score', 0)
            reasoning = result.get('reasoning', 'No reasoning provided')
            options_text += f"{i}. {code}: {description} (confidence: {confidence:.2f})\n"
            options_text += f"   Reasoning: {reasoning}\n\n"
        
        prompt = f"""You are an expert in tariff classification. Compare these HS code options for the product "{product_name}" and select the most appropriate one.

PRODUCT: {product_name}

HS CODE OPTIONS:
{options_text}

IMPORTANT: You must select the MOST SPECIFIC code that accurately describes the product. Consider:
- Which code is most specific to the product type (prefer specific over generic)
- Which code best matches the product's characteristics and context
- Which code is most accurate for classification purposes
- ALWAYS prefer more specific codes over generic ones when both are valid
- Look at the detailed reasoning provided for each option

For a 2022 Tesla Model Y (electric vehicle, individual importer, less than 3 years old), you should prefer:
- 8703.80 (electric vehicles) over 8703.00 (generic motor vehicles)
- 8703.80 with specific conditions over 8703.80 without conditions

Respond in this EXACT JSON format:
{{
    "selected_code": "8703.80",
    "reasoning": "Explanation of why this code is the best choice"
}}"""

        if not COMMODITY_LLM_AVAILABLE:
            print("⚠️  LLM comparison unavailable - using first result")
            return valid_results[0].get('resolved_hs_code'), 1, "LLM import failed"
        
        try:
            print(f"🔍 DEBUG: Calling LLM with prompt...")
            response = reason_with_llm_fn(prompt)
            print(f"🔍 DEBUG: LLM response received: {response[:100]}...")
            
            # Parse JSON response
            try:
                result = json.loads(response)
                selected_code = result.get('selected_code')
                reasoning = result.get('reasoning', 'No reasoning provided')
                
                # Print the LLM's reasoning
                print(f"\n🤖 LLM COMPARISON RESULT:")
                print(f"   Selected: {selected_code}")
                print(f"   Reasoning: {reasoning}")
                print(f"   Full LLM Response: {response}")
                
                # Find the matching result
                for result in valid_results:
                    if result.get('resolved_hs_code') == selected_code:
                        return selected_code, 1, reasoning
                
                # If LLM response doesn't match any option, fall back to first result
                if self.verbose:
                    print(f"🔍 DEBUG: LLM selected {selected_code} but it doesn't match any option, using first result")
                return valid_results[0].get('resolved_hs_code'), 1, "Fallback to first result"
                
            except json.JSONDecodeError as e:
                if self.verbose:
                    print(f"🔍 DEBUG: Failed to parse LLM JSON response: {str(e)}")
                # Fall back to first result if JSON parsing fails
                return valid_results[0].get('resolved_hs_code'), 1, "Fallback due to JSON parsing error"
            
        except Exception as e:
            print(f"🔍 DEBUG: LLM comparison failed: {str(e)}, using first result")
            print(f"🔍 DEBUG: Exception type: {type(e).__name__}")
            return valid_results[0].get('resolved_hs_code'), 1, f"Fallback due to error: {str(e)}"

    def display_executive_summary(self, final_determination, product_name):
        """Display executive summary for quick decision making"""
        # Only display if running as standalone script
        if __name__ == "__main__":
            print(f"\n🎯 EXECUTIVE SUMMARY")
            print("=" * 50)
            print(f"Product: {product_name}")
            
            if final_determination['confirmed_hs_code'] == 'NO_MATCH':
                print(f"Recommended HS Code: ❌ NO VALID CODE FOUND")
                print(f"Quality Score: {final_determination['quality_score']}/10")
                print(f"Manual Review: ✅ REQUIRED")
            else:
                print(f"Recommended HS Code: {final_determination['confirmed_hs_code']}")
                
                # Display confidence with emoji
                quality = final_determination['quality_score']
                if quality >= 8:
                    quality_emoji = "🟢"
                    quality_text = "Excellent"
                elif quality >= 6:
                    quality_emoji = "🟡"
                    quality_text = "Good"
                elif quality >= 4:
                    quality_emoji = "🟠"
                    quality_text = "Fair"
                else:
                    quality_emoji = "🔴"
                    quality_text = "Poor"
                    
                print(f"Quality Score: {quality_emoji} {quality}/{10} ({quality_text})")
                print(f"Consensus: {final_determination['consensus'].title()} ({final_determination['consensus_count']}/{final_determination['total_inputs']})")
                
                if final_determination['requires_manual_review']:
                    print(f"Manual Review: ⚠️  RECOMMENDED")
                else:
                    print(f"Manual Review: ✅ NOT REQUIRED")
                    
                if final_determination.get('description'):
                    print(f"Description: {final_determination['description']}")
            
            # Display warnings and errors
            if final_determination.get('overall_warnings'):
                print(f"\n⚠️  Warnings:")
                for warning in final_determination['overall_warnings']:
                    print(f"   • {warning}")
                    
            if final_determination.get('overall_errors'):
                print(f"\n❌ Errors:")
                for error in final_determination['overall_errors']:
                    print(f"   • {error}")

    def display_compact_process_log(self, reconciliation_results, product_name):
        """Display compact process logging"""
        print(f"\n📊 PROCESS SUMMARY")
        print("-" * 50)
        
        for result in reconciliation_results:
            input_code = result['input_hs_code']
            
            if result['resolved_hs_code']:
                confidence = result.get('confidence_level', 'unknown')
                confidence_emoji = {
                    'high': '✅',
                    'medium': '🟡', 
                    'low': '🟠',
                    'very_low': '🔴',
                    'none': '❌'
                }.get(confidence, '❓')
                
                status = f"→ {result['resolved_hs_code']} {confidence_emoji}"
                
                # Add warning indicators
                if result.get('warnings'):
                    status += " ⚠️"
                if result.get('errors'):
                    status += " ❌"
                    
            else:
                status = "→ ❌ No selection"
                
            print(f"├── {input_code}: {status}")

    def _format_hs_code(self, hs_code_str: str) -> str:
        """Format HS code for lookup → 851712 → '8517.12'"""
        if not hs_code_str.isdigit() or len(hs_code_str) != 6:
            raise ValueError("HS code must be 6 digits")
        return f"{hs_code_str[:4]}.{hs_code_str[4:]}"

if __name__ == "__main__":
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="HS Code Reconciler")
    parser.add_argument("product", help="Product name")
    parser.add_argument("hs_codes", help="Comma-separated list of HS codes to reconcile")
    parser.add_argument("--info", help="Product information text", default="")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--summary", "-s", action="store_true", help="Show only executive summary")
    args = parser.parse_args()

    # Initialize reconciler with verbosity setting
    verbose_mode = args.verbose or not args.summary
    reconciler = HSCodeReconciler(create_client(SUPABASE_URL, SUPABASE_KEY), reason_with_llm_fn, verbose=verbose_mode)

    # Process each HS code
    hs_codes = [code.strip() for code in args.hs_codes.split(',')]
    results = []

    if not args.summary:
        print(f"\n🔍 PROCESSING {len(hs_codes)} HS CODES FOR: {args.product}")
        if not verbose_mode:
            print("📊 DATABASE QUERIES")

    for hs_code in hs_codes:
        if verbose_mode:
            print(f"\n{'='*60}")
            print(f"Processing HS Code: {hs_code}")
            print(f"{'='*60}")
        
        result = reconciler.reconcile_hs_code(hs_code, args.product, args.info)
        results.append(result)
        
        if verbose_mode:
            print(f"\n=== Result for {hs_code} ===")
            print(json.dumps(result, indent=2))

    # Determine final consensus
    final_hs_determination = reconciler.determine_final_hs_code(results, args.product)

    # Display results based on mode
    if args.summary:
        # Summary mode - just executive summary
        reconciler.display_executive_summary(final_hs_determination, args.product)
    else:
        # Regular mode - show process summary and executive summary
        reconciler.display_compact_process_log(results, args.product)
        reconciler.display_executive_summary(final_hs_determination, args.product)
        
        if verbose_mode:
            print(f"\n{'='*60}")
            print("=== DETAILED CONSENSUS ANALYSIS ===")
            print(f"{'='*60}")
            print(json.dumps(final_hs_determination, indent=2))

    # Enhanced final output
    final_output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "product": args.product,
            "input_hs_codes": hs_codes,
            "processing_mode": "summary" if args.summary else "detailed"
        },
        "executive_summary": {
            "recommended_hs_code": final_hs_determination['confirmed_hs_code'],
            "quality_score": final_hs_determination['quality_score'],
            "consensus_strength": final_hs_determination['consensus'],
            "manual_review_required": final_hs_determination['requires_manual_review'],
            "key_warnings": final_hs_determination.get('overall_warnings', [])[:3],  # Top 3 warnings
            "critical_errors": final_hs_determination.get('overall_errors', [])
        },
        "detailed_results": {
            "reconciliation_results": results,
            "final_determination": final_hs_determination
        }
    }

    if verbose_mode:
        print(f"\n{'='*60}")
        print("=== ENHANCED JSON OUTPUT ===")
        print(f"{'='*60}")
        print(json.dumps(final_output, indent=2))