from fastapi import APIRouter, BackgroundTasks
from typing import List
from app.pipelines.signals.pipeline import SignalsPipeline
import structlog

logger = structlog.get_logger()
router = APIRouter()

@router.post("/collect/{ticker}")
async def trigger_signal_collection(ticker: str, background_tasks: BackgroundTasks):
    """
    Trigger external signal collection (Jobs, Patents, Tech) for a specific ticker.
    """
    async def task_wrapper(tickers: List[str]):
        pipeline = SignalsPipeline()
        await pipeline.run(tickers)
        
    background_tasks.add_task(task_wrapper, [ticker])
    return {"status": "accepted", "message": f"Signal collection started for {ticker}"}

@router.post("/collect-batch")
async def trigger_signal_batch(tickers: List[str], background_tasks: BackgroundTasks):
    async def task_wrapper(tickers: List[str]):
        pipeline = SignalsPipeline()
        await pipeline.run(tickers)
        
    background_tasks.add_task(task_wrapper, tickers)
    return {"status": "accepted", "message": "Batch signal collection started"}
