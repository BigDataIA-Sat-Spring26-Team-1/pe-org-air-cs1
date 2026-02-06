import logging
import uuid
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Any, List

from app.pipelines.external_signals.orchestrator import MasterPipeline
from app.pipelines.sec.pipeline import SecPipeline
from app.services.snowflake import db
from app.services.redis_cache import cache

logger = logging.getLogger(__name__)

class BackfillService:
    def __init__(self):
        # Only store static metadata here, not IDs
        self._target_companies = {
            "CAT": {"name": "Caterpillar Inc.", "sector": "Manufacturing"},
            "DE": {"name": "Deere & Company", "sector": "Manufacturing"},
            "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare"},
            "HCA": {"name": "HCA Healthcare", "sector": "Healthcare"},
            "ADP": {"name": "Automatic Data Processing", "sector": "Services"},
            "PAYX": {"name": "Paychex Inc.", "sector": "Services"},
            "WMT": {"name": "Walmart Inc.", "sector": "Retail"},
            "TGT": {"name": "Target Corporation", "sector": "Retail"},
            "JPM": {"name": "JPMorgan Chase", "sector": "Financial"},
            "GS": {"name": "Goldman Sachs", "sector": "Financial"},
        }
        self._stats = {
            "companies": 0,
            "documents": 0,
            "signals": 0,
            "errors": 0,
            "status": "idle",
            "last_run": None,
            "duration_seconds": 0
        }

    @property
    def stats(self) -> Dict[str, Any]:
        return self._stats

    @property
    def target_companies(self) -> List[str]:
        return list(self._target_companies.keys())

    def is_running(self) -> bool:
        return self._stats["status"] == "running"

    async def run_backfill(self):
        self._stats["status"] = "running"
        self._stats["companies"] = 0
        self._stats["signals"] = 0
        self._stats["documents"] = 0
        self._stats["errors"] = 0
        self._stats["last_run"] = datetime.utcnow().isoformat()
        start_time = datetime.utcnow()
        
        sec_pipeline = SecPipeline()
        signal_pipeline = MasterPipeline()
        
        # Pre-fetch industry map
        industry_map = {}
        all_industries = await db.fetch_industries()
        for ind in all_industries:
            industry_map[ind['name']] = ind['id']
        
        tickers = list(self._target_companies.keys())
        batch_size = 2 # Process 2 companies (4 parallel pipelines) at a time

        async def _process_company_full(ticker: str):
            """Worker to run SEC + Signals for one company in parallel."""
            info = self._target_companies[ticker]
            try:
                # 1. Resolve Industry ID & Ensure Company Record
                sector = info['sector']
                industry_id = industry_map.get(sector) or (await db.fetch_industry_by_name(sector) or {}).get('id')
                if not industry_id and all_industries:
                    industry_id = all_industries[0]['id']

                existing = await db.fetch_company_by_ticker(ticker)
                company_id = existing['id'] if existing else str(uuid.uuid4())
                if not existing:
                    await db.create_company({
                        "id": company_id, "name": info['name'], "ticker": ticker,
                        "industry_id": industry_id, "position_factor": 0.5 
                    })

                # 2. Define independent workers
                async def _run_sec():
                    res = await sec_pipeline.run([ticker], limit=5)
                    processed_docs = res.get("processed", 0)
                    self._stats["documents"] += processed_docs
                    logger.info(f"==> FINISHED SEC for {ticker}: {processed_docs} documents")
                    return res

                async def _run_signals():
                    res = await signal_pipeline.run(info["name"], ticker, company_id=company_id)
                    logger.info(f"==> SAVING Signals for {ticker}...")
                    
                    await db.upsert_company_signal_summary(res['summary'])
                    
                    signals_to_save = []
                    for s in res['signals']:
                        if not s.get('signal_hash'):
                            hash_input = f"{s['company_id']}{s['source']}{s.get('raw_value', '')}"
                            s['signal_hash'] = hashlib.sha256(hash_input.encode()).hexdigest()
                        signals_to_save.append(s)
                    
                    if signals_to_save:
                        await db.create_external_signals_bulk(signals_to_save)
                    if res.get('evidence'):
                        await db.create_signal_evidence_bulk(res['evidence'])
                    
                    self._stats["signals"] += len(signals_to_save)
                    logger.info(f"==> FINISHED Signals for {ticker}: {len(signals_to_save)} added")
                    return res

                # 3. Trigger both and wait for completion
                logger.info(f"==> STARTING Pipelines for {ticker} (SEC + Signals)")
                await asyncio.gather(_run_sec(), _run_signals())
                
                # 4. Finalize Company Stats
                self._stats["companies"] += 1
                cache.delete(f"signals:summary:{company_id}")
                cache.delete_pattern(f"signals:list:{company_id}:*")
                
            except Exception as e:
                logger.error(f"Failed to process {ticker}: {e}", exc_info=True)
                self._stats["errors"] += 1

        # Execution Loop
        for i in range(0, len(tickers), batch_size):
            batch_tickers = tickers[i : i + batch_size]
            logger.info(f"Processing batch concurrently: {batch_tickers}")
            
            tasks = [_process_company_full(t) for t in batch_tickers]
            await asyncio.gather(*tasks)
                
            # Small cooldown between batches
            await asyncio.sleep(1)

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        self._stats["duration_seconds"] = round(duration, 2)
        self._stats["status"] = "completed"

backfill_service = BackfillService()
