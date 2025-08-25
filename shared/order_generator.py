#!/usr/bin/env python3
"""
Order Number Generator Utility
Generates unique order numbers for customs declaration workflow
"""

import os
import sys
from datetime import datetime
from typing import Optional

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'modules'))

def generate_order_number() -> str:
    """
    Generate a unique order number in format: ORD-YYYYMMDD-SEQUENCE
    
    Returns:
        str: Unique order number
    """
    try:
        from modules.core.supabase_client import get_supabase_client
        
        # Get current date
        today = datetime.now().strftime("%Y%m%d")
        
        # Get the next sequence number for today
        supabase = get_supabase_client()
        
        # Count existing orders for today
        result = supabase.table("orders").select("order_number").like("order_number", f"ORD-{today}-%").execute()
        
        # Calculate next sequence number
        existing_count = len(result.data) if result.data else 0
        sequence = existing_count + 1
        
        # Format: ORD-YYYYMMDD-SEQUENCE (e.g., ORD-20241201-001)
        order_number = f"ORD-{today}-{sequence:03d}"
        
        return order_number
        
    except Exception as e:
        print(f"❌ Error generating order number: {e}")
        # Fallback: use timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"ORD-{timestamp}"

def validate_order_number(order_number: str) -> bool:
    """
    Validate order number format
    
    Args:
        order_number (str): Order number to validate
        
    Returns:
        bool: True if valid format, False otherwise
    """
    try:
        # Check format: ORD-YYYYMMDD-SEQUENCE
        if not order_number.startswith("ORD-"):
            return False
        
        parts = order_number.split("-")
        if len(parts) != 3:
            return False
        
        # Validate date part (YYYYMMDD)
        date_part = parts[1]
        if len(date_part) != 8:
            return False
        
        # Validate sequence part (numeric)
        sequence_part = parts[2]
        if not sequence_part.isdigit():
            return False
        
        return True
        
    except Exception:
        return False

def get_order_by_number(order_number: str) -> Optional[dict]:
    """
    Get order by order number
    
    Args:
        order_number (str): Order number to find
        
    Returns:
        dict: Order data or None if not found
    """
    try:
        from modules.core.supabase_client import get_supabase_client
        
        supabase = get_supabase_client()
        result = supabase.table("orders").select("*").eq("order_number", order_number).execute()
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"❌ Error getting order by number: {e}")
        return None 