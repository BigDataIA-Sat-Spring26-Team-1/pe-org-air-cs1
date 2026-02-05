from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List
from app.pipelines.sec.pipeline import SecPipeline
import structlog

logger = structlog.get_logger()
router = APIRouter()

@router.post("/collect/{ticker}")
async def trigger_collection(ticker: str, background_tasks: BackgroundTasks):
    """
    Trigger SEC collection for a specific ticker in the background.
    """
    async def task_wrapper(tickers: List[str]):
        pipeline = SecPipeline()
        await pipeline.run(tickers)
        
    background_tasks.add_task(task_wrapper, [ticker])
    return {"status": "accepted", "message": f"Collection started for {ticker}"}

@router.post("/collect-batch")
async def trigger_batch_collection(tickers: List[str], background_tasks: BackgroundTasks):
    """
    Trigger batch collection.
    """
    async def task_wrapper(tickers: List[str]):
        pipeline = SecPipeline()
        await pipeline.run(tickers)
        
    background_tasks.add_task(task_wrapper, tickers)
    return {"status": "accepted", "message": f"Collection started for {len(tickers)} companies"}
