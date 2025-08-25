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
from typing import Optional
import json
from datetime import datetime

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'orders'))
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
    invoice: UploadFile = File(..., description="Invoice document"),
    bill_of_lading: UploadFile = File(..., description="Bill of lading document"),
    arrival_notice: Optional[UploadFile] = File(None, description="Arrival notice (optional)"),
    client_id: int = Form(1, description="Client ID"),
    description: Optional[str] = Form(None, description="Order description")
):
    """
    Upload documents for customs declaration processing
    
    - **invoice**: Required invoice document
    - **bill_of_lading**: Required bill of lading document  
    - **arrival_notice**: Optional arrival notice document
    - **client_id**: Client ID for the order
    - **description**: Optional order description
    """
    try:
        # Validate required files
        if not invoice or not bill_of_lading:
            raise HTTPException(status_code=400, detail="Invoice and bill of lading are required")
        
        # Validate file types
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        
        for file, file_type in [(invoice, "invoice"), (bill_of_lading, "bill_of_lading")]:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400, 
                    detail=f"{file_type} file type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
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
        
        # Process invoice
        invoice_success, invoice_path = await save_uploaded_file(
            invoice, order_number, "invoice", order_id
        )
        if invoice_success:
            documents_created.append("invoice")
        
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
        
        # Start automatic document processing
        processing_started = False
        try:
            from modules.primary_processing.document_processor import DocumentProcessor
            processor = DocumentProcessor()
            
            # Process documents in background (non-blocking)
            import threading
            processing_thread = threading.Thread(
                target=processor.process_order_documents,
                args=(order_number,)
            )
            processing_thread.daemon = True
            processing_thread.start()
            
            print(f"🔄 Started automatic processing for order: {order_number}")
            processing_started = True
            
        except Exception as e:
            print(f"⚠️ Automatic processing failed: {e}")
            # Continue with upload success even if processing fails
        
        return {
            "success": True,
            "message": "Documents uploaded successfully and processing started",
            "order": {
                "id": order_id,
                "order_number": order_number,
                "status": order['status']
            },
            "documents_uploaded": documents_created,
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
        # Create temporary file
        temp_file_path = f"temp/{file.filename}"
        os.makedirs("temp", exist_ok=True)
        
        # Save uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        
        # Save to proper location
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