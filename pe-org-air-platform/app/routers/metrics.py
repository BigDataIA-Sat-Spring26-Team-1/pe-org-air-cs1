from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from app.services.snowflake import db
from app.services.redis_cache import cache

router = APIRouter()

@router.get("/industry-distribution", 
            summary="Get industry distribution",
            description="Returns the number of companies in each industry.")
async def get_industry_distribution():
    cache_key = "metrics:industry_distribution"
    cached = cache.get(cache_key, List[Dict[str, Any]])
    if cached:
        return cached
        
    data = await db.fetch_industry_distribution()
    cache.set(cache_key, data, ttl_seconds=300)
    return data

@router.get("/company-stats", 
            summary="Get company stats",
            description="Returns aggregated metrics (signals, evidence, filings) for companies.")
async def get_company_stats(company_id: Optional[str] = Query(None)):
    cache_key = f"metrics:company_stats:{company_id or 'all'}"
    cached = cache.get(cache_key, List[Dict[str, Any]])
    if cached:
        return cached
        
    data = await db.fetch_company_metrics(company_id)
    cache.set(cache_key, data, ttl_seconds=300)
    return data

@router.get("/signal-distribution", 
            summary="Get signal distribution",
            description="Returns distribution of signals across categories.")
async def get_signal_distribution(company_id: Optional[str] = Query(None)):
    cache_key = f"metrics:signal_distribution:{company_id or 'all'}"
    cached = cache.get(cache_key, List[Dict[str, Any]])
    if cached:
        return cached
        
    data = await db.fetch_signal_category_distribution(company_id)
    cache.set(cache_key, data, ttl_seconds=300)
    return data

@router.get("/summary", 
            summary="Get global summary metrics",
            description="Returns high-level totals across the platform.")
async def get_global_summary():
    cache_key = "metrics:summary"
    cached = cache.get(cache_key, Dict[str, Any])
    if cached:
        return cached
        
    # We can aggregate from the company metrics
    company_metrics = await db.fetch_company_metrics()
    
    summary = {
        "total_companies": len(company_metrics),
        "total_signals": sum(c['signals'] for c in company_metrics),
        "total_evidence": sum(c['evidence'] for c in company_metrics),
        "total_filings": sum(c['filings'] for c in company_metrics)
    }
    
    cache.set(cache_key, summary, ttl_seconds=300)
    return summary
