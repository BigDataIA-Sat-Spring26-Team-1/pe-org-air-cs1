from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional
from uuid import UUID, uuid4

from app.models.company import CompanyCreate, CompanyResponse
from app.models.common import PaginatedResponse
from app.routers.routers_utils import create_paginated_response, get_offset
from app.services.snowflake import db
from app.services.redis_cache import cache

router = APIRouter()

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(company: CompanyCreate):
    new_id = uuid4()
    company_data = company.model_dump()
    company_data['id'] = new_id
    
    await db.create_company(company_data)
    
    # Invalidate list cache
    cache.delete_pattern("companies:list:*")
    
    # Fetch back to get timestamps
    created_company = await db.fetch_company(str(new_id))
    if not created_company:
        raise HTTPException(status_code=500, detail="Failed to retrieve created company")
        
    return created_company

@router.get("/", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    industry_id: Optional[UUID] = None
):
    # Cache key based on params
    cache_key = f"companies:list:{page}:{page_size}:{industry_id}"
    cached = cache.get(cache_key, PaginatedResponse[CompanyResponse])
    if cached:
        return cached

    offset = get_offset(page, page_size)
    companies = await db.fetch_companies(limit=page_size, offset=offset, industry_id=str(industry_id) if industry_id else None)
    total_count = await db.count_companies(industry_id=str(industry_id) if industry_id else None)
    
    response = create_paginated_response(
        items=[CompanyResponse.model_validate(c) for c in companies],
        total=total_count,
        page=page,
        page_size=page_size
    )
    
    # Cache for 60 seconds
    cache.set(cache_key, response, ttl_seconds=60)
    
    return response

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: UUID):
    cache_key = f"company:{company_id}"
    
    # Try cache first
    cached = cache.get(cache_key, CompanyResponse)
    if cached:
        return cached
    
    # Fetch from DB
    company = await db.fetch_company(str(company_id))
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company_model = CompanyResponse.model_validate(company)
    
    # Cache for 5 minutes
    cache.set(cache_key, company_model, ttl_seconds=300)
    
    return company_model

@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: UUID, company_update: CompanyCreate):
    # Check existence
    existing = await db.fetch_company(str(company_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = company_update.model_dump()
    await db.update_company(str(company_id), update_data)
    
    # Invalidate caches
    cache.delete(f"company:{company_id}")
    cache.delete_pattern("companies:list:*")
    
    updated = await db.fetch_company(str(company_id))
    return updated

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: UUID):
    # Check existence
    existing = await db.fetch_company(str(company_id))
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
        
    await db.delete_company(str(company_id))
    
    # Invalidate caches
    cache.delete(f"company:{company_id}")
    cache.delete_pattern("companies:list:*")