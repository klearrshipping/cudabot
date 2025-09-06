#!/usr/bin/env python3
"""
Test script to verify the new file structure is working correctly
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_imports():
    """Test that all imports work correctly"""
    print("🧪 Testing imports...")
    
    try:
        # Test model imports
        from models.clients import get_all_clients
        from models.documents import get_documents_by_order
        from models.orders import get_order_by_id
        print("✅ Model imports successful")
        
        # Test schema imports
        from schemas.clients import ClientCreate
        from schemas.orders import OrderCreate
        print("✅ Schema imports successful")
        
        # Test route imports
        from customs_api.routes.clients import router as clients_router
        from customs_api.routes.orders import router as orders_router
        print("✅ Route imports successful")
        
        # Test shared imports
        from shared.file_utils import save_document_file
        from shared.order_generator import generate_order_number
        print("✅ Shared imports successful")
        
        print("\n🎉 All imports successful! New structure is working correctly.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✅ File structure migration completed successfully!")
    else:
        print("\n❌ File structure migration has issues that need to be fixed.")
