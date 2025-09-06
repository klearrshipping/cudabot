# documents/models.py
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

def create_document_record(document_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create a new document record in the database
    
    Args:
        document_data (dict): Document information including:
            - order_id (int): Order ID
            - document_type (str): Type of document
            - file_path (str): Path to stored file
            - file_name (str): Original filename
            - file_size (int): File size in bytes
    
    Returns:
        dict: Created document record with ID and timestamps
    """
    try:
        result = supabase.table("documents").insert(document_data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error creating document record: {e}")
        return None

def get_document_by_id(document_id: int) -> Optional[Dict[str, Any]]:
    """
    Get document by ID
    
    Args:
        document_id (int): Document ID
        
    Returns:
        dict: Document data or None if not found
    """
    try:
        result = supabase.table("documents").select("*").eq("id", document_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error getting document by ID: {e}")
        return None

def get_documents_by_order(order_id: int) -> List[Dict[str, Any]]:
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
        print(f"❌ Error getting documents by order: {e}")
        return []

def get_documents_by_type(order_id: int, document_type: str) -> List[Dict[str, Any]]:
    """
    Get documents of a specific type for an order
    
    Args:
        order_id (int): Order ID
        document_type (str): Type of document
        
    Returns:
        list: List of documents of the specified type
    """
    try:
        result = supabase.table("documents").select("*").eq("order_id", order_id).eq("document_type", document_type).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting documents by type: {e}")
        return []

def update_document_status(document_id: int, status: str, error_message: str = None, processed_data_path: str = None) -> Optional[Dict[str, Any]]:
    """
    Update document processing status
    
    Args:
        document_id (int): Document ID
        status (str): New status
        error_message (str): Error message if status is failed
        processed_data_path (str): Path to processed data files
        
    Returns:
        dict: Updated document or None if error
    """
    try:
        valid_statuses = ['uploaded', 'processing', 'completed', 'failed']
        if status not in valid_statuses:
            print(f"❌ Invalid status: {status}")
            return None
        
        update_data = {
            "processing_status": status,
            "processed_at": datetime.now().isoformat() if status in ['completed', 'failed'] else None
        }
        
        if error_message:
            update_data["processing_error"] = error_message
        
        if processed_data_path:
            update_data["processed_data_path"] = processed_data_path
        
        # Increment retry count if status is failed
        if status == 'failed':
            update_data["retry_count"] = supabase.table("documents").select("retry_count").eq("id", document_id).execute().data[0].get("retry_count", 0) + 1
        
        result = supabase.table("documents").update(update_data).eq("id", document_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error updating document status: {e}")
        return None

def delete_document_record(document_id: int) -> bool:
    """
    Delete a document record
    
    Args:
        document_id (int): Document ID to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get document info before deletion
        document = get_document_by_id(document_id)
        if not document:
            print(f"❌ Document with ID {document_id} not found")
            return False
        
        # Delete from database
        result = supabase.table("documents").delete().eq("id", document_id).execute()
        
        if result.data:
            # Delete actual file
            from shared.file_utils import delete_document_file
            file_path = document.get('file_path', '')
            if file_path:
                delete_document_file(file_path)
            
            print(f"✅ Deleted document record: {document_id}")
            return True
        else:
            print(f"❌ Failed to delete document record: {document_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error deleting document record: {e}")
        return False

def get_document_stats(order_id: int) -> Dict[str, Any]:
    """
    Get document statistics for an order
    
    Args:
        order_id (int): Order ID
        
    Returns:
        dict: Document statistics
    """
    try:
        documents = get_documents_by_order(order_id)
        
        # Count by type
        type_counts = {}
        total_size = 0
        
        for doc in documents:
            doc_type = doc.get('document_type', 'unknown')
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            total_size += doc.get('file_size', 0)
        
        return {
            "order_id": order_id,
            "total_documents": len(documents),
            "documents_by_type": type_counts,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        print(f"❌ Error getting document stats: {e}")
        return {
            "order_id": order_id,
            "total_documents": 0,
            "documents_by_type": {},
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "error": str(e)
        }

def check_document_requirements(order_id: int) -> Dict[str, Any]:
    """
    Check if an order has all required documents
    
    Args:
        order_id (int): Order ID
        
    Returns:
        dict: Document requirements status
    """
    try:
        documents = get_documents_by_order(order_id)
        
        # Required document types
        required_types = ['invoice', 'bill_of_lading']
        optional_types = ['arrival_notice']
        
        # Check uploaded types
        uploaded_types = [doc.get('document_type') for doc in documents]
        
        # Check requirements
        missing_required = [doc_type for doc_type in required_types if doc_type not in uploaded_types]
        has_optional = any(doc_type in uploaded_types for doc_type in optional_types)
        
        is_complete = len(missing_required) == 0
        
        return {
            "order_id": order_id,
            "is_complete": is_complete,
            "missing_required": missing_required,
            "has_optional": has_optional,
            "uploaded_types": uploaded_types,
            "total_documents": len(documents)
        }
        
    except Exception as e:
        print(f"❌ Error checking document requirements: {e}")
        return {
            "order_id": order_id,
            "is_complete": False,
            "error": str(e)
        }

def get_recent_documents(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent documents
    
    Args:
        limit (int): Number of documents to return
        
    Returns:
        list: List of recent documents
    """
    try:
        result = supabase.table("documents").select("*").order("upload_date", desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting recent documents: {e}")
        return []

def search_documents(order_id: int = None, document_type: str = None, status: str = None) -> List[Dict[str, Any]]:
    """
    Search documents with filters
    
    Args:
        order_id (int): Filter by order ID
        document_type (str): Filter by document type
        status (str): Filter by processing status
        
    Returns:
        list: List of matching documents
    """
    try:
        query = supabase.table("documents").select("*")
        
        if order_id:
            query = query.eq("order_id", order_id)
        
        if document_type:
            query = query.eq("document_type", document_type)
        
        if status:
            query = query.eq("processing_status", status)
        
        result = query.order("upload_date", desc=True).execute()
        return result.data if result.data else []
        
    except Exception as e:
        print(f"❌ Error searching documents: {e}")
        return [] 