# orders/models.py
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modules'))

# Import config for Supabase credentials
from config import SUPABASE_URL, SUPABASE_ANON_KEY
from supabase import create_client

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def create_order(client_id: int, description: str = None) -> Optional[Dict[str, Any]]:
    """
    Create a new order with auto-generated order number
    
    Args:
        client_id (int): ID of the client
        description (str): Optional order description
        
    Returns:
        dict: Created order record with ID and order number
    """
    try:
        from order_generator import generate_order_number
        
        # Generate unique order number
        order_number = generate_order_number()
        
        # Create order data
        order_data = {
            "order_number": order_number,
            "client_id": client_id,
            "description": description,
            "status": "pending"
        }
        
        # Insert into database
        result = supabase.table("orders").insert(order_data).execute()
        
        if result.data:
            print(f"✅ Created order: {order_number}")
            return result.data[0]
        else:
            print("❌ Failed to create order")
            return None
            
    except Exception as e:
        print(f"❌ Error creating order: {e}")
        return None

def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    """
    Get order by ID
    
    Args:
        order_id (int): Order ID
        
    Returns:
        dict: Order data or None if not found
    """
    try:
        result = supabase.table("orders").select("*").eq("id", order_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error getting order by ID: {e}")
        return None

def get_order_by_number(order_number: str) -> Optional[Dict[str, Any]]:
    """
    Get order by order number
    
    Args:
        order_number (str): Order number
        
    Returns:
        dict: Order data or None if not found
    """
    try:
        result = supabase.table("orders").select("*").eq("order_number", order_number).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error getting order by number: {e}")
        return None

def get_orders_by_client(client_id: int) -> List[Dict[str, Any]]:
    """
    Get all orders for a client
    
    Args:
        client_id (int): Client ID
        
    Returns:
        list: List of orders for the client
    """
    try:
        result = supabase.table("orders").select("*").eq("client_id", client_id).order("created_at", desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting orders by client: {e}")
        return []

def update_order_status(order_id: int, status: str) -> Optional[Dict[str, Any]]:
    """
    Update order status
    
    Args:
        order_id (int): Order ID
        status (str): New status
        
    Returns:
        dict: Updated order or None if error
    """
    try:
        valid_statuses = ['pending', 'documents_uploaded', 'processing', 'completed', 'failed']
        if status not in valid_statuses:
            print(f"❌ Invalid status: {status}")
            return None
        
        result = supabase.table("orders").update({"status": status, "updated_at": datetime.now().isoformat()}).eq("id", order_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error updating order status: {e}")
        return None

def get_order_documents(order_id: int) -> List[Dict[str, Any]]:
    """
    Get all documents for an order
    
    Args:
        order_id (int): Order ID
        
    Returns:
        list: List of documents for the order
    """
    try:
        result = supabase.table("documents").select("*").eq("order_id", order_id).order("upload_date", desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting order documents: {e}")
        return []

def get_orders_with_documents() -> List[Dict[str, Any]]:
    """
    Get all orders with their document counts
    
    Returns:
        list: List of orders with document information
    """
    try:
        # Get orders with document counts
        result = supabase.table("orders").select("*, documents(*)").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting orders with documents: {e}")
        return []

def validate_order_completeness(order_id: int) -> Dict[str, Any]:
    """
    Validate if an order has all required documents
    
    Args:
        order_id (int): Order ID
        
    Returns:
        dict: Validation result with completeness status
    """
    try:
        # Get order documents
        documents = get_order_documents(order_id)
        
        # Required document types
        required_types = ['invoice', 'bill_of_lading']
        
        # Check which documents are uploaded
        uploaded_types = [doc['document_type'] for doc in documents]
        
        # Check completeness
        missing_types = [doc_type for doc_type in required_types if doc_type not in uploaded_types]
        has_arrival_notice = 'arrival_notice' in uploaded_types
        
        is_complete = len(missing_types) == 0
        
        return {
            "order_id": order_id,
            "is_complete": is_complete,
            "missing_documents": missing_types,
            "has_arrival_notice": has_arrival_notice,
            "uploaded_documents": uploaded_types,
            "total_documents": len(documents)
        }
        
    except Exception as e:
        print(f"❌ Error validating order completeness: {e}")
        return {
            "order_id": order_id,
            "is_complete": False,
            "error": str(e)
        }

def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent orders
    
    Args:
        limit (int): Number of orders to return
        
    Returns:
        list: List of recent orders
    """
    try:
        result = supabase.table("orders").select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting recent orders: {e}")
        return []

def count_orders_by_status() -> Dict[str, int]:
    """
    Count orders by status
    
    Returns:
        dict: Count of orders by status
    """
    try:
        result = supabase.table("orders").select("status").execute()
        
        if not result.data:
            return {}
        
        status_counts = {}
        for order in result.data:
            status = order.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return status_counts
        
    except Exception as e:
        print(f"❌ Error counting orders by status: {e}")
        return {} 