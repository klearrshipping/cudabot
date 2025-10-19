#!/usr/bin/env python3
"""
Debug script to test CIF module specifically
"""

import json
import sys
import os

# Add project paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
customs_api_dir = os.path.join(current_dir, 'customs_api')
sys.path.insert(0, customs_api_dir)
sys.path.insert(0, current_dir)

def debug_cif_import():
    """Debug the CIF module import and configuration."""
    print("🔍 Debugging CIF Module Import...")
    
    try:
        print("1. Testing config import...")
        from customs_api.config import OPENROUTER_GENERAL_MODELS
        print(f"✅ Config imported successfully")
        print(f"📋 Available models: {list(OPENROUTER_GENERAL_MODELS.keys())}")
        
        if "gpt_4o" in OPENROUTER_GENERAL_MODELS:
            print(f"✅ gpt_4o model found: {OPENROUTER_GENERAL_MODELS['gpt_4o']}")
        else:
            print("❌ gpt_4o model not found in config")
            
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        print("\n2. Testing LLMClient import...")
        from customs_api.modules.core.llm_client import LLMClient
        print("✅ LLMClient imported successfully")
        
        llm = LLMClient()
        print("✅ LLMClient instantiated successfully")
        
    except ImportError as e:
        print(f"❌ LLMClient import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ LLMClient instantiation failed: {e}")
        return False
    
    try:
        print("\n3. Testing CIF module import...")
        from customs_api.modules.esad_processor.esad_modules.core.esad_cif import ask_llm_for_cif_components
        print("✅ CIF module imported successfully")
        
    except ImportError as e:
        print(f"❌ CIF module import failed: {e}")
        return False
    
    return True

def test_cif_with_simple_data():
    """Test CIF module with simple test data."""
    print("\n🧪 Testing CIF Module with Simple Data...")
    
    # Simple test data
    invoice_data = {
        "items": [{"description": "Test battery pack", "total_price": 1000}],
        "totals": {"total_amount": 1200, "subtotal": 1000, "shipping_handling": 200},
        "currency": "USD",
        "invoice_details": {"terms_of_sale": "CIF"}
    }
    
    bol_data = {
        "freight_and_charges": "Freight: $200",
        "charges_table": [{"type": "Freight", "amount": 200}],
        "freight_charge_amount": "200"
    }
    
    try:
        from customs_api.modules.esad_processor.esad_modules.core.esad_cif import ask_llm_for_cif_components
        
        print("📊 Calling ask_llm_for_cif_components...")
        result = ask_llm_for_cif_components(invoice_data, bol_data)
        
        print("✅ CIF module executed successfully!")
        print("📋 Result:")
        
        # Handle circular references in JSON serialization
        def safe_json_dumps(obj):
            try:
                return json.dumps(obj, indent=2, ensure_ascii=False)
            except (ValueError, TypeError) as e:
                return f"JSON serialization failed: {e}\nObject type: {type(obj)}\nObject repr: {repr(obj)}"
        
        print(safe_json_dumps(result))
        
        return True
        
    except Exception as e:
        print(f"❌ CIF module execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔬 CIF Module Debug Script")
    print("=" * 50)
    
    # Step 1: Debug imports
    if debug_cif_import():
        print("\n✅ All imports successful!")
        
        # Step 2: Test with simple data
        test_cif_with_simple_data()
    else:
        print("\n❌ Import debugging failed. Check the errors above.")
