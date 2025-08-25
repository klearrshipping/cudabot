
import os
from supabase import create_client, Client
from typing import Dict, Any, List, Optional
from datetime import datetime

# Try to load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    pass

# Try config.py first, then environment variables
try:
    from config import SUPABASE_URL
    try:
        from config import SUPABASE_KEY
    except ImportError:
        try:
            from config import SUPABASE_ANON_KEY as SUPABASE_KEY
        except ImportError:
            SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
except ImportError:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY (or SUPABASE_ANON_KEY) must be set in config.py or .env")

def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# EXISTING METHODS
# =====================================================





# =====================================================
# NEW METHODS FOR DOCUMENT EXTRACTIONS AND ORDERS
# =====================================================

def create_or_get_order(order_number: str, description: str = None, customer_name: str = None) -> Dict[str, Any]:
    """Create a new order or get existing one by order number"""
    try:
        supabase = get_supabase_client()
        
        # Check if order already exists
        result = supabase.table("orders").select("*").eq("order_number", order_number).execute()
        
        if result.data:
            print(f"✅ Found existing order: {order_number}")
            return result.data[0]
        
        # Create new order
        order_data = {
            "order_number": order_number,
            "description": description or f"Order {order_number}",
            "customer_name": customer_name or "Unknown Customer"
        }
        
        result = supabase.table("orders").insert(order_data).execute()
        print(f"✅ Created new order: {order_number}")
        return result.data[0]
        
    except Exception as e:
        print(f"❌ Error creating/getting order: {e}")
        return None

def create_document_record(order_id: int, file_name: str, file_path: str, document_type: str, 
                          description: str = None, file_size: int = None, mime_type: str = None) -> Dict[str, Any]:
    """Create a new document record"""
    try:
        supabase = get_supabase_client()
        
        document_data = {
            "order_id": order_id,
            "file_name": file_name,
            "file_path": file_path,
            "document_type": document_type,
            "description": description or f"{document_type.upper()} document",
            "file_size": file_size,
            "mime_type": mime_type or "application/pdf"
        }
        
        result = supabase.table("documents").insert(document_data).execute()
        print(f"✅ Created document record: {file_name}")
        return result.data[0]
        
    except Exception as e:
        print(f"❌ Error creating document record: {e}")
        return None

def save_bol_extraction(document_id: int, order_id: int, extracted_data: Dict[str, Any], 
                       metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Save BOL extraction results to database"""
    try:
        supabase = get_supabase_client()
        
        # Prepare BOL extraction data
        bol_data = {
            "document_id": document_id,
            "order_id": order_id,
            "reported_date": extracted_data.get("reported_date"),
            "consignee_name": extracted_data.get("consignee_name"),
            "consignee_address": extracted_data.get("consignee_address"),
            "consignee_tel": extracted_data.get("consignee_tel#"),
            "shipper": extracted_data.get("shipper"),
            "shipper_address": extracted_data.get("shipper_address"),
            "master_bill_of_lading": extracted_data.get("master_bill_of_lading"),
            "voyage_number": extracted_data.get("voyage_number"),
            "bill_of_lading": extracted_data.get("bill_of_lading"),
            "last_departure_date": extracted_data.get("last_departure_date"),
            "port_of_origin": extracted_data.get("port_of_origin"),
            "port_of_loading": extracted_data.get("port_of_loading"),
            "port_of_destination": extracted_data.get("port_of_destination"),
            "vessel": extracted_data.get("vessel"),
            "manifest_registration_number": extracted_data.get("manifest/registration_#"),
            "package_type": extracted_data.get("package_type"),
            "package_count": extracted_data.get("package_count"),
            "gross_weight": extracted_data.get("gross_weight"),
            "measurement": extracted_data.get("measurement"),
            "raw_extraction_data": extracted_data,
            "extraction_status": "success"
        }
        
        # Add metadata if provided
        if metadata:
            bol_data.update({
                "processor": metadata.get("processor", "claude_sonnet_4_via_openrouter"),
                "model": metadata.get("model"),
                "processing_method": metadata.get("processing_method", "pdf_to_image_conversion"),
                "confidence_score": metadata.get("confidence_score")
            })
        
        result = supabase.table("bol_extractions").insert(bol_data).execute()
        print(f"✅ Saved BOL extraction to database")
        return result.data[0]
        
    except Exception as e:
        print(f"❌ Error saving BOL extraction: {e}")
        return None

def save_invoice_extraction(document_id: int, order_id: int, extracted_data: Dict[str, Any], 
                          metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Save invoice extraction results to database"""
    try:
        supabase = get_supabase_client()
        
        # Prepare invoice extraction data
        invoice_data = {
            "document_id": document_id,
            "order_id": order_id,
            "invoice_number": extracted_data.get("invoice_number"),
            "invoice_date": extracted_data.get("invoice_date"),
            "seller_name": extracted_data.get("seller_name"),
            "seller_address": extracted_data.get("seller_address"),
            "buyer_name": extracted_data.get("buyer_name"),
            "buyer_address": extracted_data.get("buyer_address"),
            "currency": extracted_data.get("currency"),
            "total_amount": extracted_data.get("total_amount"),
            "subtotal": extracted_data.get("subtotal"),
            "tax_amount": extracted_data.get("tax_amount"),
            "freight_amount": extracted_data.get("freight_amount"),
            "insurance_amount": extracted_data.get("insurance_amount"),
            "product_details": extracted_data.get("product_details", {}),
            "raw_extraction_data": extracted_data,
            "extraction_status": "success"
        }
        
        # Add metadata if provided
        if metadata:
            invoice_data.update({
                "processor": metadata.get("processor", "claude_sonnet_4_via_openrouter"),
                "model": metadata.get("model"),
                "processing_method": metadata.get("processing_method", "pdf_to_image_conversion"),
                "confidence_score": metadata.get("confidence_score")
            })
        
        result = supabase.table("invoice_extractions").insert(invoice_data).execute()
        print(f"✅ Saved invoice extraction to database")
        return result.data[0]
        
    except Exception as e:
        print(f"❌ Error saving invoice extraction: {e}")
        return None

def get_order_extractions(order_id: int) -> Dict[str, Any]:
    """Get complete order data including BOL and invoice extractions"""
    try:
        supabase = get_supabase_client()
        
        # Get order details
        order_result = supabase.table("orders").select("*").eq("id", order_id).execute()
        if not order_result.data:
            return None
        
        order = order_result.data[0]
        
        # Get BOL extraction
        bol_result = supabase.table("bol_extractions").select("*").eq("order_id", order_id).execute()
        bol_extraction = bol_result.data[0] if bol_result.data else None
        
        # Get invoice extraction
        invoice_result = supabase.table("invoice_extractions").select("*").eq("order_id", order_id).execute()
        invoice_extraction = invoice_result.data[0] if invoice_result.data else None
        
        return {
            "order": order,
            "bol_extraction": bol_extraction,
            "invoice_extraction": invoice_extraction
        }
        
    except Exception as e:
        print(f"❌ Error getting order extractions: {e}")
        return None

def get_order_by_number(order_number: str) -> Dict[str, Any]:
    """Get order by order number"""
    try:
        supabase = get_supabase_client()
        result = supabase.table("orders").select("*").eq("order_number", order_number).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ Error getting order by number: {e}")
        return None

def save_processing_result(order_id: int, processor_name: str, status: str, 
                          input_data: Dict[str, Any] = None, output_data: Dict[str, Any] = None,
                          error_message: str = None, processing_time_ms: int = None) -> Dict[str, Any]:
    """Save processing result to database"""
    try:
        supabase = get_supabase_client()
        
        result_data = {
            "order_id": order_id,
            "processor_name": processor_name,
            "status": status,
            "input_data": input_data,
            "output_data": output_data,
            "error_message": error_message,
            "processing_time_ms": processing_time_ms
        }
        
        result = supabase.table("processing_results").insert(result_data).execute()
        print(f"✅ Saved processing result for {processor_name}")
        return result.data[0]
        
    except Exception as e:
        print(f"❌ Error saving processing result: {e}")
        return None

def save_esad_field(order_id: int, field_name: str, field_value: str, field_type: str = "text",
                    confidence_score: float = None, source_document: str = "combined", 
                    extraction_method: str = "rule_based") -> Dict[str, Any]:
    """Save ESAD field to database"""
    try:
        supabase = get_supabase_client()
        
        field_data = {
            "order_id": order_id,
            "field_name": field_name,
            "field_value": field_value,
            "field_type": field_type,
            "confidence_score": confidence_score,
            "source_document": source_document,
            "extraction_method": extraction_method
        }
        
        result = supabase.table("esad_fields").insert(field_data).execute()
        print(f"✅ Saved ESAD field: {field_name}")
        return result.data[0]
        
    except Exception as e:
        print(f"❌ Error saving ESAD field: {e}")
        return None

def get_esad_fields_for_order(order_id: int) -> List[Dict[str, Any]]:
    """Get all ESAD fields for a specific order"""
    try:
        supabase = get_supabase_client()
        result = supabase.table("esad_fields").select("*").eq("order_id", order_id).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ Error getting ESAD fields: {e}")
        return []

def check_database_schema():
    """Check if all required tables exist and create them if needed"""
    try:
        supabase = get_supabase_client()
        
        # List of required tables
        required_tables = [
            "orders", "documents", "bol_extractions", "invoice_extractions", 
            "processing_results", "esad_fields"
        ]
        
        missing_tables = []
        
        for table in required_tables:
            try:
                result = supabase.table(table).select("id").limit(1).execute()
                print(f"✅ Table {table} exists")
            except Exception:
                print(f"❌ Table {table} missing")
                missing_tables.append(table)
        
        if missing_tables:
            print(f"\n⚠️ Missing tables: {', '.join(missing_tables)}")
            print("💡 Please run the database_schema.sql script in your Supabase SQL editor")
            return False
        
        print("\n✅ All required database tables are available")
        return True
        
    except Exception as e:
        print(f"❌ Error checking database schema: {e}")
        return False
