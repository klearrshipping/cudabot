import sys
import json
import difflib
from typing import Optional, Dict, List
from modules.core.csv_data_client import fetch_package_types
from modules.core.llm_client import LLMClient

# Cache for package types to avoid repeated database calls
_package_types_cache = None

def get_kind_of_packages_from_json(json_path: str) -> Optional[str]:
    """Extract kind_of_packages from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['result']['extracted_fields'].get('kind_of_packages', None)

def get_package_types() -> List[Dict]:
    """Get package types with caching to avoid repeated database calls."""
    global _package_types_cache
    if _package_types_cache is None:
        _package_types_cache = fetch_package_types()
    return _package_types_cache

def parse_llm_response(raw_response: str) -> Optional[str]:
    """Parse LLM response and extract package code."""
    if not raw_response:
        return None
    
    try:
        # Try to parse as JSON
        code_obj = json.loads(raw_response.strip())
        code = code_obj.get('code', '').strip()
        return code if code else None
    except (json.JSONDecodeError, AttributeError):
        # If JSON parsing fails, try to extract code pattern
        import re
        code_match = re.search(r'"code"\s*:\s*"([^"]+)"', raw_response)
        if code_match:
            return code_match.group(1).strip()
        return None

def string_similarity_fallback(kind_of_packages: str, package_types: List[Dict]) -> Optional[str]:
    """Fallback method using string similarity matching."""
    extracted = kind_of_packages.strip().lower()
    choices = [(pt['code'], pt['package_type']) for pt in package_types]
    
    # Try matching against codes first
    best = difflib.get_close_matches(extracted, [c[0].lower() for c in choices], n=1, cutoff=0.6)
    if best:
        return best[0].upper()
    
    # Try matching against package_type names
    best_name = difflib.get_close_matches(extracted, [c[1].lower() for c in choices], n=1, cutoff=0.6)
    if best_name:
        idx = [c[1].lower() for c in choices].index(best_name[0])
        return choices[idx][0]
    
    return None

def ask_llm_for_best_package_type(kind_of_packages: str, package_types: List[Dict]) -> Optional[str]:
    """Get the best package type using LLM with early termination."""
    # Optimized model selection: Use general models for secondary processing
    from config import OPENROUTER_GENERAL_MODELS
    priority_models = [
        OPENROUTER_GENERAL_MODELS["gpt_5_nano"],        # Primary - Best for text analysis
        OPENROUTER_GENERAL_MODELS["kimi_standard"]         # Backup - Reliable fallback
    ]
    
    llm = LLMClient()
    
    # Create package types list for prompt
    package_list = [f"{pt['code']}: {pt['package_type']}" for pt in package_types]
    
    prompt = f"""
You are a customs documentation expert. Given the extracted package type value from a customs document: '{kind_of_packages}', and the following list of valid package types from the database:

{package_list}

Return ONLY a valid JSON object with a single field 'code', e.g. {{"code": "BX"}}, where the value is the code of the most suitable package type from the list above that best matches the extracted value. If no good match, return the closest code. Do not return any explanation or extra text.
"""
    
    # Try priority models with early termination
    for model in priority_models:
        print(f"Testing model: {model.split('/')[-1].split(':')[0]}")
        try:
            raw_response = llm.send_prompt(prompt, model=model)
            code = parse_llm_response(raw_response)
            
            if code:
                print(f"✅ Model returned code: {code}")
                return code
            else:
                print(f"❌ Model did not return a valid code.")
                
        except Exception as e:
            print(f"❌ Exception for model: {e}")
    
    # If both models fail, try fallback
    print("🔄 Both models failed, using string similarity fallback.")
    return string_similarity_fallback(kind_of_packages, package_types)

class PackageProcessor:
    """Processor class for eSAD package types (Box 31 - Kind of packages)."""
    
    def __init__(self, config: Dict = None):
        """Initialize the PackageProcessor."""
        self.config = config or {}
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data to determine package type.
        
        Args:
            input_data: Dictionary containing invoice_data, bol_data, fields, and existing_fields
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Extract kind of packages from various sources
            kind_of_packages = self._extract_kind_of_packages(input_data)
            
            if not kind_of_packages:
                return {
                    'success': False,
                    'error': 'No kind of packages found',
                    'package_code': None
                }
            
            # Get package types from database
            package_types = get_package_types()
            if not package_types:
                return {
                    'success': False,
                    'error': 'No package types found in database',
                    'package_code': None
                }
            
            # Find best matching package type
            best_code = ask_llm_for_best_package_type(kind_of_packages, package_types)
            
            if best_code:
                return {
                    'success': True,
                    'package_code': best_code,
                    'kind_of_packages': kind_of_packages,
                    'package_types_available': len(package_types)
                }
            else:
                return {
                    'success': False,
                    'error': 'No suitable package type found',
                    'kind_of_packages': kind_of_packages,
                    'package_code': None
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'package_code': None
            }
    
    def _extract_kind_of_packages(self, input_data: Dict[str, Any]) -> str:
        """Extract kind of packages from input data."""
        # Try to get from existing fields first
        existing_fields = input_data.get('existing_fields', {})
        
        # Look for kind of packages in various field keys
        package_keys = [
            'kind_of_packages',
            '31_kind_of_packages',
            'package_type',
            'package_description',
            'packaging'
        ]
        
        for key in package_keys:
            if key in existing_fields and existing_fields[key]:
                return str(existing_fields[key])
        
        # Try to extract from invoice data
        invoice_data = input_data.get('invoice_data', {})
        if invoice_data:
            # Check items for packaging info
            items = invoice_data.get('items', [])
            if items and len(items) > 0:
                first_item = items[0]
                if isinstance(first_item, dict):
                    # Look for packaging-related fields
                    for field in ['packaging', 'package_type', 'container_type']:
                        if field in first_item and first_item[field]:
                            return str(first_item[field])
        
        # Try to extract from BOL data
        bol_data = input_data.get('bol_data', {})
        if bol_data:
            # Check cargo for packaging info
            cargo = bol_data.get('cargo', {})
            if isinstance(cargo, dict):
                for field in ['packaging', 'package_type', 'container_type']:
                    if field in cargo and cargo[field]:
                        return str(cargo[field])
        
        return ""

def main():
    """Main function with improved error handling."""
    if len(sys.argv) < 2:
        print("Usage: python -m modules.esad_pkg <esad_json_path>")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    try:
        kind_of_packages = get_kind_of_packages_from_json(json_path)
        if not kind_of_packages:
            print("No kind_of_packages value found in the JSON file.")
            sys.exit(1)
        
        package_types = get_package_types()
        if not package_types:
            print("No package types found in database.")
            sys.exit(1)
        
        best_code = ask_llm_for_best_package_type(kind_of_packages, package_types)
        
        if best_code:
            print(f"Best matching package_type code: {best_code}")
        else:
            print("No suitable package type found.")
            
    except FileNotFoundError:
        print(f"Error: File '{json_path}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file '{json_path}'.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
