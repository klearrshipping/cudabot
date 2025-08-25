#!/usr/bin/env python3
"""
File Utilities for Document Upload and Storage
Handles file operations for the customs declaration workflow
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modules'))

# Allowed file extensions
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def create_order_directory(order_number: str) -> str:
    """
    Create directory structure for an order
    
    Args:
        order_number (str): Order number
        
    Returns:
        str: Path to the order directory
    """
    try:
        # Base uploads directory
        base_dir = Path("uploads/orders")
        order_dir = base_dir / order_number
        
        # Create subdirectories
        subdirs = ["invoices", "bills_of_lading", "arrival_notices"]
        
        for subdir in subdirs:
            (order_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        print(f"✅ Created order directory: {order_dir}")
        return str(order_dir)
        
    except Exception as e:
        print(f"❌ Error creating order directory: {e}")
        return ""

def validate_file_upload(file_path: str, file_size: int) -> Tuple[bool, str]:
    """
    Validate uploaded file
    
    Args:
        file_path (str): Path to uploaded file
        file_size (int): File size in bytes
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return False, f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            return False, f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE} bytes"
        
        # Check if file exists
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        return True, ""
        
    except Exception as e:
        return False, f"File validation error: {str(e)}"

def save_document_file(temp_file_path: str, order_number: str, document_type: str, original_filename: str) -> Tuple[bool, str]:
    """
    Save uploaded document to appropriate directory
    
    Args:
        temp_file_path (str): Path to temporary uploaded file
        order_number (str): Order number
        document_type (str): Type of document (invoice, bill_of_lading, arrival_notice)
        original_filename (str): Original filename
        
    Returns:
        Tuple[bool, str]: (success, file_path_or_error)
    """
    try:
        # Validate file
        file_size = os.path.getsize(temp_file_path)
        is_valid, error_msg = validate_file_upload(temp_file_path, file_size)
        
        if not is_valid:
            return False, error_msg
        
        # Create order directory if it doesn't exist
        order_dir = create_order_directory(order_number)
        if not order_dir:
            return False, "Failed to create order directory"
        
        # Map document type to directory
        type_to_dir = {
            'invoice': 'invoices',
            'bill_of_lading': 'bills_of_lading',
            'arrival_notice': 'arrival_notices'
        }
        
        if document_type not in type_to_dir:
            return False, f"Invalid document type: {document_type}"
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(original_filename).suffix
        new_filename = f"{document_type}_{timestamp}{file_ext}"
        
        # Destination path
        dest_dir = Path(order_dir) / type_to_dir[document_type]
        dest_path = dest_dir / new_filename
        
        # Copy file to destination
        shutil.copy2(temp_file_path, dest_path)
        
        # Return relative path for database storage
        relative_path = f"uploads/orders/{order_number}/{type_to_dir[document_type]}/{new_filename}"
        
        print(f"✅ File saved: {relative_path}")
        return True, relative_path
        
    except Exception as e:
        return False, f"Error saving file: {str(e)}"

def get_document_path(order_number: str, document_type: str, filename: str) -> str:
    """
    Get full path to a document file
    
    Args:
        order_number (str): Order number
        document_type (str): Document type
        filename (str): Filename
        
    Returns:
        str: Full path to document
    """
    type_to_dir = {
        'invoice': 'invoices',
        'bill_of_lading': 'bills_of_lading',
        'arrival_notice': 'arrival_notices'
    }
    
    if document_type not in type_to_dir:
        return ""
    
    return f"uploads/orders/{order_number}/{type_to_dir[document_type]}/{filename}"

def delete_document_file(file_path: str) -> bool:
    """
    Delete a document file
    
    Args:
        file_path (str): Path to file to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ Deleted file: {file_path}")
            return True
        else:
            print(f"⚠️  File not found: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error deleting file: {e}")
        return False

def get_file_info(file_path: str) -> Optional[dict]:
    """
    Get file information
    
    Args:
        file_path (str): Path to file
        
    Returns:
        dict: File information or None if error
    """
    try:
        if not os.path.exists(file_path):
            return None
        
        stat = os.stat(file_path)
        return {
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'exists': True
        }
        
    except Exception as e:
        print(f"❌ Error getting file info: {e}")
        return None 