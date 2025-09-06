# orders/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "pending"
    DOCUMENTS_UPLOADED = "documents_uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentType(str, Enum):
    """Document type enumeration"""
    INVOICE = "invoice"
    BILL_OF_LADING = "bill_of_lading"
    ARRIVAL_NOTICE = "arrival_notice"

class OrderCreate(BaseModel):
    """Schema for creating a new order"""
    client_id: int = Field(..., description="ID of the client")
    description: Optional[str] = Field(None, description="Optional order description")
    
    @validator('client_id')
    def validate_client_id(cls, v):
        if v <= 0:
            raise ValueError('Client ID must be positive')
        return v

class OrderUpdate(BaseModel):
    """Schema for updating an order"""
    description: Optional[str] = Field(None, description="Order description")
    status: Optional[OrderStatus] = Field(None, description="Order status")

class OrderResponse(BaseModel):
    """Schema for order response"""
    id: int
    order_number: str
    client_id: int
    description: Optional[str]
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class OrderListResponse(BaseModel):
    """Schema for list of orders response"""
    orders: List[OrderResponse]
    total: int
    limit: int
    offset: int

class OrderValidationResponse(BaseModel):
    """Schema for order validation response"""
    order_id: int
    is_complete: bool
    missing_documents: List[str]
    has_arrival_notice: bool
    uploaded_documents: List[str]
    total_documents: int
    error: Optional[str] = None

class OrderStatsResponse(BaseModel):
    """Schema for order statistics response"""
    total_orders: int
    orders_by_status: dict
    recent_orders: List[OrderResponse]

class DocumentUploadResponse(BaseModel):
    """Schema for document upload response"""
    id: int
    order_id: int
    document_type: DocumentType
    file_name: str
    file_path: str
    file_size: int
    upload_date: datetime
    processing_status: str
    
    class Config:
        from_attributes = True

class DocumentCreate(BaseModel):
    """Schema for creating a document record"""
    order_id: int
    document_type: DocumentType
    file_path: str
    file_name: str
    file_size: int
    
    @validator('order_id')
    def validate_order_id(cls, v):
        if v <= 0:
            raise ValueError('Order ID must be positive')
        return v
    
    @validator('file_size')
    def validate_file_size(cls, v):
        if v <= 0:
            raise ValueError('File size must be positive')
        return v

class OrderWithDocumentsResponse(BaseModel):
    """Schema for order with documents response"""
    order: OrderResponse
    documents: List[DocumentUploadResponse]
    validation: OrderValidationResponse

class OrderSearchParams(BaseModel):
    """Schema for order search parameters"""
    client_id: Optional[int] = None
    status: Optional[OrderStatus] = None
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)

class OrderCreateResponse(BaseModel):
    """Schema for order creation response"""
    order: OrderResponse
    message: str = "Order created successfully"
    next_steps: List[str] = [
        "Upload invoice document",
        "Upload bill of lading document",
        "Optionally upload arrival notice"
    ] 