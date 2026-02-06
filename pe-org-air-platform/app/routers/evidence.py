from fastapi import APIRouter, BackgroundTasks
from app.services.backfill import backfill_service

router = APIRouter()

@router.post("/backfill", status_code=202)
async def backfill_evidence_endpoint(background_tasks: BackgroundTasks):
    """Backfill evidence for all 10 target companies"""
    if backfill_service.is_running():
        return {
            "message": "Backfill already in progress", 
            "status": backfill_service.stats["status"]
        }
        
    background_tasks.add_task(backfill_service.run_backfill)
    return {
        "message": "Backfill started for 10 companies", 
        "status": "started",
        "targets": backfill_service.target_companies
    }

@router.get("/stats")
async def get_evidence_stats():
    """Get evidence collection statistics"""
    return backfill_service.stats
