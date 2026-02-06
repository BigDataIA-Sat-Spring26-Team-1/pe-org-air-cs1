from fastapi import APIRouter, BackgroundTasks
from app.services.backfill import backfill_service

router = APIRouter()

@router.post("/backfill", 
             status_code=202,
             summary="Run full backfill",
             description="Starts a background process to collect external evidence (SEC data, signals) for all target companies.")
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

@router.get("/stats",
            summary="Get backfill stats",
            description="Retrieve progress statistics and status of the current or most recent backfill operation.")
async def get_evidence_stats():
    """Get evidence collection statistics"""
    stats = backfill_service.stats.copy()
    
    # If idle, fetch actual historical stats from DB to show on dashboard
    if stats["status"] == "idle" or stats["status"] == "completed":
        from app.services.snowflake import db
        company_metrics = await db.fetch_company_metrics()
        stats["companies"] = len(company_metrics)
        stats["signals"] = sum(c['signals'] for c in company_metrics)
        stats["documents"] = sum(c['filings'] for c in company_metrics)
    
    return stats
