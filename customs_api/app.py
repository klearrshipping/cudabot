#!/usr/bin/env python3
"""
FastAPI Application for Customs Declaration Workflow
Handles file uploads and integrates with orders/documents system
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
from typing import Optional, List
import json
from datetime import datetime
from pathlib import Path

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared'))

# Import our modules
from orders.models import create_order, get_order_by_id, validate_order_completeness
from orders.schemas import OrderCreate
from documents.models import create_document_record
from shared.file_utils import save_document_file, validate_file_upload
from shared.order_generator import generate_order_number
from modules.order_process.process_order import OrderProcessor

# Initialize FastAPI app
app = FastAPI(
    title="Customs Declaration API",
    description="API for processing customs declaration documents",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (for serving the HTML page)
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    """Serve the main upload page"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")

@app.post("/api/upload-documents")
async def upload_documents(
    invoices: List[UploadFile] = File(..., description="Invoice documents"),
    bill_of_lading: UploadFile = File(..., description="Bill of lading document"),
    arrival_notice: Optional[UploadFile] = File(None, description="Arrival notice (optional)"),
    client_id: int = Form(1, description="Client ID"),
    description: Optional[str] = Form(None, description="Order description")
):
    """
    Upload documents for customs declaration processing
    
    - **invoices**: Required invoice documents (multiple allowed)
    - **bill_of_lading**: Required bill of lading document  
    - **arrival_notice**: Optional arrival notice document
    - **client_id**: Client ID for the order
    - **description**: Optional order description
    """
    try:
        # Validate required files
        if not invoices or len(invoices) == 0 or not bill_of_lading:
            raise HTTPException(status_code=400, detail="At least one invoice and bill of lading are required")
        
        # Validate file types
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        
        # Validate all invoice files
        for i, invoice in enumerate(invoices):
            file_ext = os.path.splitext(invoice.filename)[1].lower()
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invoice {i+1} file type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        # Validate bill of lading
        bol_ext = os.path.splitext(bill_of_lading.filename)[1].lower()
        if bol_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Bill of lading file type {bol_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Create order using OrderProcessor to generate folder structure
        order_processor = OrderProcessor()
        
        # Create order with folder structure
        order_info = order_processor.create_order(
            description=description,
            client_name=f"Client {client_id}"  # You might want to get actual client name
        )
        
        if 'error' in order_info:
            raise HTTPException(status_code=500, detail=f"Failed to create order: {order_info['error']}")
        
        order_number = order_info['order_number']
        
        # Also create order in database for compatibility
        order_data = OrderCreate(client_id=client_id, description=description)
        order = create_order(order_data.client_id, order_data.description)
        
        if not order:
            raise HTTPException(status_code=500, detail="Failed to create database order record")
        
        order_id = order['id']
        
        # Save files and create document records
        documents_created = []
        
        # Process multiple invoices
        invoice_paths = []
        for i, invoice in enumerate(invoices):
            invoice_success, invoice_path = await save_uploaded_file(
                invoice, order_number, f"invoice_{i+1}", order_id
            )
            if invoice_success:
                invoice_paths.append(invoice_path)
                documents_created.append(f"invoice_{i+1}")
        
        # Process bill of lading
        bol_success, bol_path = await save_uploaded_file(
            bill_of_lading, order_number, "bill_of_lading", order_id
        )
        if bol_success:
            documents_created.append("bill_of_lading")
        
        # Process arrival notice (optional)
        arrival_path = None
        if arrival_notice:
            arrival_success, arrival_path = await save_uploaded_file(
                arrival_notice, order_number, "arrival_notice", order_id
            )
            if arrival_success:
                documents_created.append("arrival_notice")
        
        # Validate order completeness
        validation = validate_order_completeness(order_id)
        
        # Start automatic document processing and eSAD processing
        processing_started = False
        try:
            from modules.extraction_process.document_processor import DocumentProcessor
            from modules.esad_processor.process_esad import ESADOrchestrator
            
            # Process documents and eSAD in background (non-blocking)
            import threading
            print(f"[WF] Scheduling complete workflow for {order_number}")
            processing_thread = threading.Thread(
                target=process_complete_workflow,
                args=(order_number,)
            )
            processing_thread.daemon = True
            processing_thread.start()
            
            print(f"🔄 Started automatic complete workflow for order: {order_number}")
            processing_started = True
            
        except Exception as e:
            print(f"⚠️ Automatic processing failed: {e}")
            # Continue with upload success even if processing fails
        
        return {
            "success": True,
            "message": f"Documents uploaded successfully - {len(invoices)} invoice(s) + BOL - Complete workflow (Document extraction + eSAD processing) started automatically",
            "order": {
                "id": order_id,
                "order_number": order_number,
                "status": order['status'],
                "folder_structure": {
                    "base_path": f"processed_orders/{order_number}",
                    "subdirectories": ["file_uploads", "invoices", "bills_of_lading", "esad_files"]
                }
            },
            "documents_uploaded": documents_created,
            "invoice_count": len(invoices),
            "validation": validation,
            "processing_started": processing_started,
            "workflow_stages": [
                "Document extraction (automatic)",
                "eSAD processing (automatic)", 
                "Final customs declaration generation (automatic)"
            ],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def save_uploaded_file(
    file: UploadFile, 
    order_number: str, 
    document_type: str, 
    order_id: int
) -> tuple[bool, Optional[str]]:
    """
    Save uploaded file and create document record using updated shared/file_utils
    
    Returns:
        tuple: (success, file_path_or_error)
    """
    try:
        # Create temporary file
        temp_file_path = f"temp/{file.filename}"
        os.makedirs("temp", exist_ok=True)
        
        # Save uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        
        # Use the updated shared/file_utils function
        success, result = save_document_file(
            temp_file_path,
            order_number,
            document_type,
            file.filename
        )
        
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if not success:
            return False, result
        
        # Update order metadata to track the file
        try:
            order_processor = OrderProcessor()
            order_processor.add_file_to_order_metadata(order_number, result, document_type)
        except Exception as e:
            print(f"⚠️  Warning: Failed to update order metadata: {e}")
            # Continue anyway, file was saved successfully
        
        # Create document record in database
        document_data = {
            "order_id": order_id,
            "document_type": document_type,
            "file_path": result,
            "file_name": file.filename,
            "file_size": len(content)
        }
        
        doc_record = create_document_record(document_data)
        if not doc_record:
            print(f"⚠️  Warning: Failed to create document record for {document_type}")
        
        return True, result
        
    except Exception as e:
        return False, str(e)

@app.get("/api/orders/{order_id}")
async def get_order(order_id: int):
    """Get order by ID"""
    try:
        order = get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        
        return order
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting order: {str(e)}")

@app.get("/api/orders/{order_id}/validation")
async def validate_order(order_id: int):
    """Validate order completeness"""
    try:
        validation = validate_order_completeness(order_id)
        return validation
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating order: {str(e)}")

@app.get("/api/orders/{order_id}/context")
async def get_order_context(order_id: int):
    """
    Get complete order context including BOL and invoice data for hscode_api.
    
    Returns:
        {
            "contextual_data": {
                "invoice_data": {...},
                "bill_of_lading": {...},
                "user_query": "Order ORD-123"
            },
            "order_id": 123,
            "order_number": "ORD-123"
        }
    """
    try:
        # Step 1: Get order data from database
        from modules.core.supabase_client import get_order_extractions
        
        order_data = get_order_extractions(order_id)
        if not order_data:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        
        order_number = order_data['order']['order_number']
        
        # Step 2: Get file paths
        from pathlib import Path
        processed_orders_dir = Path("processed_orders") / order_number
        
        # Step 3: Load BOL and invoice JSON files from the new structure
        # Check both possible locations for backward compatibility
        bol_file = processed_orders_dir / "bills_of_lading" / f"bill_of_lading_{order_number}_primary_extract.json"
        invoice_file = processed_orders_dir / "invoices" / f"invoice_{order_number}_primary_extract.json"
        
        # Fallback to old structure if new structure doesn't exist
        if not bol_file.exists():
            old_processed_data_dir = Path("processed_data") / "orders" / order_number / "primary_process"
            bol_file = old_processed_data_dir / f"bill_of_lading_{order_number}_primary_extract.json"
        
        if not invoice_file.exists():
            old_processed_data_dir = Path("processed_data") / "orders" / order_number / "primary_process"
            invoice_file = old_processed_data_dir / f"invoice_{order_number}_primary_extract.json"
        
        bol_data = {}
        invoice_data = {}
        
        if bol_file.exists():
            with open(bol_file, 'r', encoding='utf-8') as f:
                bol_data = json.load(f)
        else:
            print(f"⚠️ BOL file not found: {bol_file}")
        
        if invoice_file.exists():
            with open(invoice_file, 'r', encoding='utf-8') as f:
                invoice_data = json.load(f)
        else:
            print(f"⚠️ Invoice file not found: {invoice_file}")
        
        # Step 4: Return structured response
        return {
            "contextual_data": {
                "invoice_data": invoice_data,
                "bill_of_lading": bol_data,
                "user_query": f"Order {order_number}"
            },
            "order_id": order_id,
            "order_number": order_number,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_order_context: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

def process_complete_workflow(order_number: str):
    """
    Process complete workflow: Document extraction + eSAD processing
    
    Args:
        order_number (str): Order number to process
    """
    try:
        print(f"[WF] Begin complete workflow: {order_number}")
        
        # Stage 1: Document Extraction
        print(f"📄 STAGE 1: Document Extraction")
        print(f"─────────────────────────────────")
        
        from modules.extraction_process.document_processor import DocumentProcessor
        doc_processor = DocumentProcessor()
        
        # Process documents
        doc_results = doc_processor.process_order_documents(order_number)
        
        if 'error' in doc_results:
            print(f"❌ Document extraction failed: {doc_results['error']}")
            return
        
        try:
            result_keys = list(doc_results.keys()) if isinstance(doc_results, dict) else []
        except Exception:
            result_keys = []
        print(f"[WF] Extraction finished: {order_number} result_keys={result_keys}")
        print(f"✅ Document extraction completed successfully")

        # Additional DEBUG context prior to ESAD stage
        try:
            print(f"[WF] DEBUG: About to start Stage 2 for {order_number}")
            print(f"[WF] DEBUG: Current working directory: {os.getcwd()}")
            print(f"[WF] DEBUG: Python path head: {sys.path[:3]}")
        except Exception as _dbg_e:
            print(f"[WF] DEBUG: Failed to print env info: {_dbg_e}")
        
        # Stage 2: eSAD Processing
        print(f"\n🔧 STAGE 2: eSAD Processing")
        print(f"─────────────────────────────")
        
        # Robust import with explicit diagnostics
        print(f"[WF] DEBUG: Attempting to import ESADOrchestrator...")
        try:
            from modules.esad_processor.process_esad import ESADOrchestrator
            print(f"[WF] DEBUG: ESADOrchestrator import OK")
        except ImportError as ie:
            print(f"[WF] ERROR: ImportError importing ESADOrchestrator: {ie}")
            try:
                esad_file_path = os.path.join(os.path.dirname(__file__), 'modules', 'esad_processor', 'process_esad.py')
                print(f"[WF] DEBUG: Looking for: {esad_file_path} exists={os.path.exists(esad_file_path)}")
            except Exception as _p:
                print(f"[WF] DEBUG: Path check failed: {_p}")
            raise
        except Exception as imp_e:
            print(f"[WF] ERROR: Unexpected import error: {imp_e}")
            raise

        # Initialize orchestrator with diagnostics
        print(f"[WF] DEBUG: Attempting ESADOrchestrator initialization...")
        try:
            esad_orchestrator = ESADOrchestrator()
            print(f"[WF] DEBUG: ESADOrchestrator initialized")
        except Exception as init_e:
            print(f"[WF] ERROR: ESADOrchestrator initialization failed: {init_e}")
            import traceback as _tb
            _tb.print_exc()
            raise
        
        # Process eSAD
        print(f"[WF] ESAD start: {order_number}")
        esad_results = esad_orchestrator.process_order_esad(order_number)
        
        if esad_results.get('status') == 'success':
            print(f"[WF] ESAD done: {order_number} status=success path={esad_results.get('final_esad_path')}")
            print(f"✅ eSAD processing completed successfully!")
            print(f"   📄 Final eSAD: {esad_results.get('final_esad_path')}")
            print(f"   📊 Fields processed: {esad_results.get('processing_summary', {}).get('total_fields', 0)}")
        else:
            print(f"[WF] ESAD done: {order_number} status=error error={esad_results.get('error')}")
            print(f"❌ eSAD processing failed: {esad_results.get('error', 'Unknown error')}")
            return
        
        # Stage 3: Workflow Complete
        print(f"\n🎉 COMPLETE WORKFLOW FINISHED")
        print(f"═══════════════════════════════")
        print(f"   Order: {order_number}")
        print(f"   Status: Ready for customs submission")
        print(f"   Files: Document extraction + eSAD form generated")
        
    except Exception as e:
        print(f"[WF] ERROR in complete workflow {order_number}: {e}")
        print(f"❌ Complete workflow failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    
    print("🚀 Starting Customs Declaration API Server...")
    print("📋 Available endpoints:")
    print("   GET  /                    - Upload interface")
    print("   POST /api/upload-documents - Upload documents")
    print("   GET  /api/orders/{id}     - Get order")
    print("   GET  /api/health          - Health check")
    print("\n🌐 Server will be available at: http://localhost:8000")
    
    # Run using the app object directly to avoid importing the wrong module ('app:app' ambiguity)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid the warning
        log_level="info"
    )