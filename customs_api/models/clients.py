# clients/models.py
from supabase import create_client
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

# Initialize Supabase client
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

def create_client_record(client_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new client record in the database
    
    Args:
        client_data (dict): Client information including:
            - company_name (str): Company or organization name
            - contact_email (str): Primary contact email address
            - phone_number (str): Contact phone number
            - address (str): Business address
            - tax_id (str): Tax identification number
    
    Returns:
        dict: Created client record with ID and timestamps
    """
    try:
        result = supabase.table("clients").insert(client_data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error creating client record: {e}")
        return None

def get_client_by_id(client_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a client record by ID
    
    Args:
        client_id (int): Primary key of the client
    
    Returns:
        dict: Client record or None if not found
    """
    try:
        result = supabase.table("clients").select("*").eq("id", client_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error retrieving client by ID: {e}")
        return None

def get_all_clients() -> List[Dict[str, Any]]:
    """
    Retrieve all client records
    
    Returns:
        list: List of all client records
    """
    try:
        result = supabase.table("clients").select("*").order("created_at", desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error retrieving all clients: {e}")
        return []

def update_client_record(client_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update an existing client record
    
    Args:
        client_id (int): Primary key of the client to update
        update_data (dict): Fields to update
    
    Returns:
        dict: Updated client record or None if error
    """
    try:
        result = supabase.table("clients").update(update_data).eq("id", client_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error updating client record: {e}")
        return None

def delete_client_record(client_id: int) -> bool:
    """
    Delete a client record by ID
    
    Args:
        client_id (int): Primary key of the client to delete
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        result = supabase.table("clients").delete().eq("id", client_id).execute()
        return len(result.data) > 0 if result.data else False
    except Exception as e:
        print(f"❌ Error deleting client record: {e}")
        return False

def search_clients_by_company(company_name: str) -> List[Dict[str, Any]]:
    """
    Search clients by company name (partial match)
    
    Args:
        company_name (str): Company name to search for
    
    Returns:
        list: List of matching client records
    """
    try:
        result = supabase.table("clients").select("*").ilike("company_name", f"%{company_name}%").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error searching clients by company: {e}")
        return []

def get_client_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a client record by email address
    
    Args:
        email (str): Contact email address
    
    Returns:
        dict: Client record or None if not found
    """
    try:
        result = supabase.table("clients").select("*").eq("contact_email", email).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error retrieving client by email: {e}")
        return None

def get_clients_by_tax_id(tax_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve client records by tax ID
    
    Args:
        tax_id (str): Tax identification number
    
    Returns:
        list: List of matching client records
    """
    try:
        result = supabase.table("clients").select("*").eq("tax_id", tax_id).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error retrieving clients by tax ID: {e}")
        return []

def get_recent_clients(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recently created clients
    
    Args:
        limit (int): Maximum number of records to return
    
    Returns:
        list: List of recent client records
    """
    try:
        result = supabase.table("clients").select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error retrieving recent clients: {e}")
        return []

def count_total_clients() -> int:
    """
    Get the total number of client records
    
    Returns:
        int: Total count of clients
    """
    try:
        result = supabase.table("clients").select("id", count="exact").execute()
        return result.count if hasattr(result, 'count') else 0
    except Exception as e:
        print(f"❌ Error counting clients: {e}")
        return 0

def validate_client_data(client_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate client data before database operations
    
    Args:
        client_data (dict): Client data to validate
    
    Returns:
        dict: Validation result with success status and errors
    """
    errors = []
    
    # Check required fields
    if not client_data.get('company_name'):
        errors.append("Company name is required")
    
    # Validate email format if provided
    if client_data.get('contact_email'):
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, client_data['contact_email']):
            errors.append("Invalid email format")
    
    # Validate phone number format if provided
    if client_data.get('phone_number'):
        import re
        phone_pattern = r'^[\+]?[1-9][\d]{0,15}$'
        if not re.match(phone_pattern, client_data['phone_number'].replace(' ', '').replace('-', '').replace('(', '').replace(')', '')):
            errors.append("Invalid phone number format")
    
    # Validate and format Jamaican tax ID if provided
    if client_data.get('tax_id'):
        tax_validation = validate_jamaican_tax_id(client_data['tax_id'])
        if not tax_validation['valid']:
            errors.extend(tax_validation['errors'])
        else:
            # Update the tax_id with the formatted version
            client_data['tax_id'] = tax_validation['formatted_tax_id']
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }

def validate_jamaican_tax_id(tax_id: str) -> Dict[str, Any]:
    """
    Validate and format Jamaican tax ID
    
    Jamaican tax IDs are typically displayed as 114-103-496 but should be stored as 114103496000
    This function automatically formats the tax ID by:
    1. Removing hyphens/dashes
    2. Adding four zeros at the end if not present
    3. Validating the format
    
    Args:
        tax_id (str): Tax ID to validate and format
    
    Returns:
        dict: Validation result with formatted tax ID
    """
    import re
    
    # Remove all non-digit characters
    cleaned_tax_id = re.sub(r'[^\d]', '', tax_id)
    
    # Check if it's a valid Jamaican tax ID format
    if len(cleaned_tax_id) == 9:
        # Add four zeros to make it 13 digits
        formatted_tax_id = cleaned_tax_id + "0000"
        return {
            'valid': True,
            'formatted_tax_id': formatted_tax_id,
            'original': tax_id,
            'message': f"Tax ID formatted from {tax_id} to {formatted_tax_id}"
        }
    elif len(cleaned_tax_id) == 13:
        # Already in correct format
        return {
            'valid': True,
            'formatted_tax_id': cleaned_tax_id,
            'original': tax_id,
            'message': f"Tax ID already in correct format: {cleaned_tax_id}"
        }
    else:
        return {
            'valid': False,
            'formatted_tax_id': None,
            'original': tax_id,
            'errors': [f"Invalid Jamaican tax ID format. Expected 9 digits (e.g., 114103496) or 13 digits (e.g., 1141034960000), got {len(cleaned_tax_id)} digits: {cleaned_tax_id}"]
        }

def format_jamaican_tax_id_for_display(tax_id: str) -> str:
    """
    Format Jamaican tax ID for display (convert from 114103496000 to 114-103-496)
    
    Args:
        tax_id (str): Tax ID in database format (13 digits)
    
    Returns:
        str: Formatted tax ID for display
    """
    import re
    
    # Remove all non-digit characters
    cleaned_tax_id = re.sub(r'[^\d]', '', tax_id)
    
    if len(cleaned_tax_id) == 13:
        # Remove the last 4 zeros and format with hyphens
        base_tax_id = cleaned_tax_id[:-4]
        return f"{base_tax_id[:3]}-{base_tax_id[3:6]}-{base_tax_id[6:]}"
    elif len(cleaned_tax_id) == 9:
        # Format 9-digit tax ID with hyphens
        return f"{cleaned_tax_id[:3]}-{cleaned_tax_id[3:6]}-{cleaned_tax_id[6:]}"
    else:
        # Return original if not in expected format
        return tax_id 