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

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'customs_api'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'customs_api', 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'customs_api', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared'))

# Import our modules
from orders.models import create_order, get_order_by_id, validate_order_completeness
from orders.schemas import OrderCreate
from documents.models import create_document_record
from shared.file_utils import save_document_file, validate_file_upload
from shared.order_generator import generate_order_number

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
    invoices: List[UploadFile] = File(..., description="Invoice documents (multiple allowed)"),
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
        # Debug logging
        print(f"🔍 DEBUG: Received {len(invoices) if invoices else 0} invoice files")
        print(f"🔍 DEBUG: Received BOL: {bill_of_lading.filename if bill_of_lading else 'None'}")
        
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
        
        # Create order
        order_data = OrderCreate(client_id=client_id, description=description)
        order = create_order(order_data.client_id, order_data.description)
        
        if not order:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        order_id = order['id']
        order_number = order['order_number']
        
        # Save files and create document records
        documents_created = []
        
        # Process multiple invoices
        invoice_paths = []
        print(f"🔍 DEBUG: Processing {len(invoices)} invoice files...")
        for i, invoice in enumerate(invoices):
            print(f"🔍 DEBUG: Processing invoice {i+1}: {invoice.filename}")
            invoice_success, invoice_path = await save_uploaded_file(
                invoice, order_number, f"invoice_{i+1}", order_id
            )
            print(f"🔍 DEBUG: Invoice {i+1} result: success={invoice_success}, path={invoice_path}")
            if invoice_success:
                invoice_paths.append(invoice_path)
                documents_created.append(f"invoice_{i+1}")
            else:
                print(f"❌ DEBUG: Invoice {i+1} failed to save: {invoice_path}")
        
        # Process bill of lading
        print(f"🔍 DEBUG: Processing BOL: {bill_of_lading.filename}")
        
        bol_success, bol_path = await save_uploaded_file(
            bill_of_lading, order_number, "bill_of_lading", order_id
        )
        print(f"🔍 DEBUG: BOL result: success={bol_success}, path={bol_path}")
        if bol_success:
            documents_created.append("bill_of_lading")
        else:
            print(f"❌ DEBUG: BOL failed to save: {bol_path}")
            # Don't continue processing if BOL fails - it's required
            raise HTTPException(status_code=500, detail=f"Failed to save BOL: {bol_path}")
        
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
        
        # Start automatic document processing
        processing_started = False
        try:
            # Change to customs_api directory for processing
            original_cwd = os.getcwd()
            try:
                os.chdir('customs_api')
                from modules.extraction_process.document_processor import DocumentProcessor
                processor = DocumentProcessor()
                
                # Process documents synchronously to see errors
                print(f"🔄 Starting document processing for order: {order_number}")
                result = processor.process_order_documents(order_number)
                print(f"✅ Document processing completed: {result}")
                processing_started = True
            finally:
                os.chdir(original_cwd)
            
        except Exception as e:
            print(f"⚠️ Automatic processing failed: {e}")
            import traceback
            traceback.print_exc()
            # Continue with upload success even if processing fails
        
        return {
            "success": True,
            "message": f"Documents uploaded successfully - {len(invoices)} invoice(s) + BOL - Processing started",
            "order": {
                "id": order_id,
                "order_number": order_number,
                "status": order['status']
            },
            "documents_uploaded": documents_created,
            "invoice_count": len(invoices),
            "validation": validation,
            "processing_started": processing_started,
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
    Save uploaded file and create document record
    
    Returns:
        tuple: (success, file_path_or_error)
    """
    try:
        print(f"🔍 DEBUG: Starting save_uploaded_file for {document_type}: {file.filename}")
        
        # Create temporary file
        temp_file_path = f"temp/{file.filename}"
        os.makedirs("temp", exist_ok=True)
        
        # Save uploaded file temporarily
        print(f"🔍 DEBUG: Reading file content...")
        content = await file.read()
        print(f"🔍 DEBUG: Read {len(content)} bytes")
        
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content)
        
        print(f"🔍 DEBUG: Saved temp file: {temp_file_path}")
        
        # Save to proper location in customs_api/processed_orders
        # Change to customs_api directory temporarily to use the correct path
        original_cwd = os.getcwd()
        try:
            os.chdir('customs_api')
            print(f"🔍 DEBUG: Changed to customs_api directory")
            success, result = save_document_file(
                f"../{temp_file_path}",
                order_number,
                document_type,
                file.filename
            )
            print(f"🔍 DEBUG: save_document_file returned: success={success}, result={result}")
        finally:
            os.chdir(original_cwd)
            print(f"🔍 DEBUG: Restored to original directory")
        
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"🔍 DEBUG: Cleaned up temp file")
        
        if not success:
            print(f"❌ DEBUG: save_document_file failed: {result}")
            return False, result
        
        # Create document record in database
        # Use base document type for database (invoice_1 -> invoice, bill_of_lading -> bill_of_lading)
        if document_type == 'bill_of_lading':
            base_document_type = 'bill_of_lading'
        elif document_type.startswith('invoice_') and document_type.split('_')[1].isdigit():
            base_document_type = 'invoice'
        else:
            base_document_type = document_type
        
        document_data = {
            "order_id": order_id,
            "document_type": base_document_type,
            "file_path": result,
            "file_name": file.filename,
            "file_size": len(content)
        }
        
        print(f"🔍 DEBUG: Creating document record: {document_data}")
        doc_record = create_document_record(document_data)
        if not doc_record:
            print(f"⚠️  Warning: Failed to create document record for {document_type}")
        else:
            print(f"✅ DEBUG: Created document record for {document_type}")
        
        return True, result
        
    except Exception as e:
        print(f"❌ DEBUG: Exception in save_uploaded_file: {e}")
        import traceback
        traceback.print_exc()
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

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

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
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 