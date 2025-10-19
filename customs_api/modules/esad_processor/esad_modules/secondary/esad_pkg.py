#!/usr/bin/env python3
"""
eSAD Package Processing Module
Handles package type classification and matching
"""

import json
import re
import os
import sys
from typing import Dict, List, Any, Optional
from difflib import SequenceMatcher

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
customs_api_dir = os.path.join(current_dir, '..', '..', '..', '..')
sys.path.insert(0, customs_api_dir)

from modules.core.llm_client import LLMClient
from modules.core.csv_data_client import fetch_package_types

# Module-level initialization
llm = LLMClient()

# Model configuration
try:
    from config import OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_GENERAL_MODELS

# Priority models for package processing
PRIORITY_MODELS = []
if "gpt_4o" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_4o"])
elif "gpt_5_nano" in OPENROUTER_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["gpt_5_nano"])

if "kimi_standard" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["kimi_standard"])
elif "kimi" in OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(OPENROUTER_GENERAL_MODELS["kimi"])

# Fallback to any available model
if not PRIORITY_MODELS and OPENROUTER_GENERAL_MODELS:
    PRIORITY_MODELS.append(list(OPENROUTER_GENERAL_MODELS.values())[0])


def string_similarity_fallback(kind_of_packages: str, package_types: List[Dict]) -> Optional[str]:
    """Fallback method using string similarity matching."""
    
    if not kind_of_packages:
        return None
    
    best_match = None
    best_score = 0.0
    
    for package_type in package_types:
        package_name = package_type.get('package_type', '').lower()
        input_name = kind_of_packages.lower()
        
        # Check exact match first
        if input_name == package_name:
            return package_type['code']
        
        # Check similarity
        similarity = SequenceMatcher(None, input_name, package_name).ratio()
        if similarity > best_score and similarity > 0.6:  # Minimum threshold
            best_score = similarity
            best_match = package_type['code']
    
    return best_match


def ask_llm_for_best_package_type(kind_of_packages: str, package_types: List[Dict]) -> Optional[str]:
    """Get the best package type using LLM with early termination."""
    
    if not kind_of_packages or kind_of_packages.lower() in ['not specified', 'none', '']:
        return None
    
    # Create package types list for prompt
    package_list = [f"{pt['code']}: {pt['package_type']}" for pt in package_types]
    
    prompt = f"""
You are a customs documentation expert. Given the extracted package type value from a customs document: '{kind_of_packages}', and the following list of valid package types from the database:

{package_list}

Return ONLY a valid JSON object with a single field 'code', e.g. {{"code": "BX"}}, where the value is the code of the most suitable package type from the list above that best matches the extracted value. If no good match, return the closest code. Do not return any explanation or extra text.
"""
    
    # Try priority models with early termination
    for model in PRIORITY_MODELS:
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            code = parse_llm_response(raw_response)
            
            if code:
                return code
                
        except Exception as e:
            continue
    
    # If both models fail, try fallback
    return string_similarity_fallback(kind_of_packages, package_types)


def parse_llm_response(response) -> Optional[str]:
    """Parse LLM response to extract package code."""
    try:
        # Handle different response types
        if isinstance(response, tuple):
            response = response[0] if response else ""
        elif not isinstance(response, str):
            response = str(response)
        
        response = response.strip()
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Find JSON object anywhere in the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
        
        # Parse JSON
        result = json.loads(response)
        code = result.get('code')
        
        # Validate code (should be 2-3 characters)
        if code and isinstance(code, str) and 2 <= len(code) <= 3:
            return code.upper()
        
        return None
        
    except Exception as e:
        print(f"❌ Failed to parse LLM response: {e}")
        return None


class PackageProcessor:
    """Processor class for eSAD package types (Box 31 - Kind of packages)."""
    
    def __init__(self):
        self.package_types = []
        self._load_package_types()
    
    def _load_package_types(self):
        """Load package types from database."""
        try:
            self.package_types = fetch_package_types()
        except Exception as e:
            print(f"❌ Failed to load package types: {e}")
            self.package_types = []
    
    def process_package_type(self, kind_of_packages: str, verbose: bool = False) -> Dict[str, Any]:
        """Process package type classification."""
        
        if not self.package_types:
            return {
                'success': False,
                'error': 'No package types available',
                'package_code': None
            }
        
        if verbose:
            print(f"📦 Processing package type: {kind_of_packages}")
        
        try:
            # Find best matching package type
            best_code = ask_llm_for_best_package_type(kind_of_packages, self.package_types)
            
            if best_code:
                # Find the package type details
                package_details = next((pt for pt in self.package_types if pt['code'] == best_code), None)
                
                if verbose:
                    print(f"✅ Package type matched: {best_code} - {package_details['package_type'] if package_details else 'Unknown'}")
                
                return {
                    'success': True,
                    'package_code': best_code,
                    'package_type': package_details['package_type'] if package_details else 'Unknown',
                    'processing_method': 'llm_extraction'
                }
            else:
                if verbose:
                    print("❌ No suitable package type found")
                
                return {
                    'success': False,
                    'error': 'No suitable package type found',
                    'package_code': None
                }
                
        except Exception as e:
            if verbose:
                print(f"❌ Error processing package type: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'package_code': None
            }


def main():
    """Test function for the package module."""
    # Test data
    test_package = "Wooden Box"
    
    print("🧪 Testing Package Module...")
    processor = PackageProcessor()
    result = processor.process_package_type(test_package, verbose=True)
    print(f"📋 Result: {json.dumps(result, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()