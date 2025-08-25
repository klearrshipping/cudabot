# clients/schemas.py
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re
from datetime import datetime

class ClientCreate(BaseModel):
    """Schema for creating a new client"""
    company_name: str = Field(..., min_length=1, max_length=255, description="Company or organization name")
    contact_email: EmailStr = Field(..., description="Primary contact email address")
    phone_number: Optional[str] = Field(None, max_length=20, description="Contact phone number")
    address: Optional[str] = Field(None, max_length=500, description="Business address")
    tax_id: Optional[str] = Field(None, max_length=20, description="Tax identification number")
    
    @validator('company_name')
    def validate_company_name(cls, v):
        if not v.strip():
            raise ValueError('Company name cannot be empty')
        return v.strip()
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            # Remove common formatting characters
            cleaned = re.sub(r'[\s\-\(\)]', '', v)
            # Check if it's a valid phone number format
            if not re.match(r'^[\+]?[1-9][\d]{0,15}$', cleaned):
                raise ValueError('Invalid phone number format')
        return v
    
    @validator('tax_id')
    def validate_jamaican_tax_id(cls, v):
        if v is not None:
            # Remove all non-digit characters
            cleaned = re.sub(r'[^\d]', '', v)
            
            # Check if it's a valid Jamaican TRN format
            if len(cleaned) == 9:
                # Add four zeros to make it 13 digits
                return cleaned + "0000"
            elif len(cleaned) == 13:
                # Already in correct format
                return cleaned
            else:
                raise ValueError(f'Invalid Jamaican TRN format. TRN must be exactly 13 digits. Expected 9 digits (e.g., 114103496) or 13 digits (e.g., 1141034960000), got {len(cleaned)} digits')
        return v

class ClientUpdate(BaseModel):
    """Schema for updating an existing client"""
    company_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Company or organization name")
    contact_email: Optional[EmailStr] = Field(None, description="Primary contact email address")
    phone_number: Optional[str] = Field(None, max_length=20, description="Contact phone number")
    address: Optional[str] = Field(None, max_length=500, description="Business address")
    tax_id: Optional[str] = Field(None, max_length=20, description="Tax identification number")
    
    @validator('company_name')
    def validate_company_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Company name cannot be empty')
        return v.strip() if v else v
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            # Remove common formatting characters
            cleaned = re.sub(r'[\s\-\(\)]', '', v)
            # Check if it's a valid phone number format
            if not re.match(r'^[\+]?[1-9][\d]{0,15}$', cleaned):
                raise ValueError('Invalid phone number format')
        return v
    
    @validator('tax_id')
    def validate_jamaican_tax_id(cls, v):
        if v is not None:
            # Remove all non-digit characters
            cleaned = re.sub(r'[^\d]', '', v)
            
            # Check if it's a valid Jamaican TRN format
            if len(cleaned) == 9:
                # Add four zeros to make it 13 digits
                return cleaned + "0000"
            elif len(cleaned) == 13:
                # Already in correct format
                return cleaned
            else:
                raise ValueError(f'Invalid Jamaican TRN format. TRN must be exactly 13 digits. Expected 9 digits (e.g., 114103496) or 13 digits (e.g., 1141034960000), got {len(cleaned)} digits')
        return v

class ClientResponse(BaseModel):
    """Schema for client response data"""
    id: int = Field(..., description="Primary key")
    company_name: str = Field(..., description="Company or organization name")
    contact_email: str = Field(..., description="Primary contact email address")
    phone_number: Optional[str] = Field(None, description="Contact phone number")
    address: Optional[str] = Field(None, description="Business address")
    tax_id: Optional[str] = Field(None, description="Tax identification number")
    created_at: datetime = Field(..., description="Timestamp when record was created")
    
    class Config:
        from_attributes = True

class ClientSearch(BaseModel):
    """Schema for client search parameters"""
    company_name: Optional[str] = Field(None, description="Search by company name (partial match)")
    contact_email: Optional[str] = Field(None, description="Search by exact email address")
    tax_id: Optional[str] = Field(None, description="Search by tax ID")
    limit: Optional[int] = Field(10, ge=1, le=100, description="Maximum number of results")
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")
    
    @validator('tax_id')
    def validate_search_tax_id(cls, v):
        if v is not None:
            # Remove all non-digit characters
            cleaned = re.sub(r'[^\d]', '', v)
            
            # Check if it's a valid Jamaican TRN format
            if len(cleaned) == 9:
                # Add four zeros to make it 13 digits
                return cleaned + "0000"
            elif len(cleaned) == 13:
                # Already in correct format
                return cleaned
            else:
                raise ValueError(f'Invalid Jamaican TRN format. TRN must be exactly 13 digits. Expected 9 digits (e.g., 114103496) or 13 digits (e.g., 1141034960000), got {len(cleaned)} digits')
        return v

class ClientListResponse(BaseModel):
    """Schema for paginated client list response"""
    clients: list[ClientResponse] = Field(..., description="List of client records")
    total_count: int = Field(..., description="Total number of clients")
    limit: int = Field(..., description="Number of results per page")
    offset: int = Field(..., description="Number of results skipped")
    has_more: bool = Field(..., description="Whether there are more results available")

class ClientValidationResponse(BaseModel):
    """Schema for client validation response"""
    valid: bool = Field(..., description="Whether the client data is valid")
    errors: list[str] = Field(default_factory=list, description="List of validation errors")
    formatted_data: Optional[dict] = Field(None, description="Formatted client data")

class TaxIDFormatResponse(BaseModel):
    """Schema for tax ID formatting response"""
    valid: bool = Field(..., description="Whether the tax ID is valid")
    original: str = Field(..., description="Original tax ID input")
    formatted_tax_id: Optional[str] = Field(None, description="Formatted tax ID for database")
    display_format: Optional[str] = Field(None, description="Tax ID formatted for display")
    message: Optional[str] = Field(None, description="Processing message")
    errors: list[str] = Field(default_factory=list, description="List of validation errors")

def format_tax_id_for_display(tax_id: str) -> str:
    """
    Format Jamaican tax ID for display (convert from 114103496000 to 114-103-496)
    
    Args:
        tax_id (str): Tax ID in database format (13 digits)
    
    Returns:
        str: Formatted tax ID for display
    """
    if not tax_id:
        return tax_id
    
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

def validate_and_format_tax_id(tax_id: str) -> TaxIDFormatResponse:
    """
    Validate and format Jamaican tax ID
    
    Args:
        tax_id (str): Tax ID to validate and format
    
    Returns:
        TaxIDFormatResponse: Validation result with formatted tax ID
    """
    if not tax_id:
        return TaxIDFormatResponse(
            valid=True,
            original=tax_id,
            formatted_tax_id=None,
            display_format=None,
            message="No tax ID provided"
        )
    
    # Remove all non-digit characters
    cleaned_tax_id = re.sub(r'[^\d]', '', tax_id)
    
    # Check if it's a valid Jamaican TRN format
    if len(cleaned_tax_id) == 9:
        # Add four zeros to make it 13 digits
        formatted_tax_id = cleaned_tax_id + "0000"
        display_format = format_tax_id_for_display(formatted_tax_id)
        
        return TaxIDFormatResponse(
            valid=True,
            original=tax_id,
            formatted_tax_id=formatted_tax_id,
            display_format=display_format,
            message=f"TRN formatted from {tax_id} to {formatted_tax_id}"
        )
    elif len(cleaned_tax_id) == 13:
        # Already in correct format
        display_format = format_tax_id_for_display(cleaned_tax_id)
        
        return TaxIDFormatResponse(
            valid=True,
            original=tax_id,
            formatted_tax_id=cleaned_tax_id,
            display_format=display_format,
            message=f"TRN already in correct format: {cleaned_tax_id}"
        )
    else:
        return TaxIDFormatResponse(
            valid=False,
            original=tax_id,
            formatted_tax_id=None,
            display_format=None,
            errors=[f"Invalid Jamaican TRN format. TRN must be exactly 13 digits. Expected 9 digits (e.g., 114103496) or 13 digits (e.g., 1141034960000), got {len(cleaned_tax_id)} digits: {cleaned_tax_id}"]
        ) 