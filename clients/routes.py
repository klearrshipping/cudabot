# clients/routes.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from .models import (
    create_client_record, 
    get_client_by_id, 
    get_all_clients,
    update_client_record,
    delete_client_record,
    search_clients_by_company,
    get_client_by_email,
    get_clients_by_tax_id,
    get_recent_clients,
    count_total_clients,
    validate_client_data
)
from .schemas import (
    ClientCreate, 
    ClientUpdate, 
    ClientResponse, 
    ClientSearch, 
    ClientListResponse,
    ClientValidationResponse,
    TaxIDFormatResponse,
    validate_and_format_tax_id,
    format_tax_id_for_display
)

router = APIRouter(prefix="/clients", tags=["clients"])

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(client_data: ClientCreate):
    """
    Create a new client record
    
    - **company_name**: Required company name
    - **contact_email**: Required valid email address
    - **phone_number**: Optional phone number
    - **address**: Optional business address
    - **tax_id**: Optional Jamaican tax ID (auto-formatted)
    """
    try:
        # Validate client data using schemas
        validation_result = validate_client_data(client_data.dict())
        
        if not validation_result['valid']:
            raise HTTPException(
                status_code=400, 
                detail=f"Validation failed: {', '.join(validation_result['errors'])}"
            )
        
        # Create client record
        result = create_client_record(validation_result['formatted_data'])
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create client record")
        
        return ClientResponse(**result[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int):
    """
    Get a specific client by ID
    
    - **client_id**: Client's unique identifier
    """
    try:
        result = get_client_by_id(client_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Client with ID {client_id} not found")
        
        return ClientResponse(**result[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/", response_model=ClientListResponse)
async def list_clients(
    limit: int = Query(10, ge=1, le=100, description="Number of clients to return"),
    offset: int = Query(0, ge=0, description="Number of clients to skip"),
    company_name: Optional[str] = Query(None, description="Filter by company name (partial match)"),
    contact_email: Optional[str] = Query(None, description="Filter by exact email address"),
    tax_id: Optional[str] = Query(None, description="Filter by tax ID")
):
    """
    Get a paginated list of clients with optional filtering
    
    - **limit**: Maximum number of clients to return (1-100)
    - **offset**: Number of clients to skip for pagination
    - **company_name**: Filter by company name (partial match)
    - **contact_email**: Filter by exact email address
    - **tax_id**: Filter by tax ID (auto-formatted)
    """
    try:
        # Build search parameters
        search_params = {}
        if company_name:
            search_params['company_name'] = company_name
        if contact_email:
            search_params['contact_email'] = contact_email
        if tax_id:
            # Validate and format tax ID for search
            tax_validation = validate_and_format_tax_id(tax_id)
            if not tax_validation.valid:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid tax ID format: {', '.join(tax_validation.errors)}"
                )
            search_params['tax_id'] = tax_validation.formatted_tax_id
        
        # Get clients with search and pagination
        if search_params:
            # Use search functionality
            clients = search_clients_by_company(search_params.get('company_name', ''))
            # Filter by other parameters
            if search_params.get('contact_email'):
                clients = [c for c in clients if c.get('contact_email') == search_params['contact_email']]
            if search_params.get('tax_id'):
                clients = [c for c in clients if c.get('tax_id') == search_params['tax_id']]
        else:
            # Get all clients
            clients = get_all_clients()
        
        # Apply pagination
        total_count = len(clients)
        paginated_clients = clients[offset:offset + limit]
        
        # Convert to response models
        client_responses = [ClientResponse(**client) for client in paginated_clients]
        
        return ClientListResponse(
            clients=client_responses,
            total_count=total_count,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(client_id: int, client_data: ClientUpdate):
    """
    Update an existing client record
    
    - **client_id**: Client's unique identifier
    - **client_data**: Updated client information (all fields optional)
    """
    try:
        # Check if client exists
        existing_client = get_client_by_id(client_id)
        if not existing_client:
            raise HTTPException(status_code=404, detail=f"Client with ID {client_id} not found")
        
        # Validate update data
        update_dict = client_data.dict(exclude_unset=True)
        if update_dict:
            validation_result = validate_client_data(update_dict)
            
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Validation failed: {', '.join(validation_result['errors'])}"
                )
            
            # Update client record
            result = update_client_record(client_id, validation_result['formatted_data'])
            
            if not result:
                raise HTTPException(status_code=500, detail="Failed to update client record")
            
            return ClientResponse(**result[0])
        else:
            # No fields to update
            return ClientResponse(**existing_client[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int):
    """
    Delete a client record
    
    - **client_id**: Client's unique identifier
    """
    try:
        # Check if client exists
        existing_client = get_client_by_id(client_id)
        if not existing_client:
            raise HTTPException(status_code=404, detail=f"Client with ID {client_id} not found")
        
        # Delete client record
        result = delete_client_record(client_id)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to delete client record")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search/company", response_model=List[ClientResponse])
async def search_by_company(company_name: str = Query(..., description="Company name to search for")):
    """
    Search clients by company name (partial match)
    
    - **company_name**: Company name to search for
    """
    try:
        results = search_clients_by_company(company_name)
        return [ClientResponse(**client) for client in results]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search/email/{email}", response_model=ClientResponse)
async def get_by_email(email: str):
    """
    Get client by email address
    
    - **email**: Client's email address
    """
    try:
        result = get_client_by_email(email)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Client with email {email} not found")
        
        return ClientResponse(**result[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/search/tax-id/{tax_id}", response_model=List[ClientResponse])
async def get_by_tax_id(tax_id: str):
    """
    Get clients by tax ID
    
    - **tax_id**: Jamaican tax ID (auto-formatted)
    """
    try:
        # Validate and format tax ID
        tax_validation = validate_and_format_tax_id(tax_id)
        if not tax_validation.valid:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid tax ID format: {', '.join(tax_validation.errors)}"
            )
        
        results = get_clients_by_tax_id(tax_validation.formatted_tax_id)
        return [ClientResponse(**client) for client in results]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/recent/{limit}", response_model=List[ClientResponse])
async def get_recent_clients(limit: int = Query(10, ge=1, le=50, description="Number of recent clients to return")):
    """
    Get recently created clients
    
    - **limit**: Number of recent clients to return (1-50)
    """
    try:
        results = get_recent_clients(limit)
        return [ClientResponse(**client) for client in results]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/stats/count")
async def get_client_count():
    """
    Get total number of clients
    """
    try:
        count = count_total_clients()
        return {"total_clients": count}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/validate", response_model=ClientValidationResponse)
async def validate_client(client_data: ClientCreate):
    """
    Validate client data without saving to database
    
    - **client_data**: Client information to validate
    """
    try:
        validation_result = validate_client_data(client_data.dict())
        return ClientValidationResponse(**validation_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/validate/tax-id", response_model=TaxIDFormatResponse)
async def validate_tax_id(tax_id: str):
    """
    Validate and format Jamaican tax ID
    
    - **tax_id**: Tax ID to validate and format
    """
    try:
        return validate_and_format_tax_id(tax_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/format/tax-id/{tax_id}")
async def format_tax_id_display(tax_id: str):
    """
    Format tax ID for display
    
    - **tax_id**: Tax ID to format for display
    """
    try:
        display_format = format_tax_id_for_display(tax_id)
        return {"original": tax_id, "display_format": display_format}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 