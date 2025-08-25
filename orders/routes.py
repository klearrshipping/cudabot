# orders/routes.py
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from typing import List, Optional
import os
import sys

# Add the shared directory to the path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'shared'))

from .models import (
    create_order,
    get_order_by_id,
    get_order_by_number,
    get_orders_by_client,
    update_order_status,
    get_order_documents,
    get_orders_with_documents,
    validate_order_completeness,
    get_recent_orders,
    count_orders_by_status
)
from .schemas import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderListResponse,
    OrderValidationResponse,
    OrderStatsResponse,
    OrderWithDocumentsResponse,
    OrderSearchParams,
    OrderCreateResponse,
    DocumentType
)
from shared.file_utils import save_document_file, delete_document_file
from shared.order_generator import validate_order_number

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderCreateResponse, status_code=201)
async def create_new_order(order_data: OrderCreate):
    """
    Create a new customs declaration order
    
    - **client_id**: Required client ID
    - **description**: Optional order description
    """
    try:
        # Create order
        result = create_order(order_data.client_id, order_data.description)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create order")
        
        return OrderCreateResponse(order=OrderResponse(**result))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    """
    Get a specific order by ID
    
    - **order_id**: Order's unique identifier
    """
    try:
        result = get_order_by_id(order_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        
        return OrderResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/number/{order_number}", response_model=OrderResponse)
async def get_order_by_number(order_number: str):
    """
    Get a specific order by order number
    
    - **order_number**: Order number (format: ORD-YYYYMMDD-SEQUENCE)
    """
    try:
        if not validate_order_number(order_number):
            raise HTTPException(status_code=400, detail="Invalid order number format")
        
        result = get_order_by_number(order_number)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Order with number {order_number} not found")
        
        return OrderResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=OrderListResponse)
async def list_orders(
    limit: int = Query(10, ge=1, le=100, description="Number of orders to return"),
    offset: int = Query(0, ge=0, description="Number of orders to skip"),
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    status: Optional[str] = Query(None, description="Filter by order status")
):
    """
    Get a paginated list of orders with optional filtering
    
    - **limit**: Maximum number of orders to return (1-100)
    - **offset**: Number of orders to skip for pagination
    - **client_id**: Filter by client ID
    - **status**: Filter by order status
    """
    try:
        # Get orders with documents
        orders_data = get_orders_with_documents()
        
        # Apply filters
        if client_id:
            orders_data = [order for order in orders_data if order.get('client_id') == client_id]
        
        if status:
            orders_data = [order for order in orders_data if order.get('status') == status]
        
        # Apply pagination
        total = len(orders_data)
        paginated_orders = orders_data[offset:offset + limit]
        
        # Convert to response models
        orders = [OrderResponse(**order) for order in paginated_orders]
        
        return OrderListResponse(
            orders=orders,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/client/{client_id}", response_model=List[OrderResponse])
async def get_client_orders(client_id: int):
    """
    Get all orders for a specific client
    
    - **client_id**: Client's unique identifier
    """
    try:
        orders = get_orders_by_client(client_id)
        
        if not orders:
            return []
        
        return [OrderResponse(**order) for order in orders]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(order_id: int, order_data: OrderUpdate):
    """
    Update an existing order
    
    - **order_id**: Order's unique identifier
    - **order_data**: Fields to update
    """
    try:
        # Get existing order
        existing_order = get_order_by_id(order_id)
        if not existing_order:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        
        # Update fields
        update_data = {}
        if order_data.description is not None:
            update_data["description"] = order_data.description
        if order_data.status is not None:
            update_data["status"] = order_data.status.value
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update order
        result = update_order_status(order_id, update_data.get("status", existing_order["status"]))
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update order")
        
        return OrderResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{order_id}/validation", response_model=OrderValidationResponse)
async def validate_order(order_id: int):
    """
    Validate if an order has all required documents
    
    - **order_id**: Order's unique identifier
    """
    try:
        # Check if order exists
        order = get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        
        # Validate order completeness
        validation = validate_order_completeness(order_id)
        
        return OrderValidationResponse(**validation)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{order_id}/documents", response_model=OrderWithDocumentsResponse)
async def get_order_with_documents(order_id: int):
    """
    Get an order with all its documents
    
    - **order_id**: Order's unique identifier
    """
    try:
        # Get order
        order = get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        
        # Get documents
        documents = get_order_documents(order_id)
        
        # Validate order
        validation = validate_order_completeness(order_id)
        
        return OrderWithDocumentsResponse(
            order=OrderResponse(**order),
            documents=documents,
            validation=OrderValidationResponse(**validation)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/stats/summary", response_model=OrderStatsResponse)
async def get_order_stats():
    """
    Get order statistics and summary
    """
    try:
        # Get recent orders
        recent_orders_data = get_recent_orders(10)
        recent_orders = [OrderResponse(**order) for order in recent_orders_data]
        
        # Get status counts
        status_counts = count_orders_by_status()
        
        # Calculate total
        total_orders = sum(status_counts.values())
        
        return OrderStatsResponse(
            total_orders=total_orders,
            orders_by_status=status_counts,
            recent_orders=recent_orders
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/{order_id}/documents/{document_type}")
async def upload_document(
    order_id: int,
    document_type: DocumentType,
    file: UploadFile = File(...)
):
    """
    Upload a document for an order
    
    - **order_id**: Order's unique identifier
    - **document_type**: Type of document (invoice, bill_of_lading, arrival_notice)
    - **file**: Document file to upload
    """
    try:
        # Check if order exists
        order = get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")
        
        # Save uploaded file temporarily
        temp_file_path = f"temp/{file.filename}"
        os.makedirs("temp", exist_ok=True)
        
        with open(temp_file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        
        # Save document to proper location
        success, result = save_document_file(
            temp_file_path,
            order["order_number"],
            document_type.value,
            file.filename
        )
        
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to save document: {result}")
        
        # TODO: Create document record in database
        # This would be implemented in the documents module
        
        return {
            "message": "Document uploaded successfully",
            "file_path": result,
            "document_type": document_type.value,
            "order_number": order["order_number"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 