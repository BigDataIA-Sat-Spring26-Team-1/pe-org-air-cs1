from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.pipelines.sec.pipeline import SecPipeline
from app.services.snowflake import db
from app.models.sec import (
    SecCollectRequest, 
    SecDocument, 
    SecDocumentChunk
)

logger = structlog.get_logger()
router = APIRouter()

active_tasks = set()

async def _run_pipeline(tickers: List[str], limit: int) -> None:
    for ticker in tickers:
        try:
            logger.info("pipeline_start", ticker=ticker)
            pipeline = SecPipeline()
            results = await pipeline.run(tickers=[ticker], limit=limit)
            logger.info("pipeline_complete", ticker=ticker, results=str(results))
        except Exception as e:
            logger.error("pipeline_failed", ticker=ticker, error=str(e))
        finally:
            if ticker in active_tasks:
                active_tasks.remove(ticker)


@router.post("/collect")
async def collect_documents(req: SecCollectRequest, background_tasks: BackgroundTasks):
    """
    Trigger document collection for one or more tickers.
    """
    tickers = [t.strip().upper() for t in req.tickers if t and t.strip()]
    if not tickers:
        raise HTTPException(400, "tickers list is empty")

    if req.company_name:
         await db.upsert_sec_company(req.company_name, tickers[0])

    started_tickers = []
    for t in tickers:
        if t in active_tasks:
            logger.info("task_already_running", ticker=t)
            continue
        
        active_tasks.add(t)
        started_tickers.append(t)
    
    if not started_tickers:
        return {
            "status": "ignored",
            "message": "Jobs for all tickers are already running."
        }

    background_tasks.add_task(_run_pipeline, started_tickers, req.limit)

    return {
        "status": "accepted",
        "tickers": started_tickers,
        "message": f"Collection queued for {len(started_tickers)} tickers"
    }


@router.get("", response_model=List[SecDocument])
async def list_documents(
    company: Optional[str] = Query(default=None, description="Filter by ticker or company_name"),
    filing_type: Optional[str] = Query(default=None, description="Filter by filing_type e.g. 10-K"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    List documents (filterable).
    """
    docs = await db.fetch_sec_documents(company, filing_type, limit, offset)
    return [SecDocument(**d) for d in docs]


@router.get("/{document_id}", response_model=SecDocument)
async def get_document(document_id: str):
    """Get document with metadata."""
    doc = await db.fetch_sec_document(document_id)
    if not doc:
        raise HTTPException(404, f"Document not found: {document_id}")
    return SecDocument(**doc)


@router.get("/{document_id}/chunks", response_model=List[SecDocumentChunk])
async def get_document_chunks(
    document_id: str,
    section: Optional[str] = Query(default=None, description="Filter by section_name"),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    """Get document chunks."""
    chunks = await db.fetch_sec_document_chunks(document_id, section, limit, offset)
    return [SecDocumentChunk(**c) for c in chunks]