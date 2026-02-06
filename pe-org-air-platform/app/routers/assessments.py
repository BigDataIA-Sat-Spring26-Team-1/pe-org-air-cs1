from fastapi import APIRouter, HTTPException, Query, status, Body
from typing import List, Optional
from uuid import UUID, uuid4

from app.models.assessment import AssessmentCreate, AssessmentResponse, AssessmentStatus
from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.models.common import PaginatedResponse
from app.routers.routers_utils import create_paginated_response, get_offset
from app.services.snowflake import db
from app.services.redis_cache import cache

router = APIRouter()

# Assessments Endpoints

@router.post("/assessments", 
             response_model=AssessmentResponse, 
             status_code=status.HTTP_201_CREATED,
             summary="Create assessment",
             description="Initiate a new AI Maturity assessment for a company.")
async def create_assessment(assessment: AssessmentCreate):
    new_id = uuid4()
    data = assessment.model_dump()
    data['id'] = new_id
    
    # Verify company exists
    company = await db.fetch_company(str(assessment.company_id))
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    await db.create_assessment(data)
    
    # Invalidate lists
    cache.delete_pattern("assessments:list:*")
    
    created = await db.fetch_assessment(str(new_id))
    return created

@router.get("/assessments", 
            response_model=PaginatedResponse[AssessmentResponse],
            summary="List assessments",
            description="Retrieve a paginated list of assessments, filterable by company.")
async def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = None
):
    # Cache key
    cache_key = f"assessments:list:{page}:{page_size}:{company_id}"
    cached = cache.get(cache_key, PaginatedResponse[AssessmentResponse])
    if cached:
        return cached

    offset = get_offset(page, page_size)
    items = await db.list_assessments(limit=page_size, offset=offset, company_id=str(company_id) if company_id else None)
    total = await db.count_assessments(company_id=str(company_id) if company_id else None)
    
    response = create_paginated_response(
        items=[AssessmentResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size
    )
    
    cache.set(cache_key, response, ttl_seconds=60)
    return response

@router.get("/assessments/{assessment_id}", 
            response_model=AssessmentResponse,
            summary="Get assessment",
            description="Retrieve detailed information about a specific assessment.")
async def get_assessment(assessment_id: UUID):
    cache_key = f"assessment:{assessment_id}"
    cached = cache.get(cache_key, AssessmentResponse)
    if cached:
        return cached
        
    item = await db.fetch_assessment(str(assessment_id))
    if not item:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    response = AssessmentResponse.model_validate(item)
    cache.set(cache_key, response, ttl_seconds=120) # 2 mins TTL
    return response

@router.patch("/assessments/{assessment_id}/status", 
              response_model=AssessmentResponse,
              summary="Update assessment status",
              description="Transition an assessment through different workflow states (e.g., from 'draft' to 'submitted').")
async def update_assessment_status(assessment_id: UUID, status: AssessmentStatus = Body(..., embed=True)):
    # Check existence
    item = await db.fetch_assessment(str(assessment_id))
    if not item:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Validate status transition
    current_status = AssessmentStatus(item['status'])
    new_status = status
    
    # Define valid transitions
    valid_transitions = {
        AssessmentStatus.DRAFT: [AssessmentStatus.IN_PROGRESS],
        AssessmentStatus.IN_PROGRESS: [AssessmentStatus.SUBMITTED],
        AssessmentStatus.SUBMITTED: [AssessmentStatus.APPROVED],
        AssessmentStatus.APPROVED: [AssessmentStatus.SUPERSEDED],
        AssessmentStatus.SUPERSEDED: []  # Terminal state
    }
    
    # Check if transition is valid
    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status transition from '{current_status.value}' to '{new_status.value}'"
        )
        
    await db.update_assessment_status(str(assessment_id), status.value)
    
    # Invalidate
    cache.delete(f"assessment:{assessment_id}")
    cache.delete_pattern("assessments:list:*")
    
    updated = await db.fetch_assessment(str(assessment_id))
    return updated

# Dimension Scores Endpoints

@router.post("/assessments/{assessment_id}/scores", 
             response_model=DimensionScoreResponse, 
             status_code=status.HTTP_201_CREATED,
             summary="Add dimension score",
             description="Assign a score to a specific dimension (e.g., Data Infrastructure) within an assessment.")
async def add_dimension_score(assessment_id: UUID, score: DimensionScoreCreate):
    # Verify assessment
    assessment = await db.fetch_assessment(str(assessment_id))
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    new_id = uuid4()
    data = score.model_dump()
    data['id'] = new_id
    
    # Ensure assessment_id matches path
    if str(data['assessment_id']) != str(assessment_id):
         raise HTTPException(status_code=400, detail="Assessment ID mismatch")

    try:
        await db.create_dimension_score(data)
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
             raise HTTPException(status_code=409, detail="Score for this dimension already exists")
        raise e
    
    return {**data, "id": new_id, "created_at": "2024-01-01T00:00:00Z"}
    
@router.get("/assessments/{assessment_id}/scores", 
            response_model=List[DimensionScoreResponse],
            summary="Get dimension scores",
            description="Retrieve all dimension scores for a specific assessment.")
async def get_dimension_scores(assessment_id: UUID):
    scores = await db.fetch_dimension_scores(str(assessment_id))
    return [DimensionScoreResponse.model_validate(s) for s in scores]

@router.put("/scores/{score_id}", 
            response_model=DimensionScoreResponse,
            summary="Update dimension score",
            description="Modify an existing dimension score and its associated confidence.")
async def update_dimension_score(score_id: UUID, score_update: DimensionScoreCreate):
    await db.update_dimension_score(str(score_id), score_update.score, score_update.confidence)
    
    return {**score_update.model_dump(), "id": score_id, "created_at": "2024-01-01T00:00:00Z"}
