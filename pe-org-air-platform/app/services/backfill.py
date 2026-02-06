import logging
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
            "last_run": None
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
        
        # 0. Run SEC Pipeline
        tickers = list(self._target_companies.keys())
        try:
            logger.info(f"Starting SEC collection for {len(tickers)} companies...")
            sec_pipeline = SecPipeline()
            # Using limit=5 to be safe/faster for demo
            sec_results = await sec_pipeline.run(tickers, limit=5)
            self._stats["documents"] += sec_results.get("processed", 0)
            logger.info(f"SEC collection complete. Processed: {sec_results.get('processed')}")
        except Exception as e:
            logger.error(f"SEC Pipeline failed: {e}")
            self._stats["errors"] += 1

        pipeline = MasterPipeline()
        
        # Pre-fetch industry map to avoid repeated queries
        industry_map = {}
        all_industries = await db.fetch_industries()
        for ind in all_industries:
            industry_map[ind['name']] = ind['id']
            # Also map by sector alias if needed (simple heuristic for now)
            # Assuming 'Manufacturing' -> 'Manufacturing'
        
        for ticker, info in self._target_companies.items():
            try:
                # 1. Resolve Industry ID
                sector = info['sector']
                industry_id = industry_map.get(sector)
                
                # If direct match fails, try lookup (in case map is incomplete or sector names differ slightly)
                if not industry_id:
                     ind_rec = await db.fetch_industry_by_name(sector)
                     if ind_rec:
                         industry_id = ind_rec['id']
                         industry_map[sector] = industry_id
                
                # Fallback to a default if still not found (e.g. first available)
                if not industry_id and all_industries:
                    logger.warning(f"Sector '{sector}' not found in industries. Defaulting to first available.")
                    industry_id = all_industries[0]['id']

                # 2. Ensure company exists or create it
                existing = await db.fetch_company_by_ticker(ticker)
                
                company_id = None
                if existing:
                    company_id = existing['id']
                    logger.info(f"Company {ticker} exists with ID {company_id}")
                else:
                    # Create it
                    import uuid
                    company_id = str(uuid.uuid4())
                    new_company = {
                        "id": company_id,
                        "name": info['name'],
                        "ticker": ticker,
                        "industry_id": industry_id,
                        "position_factor": 0.5 
                    }
                    await db.create_company(new_company)
                    logger.info(f"Created company {ticker} with ID {company_id}")

                # 3. Run Signal Pipeline
                logger.info(f"Running signal collection for {ticker}...")
                results = await pipeline.run(info["name"], ticker, company_id=company_id)
                
                # 4. Save Results
                # Summary
                await db.upsert_company_signal_summary(results['summary'])
                
                # Signals
                signals_to_save = []
                for s in results['signals']:
                    if not s.get('signal_hash'):
                        raw_val = s.get('raw_value', '')
                        hash_input = f"{s['company_id']}{s['source']}{raw_val}"
                        s['signal_hash'] = hashlib.sha256(hash_input.encode()).hexdigest()
                    signals_to_save.append(s)
                
                if signals_to_save:
                    await db.create_external_signals_bulk(signals_to_save)
                    
                # Evidence
                evidence_list = results.get('evidence', [])
                if evidence_list:
                    await db.create_signal_evidence_bulk(evidence_list)
                
                self._stats["companies"] += 1
                self._stats["signals"] += len(signals_to_save)
                
                # Invalidate caches
                cache.delete(f"signals:summary:{company_id}")
                cache.delete_pattern(f"signals:list:{company_id}:*")
                
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                self._stats["errors"] += 1
                
        self._stats["status"] = "completed"

backfill_service = BackfillService()
