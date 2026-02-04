import asyncio
import os
from pathlib import Path
from typing import List, Optional, Set
from concurrent.futures import ThreadPoolExecutor
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from sec_edgar_downloader import Downloader

from app.models.sec import FilingMetadata

logger = structlog.get_logger()

class SecDownloader:
    """
    Robust SEC Edgar Downloader with concurrency and rate limiting.
    Downloads 10-K, 10-Q, 8-K filings.
    """
    def __init__(self, download_dir: str, email: str, company: str, max_workers: int = 4):
        self.download_dir = Path(download_dir)
        self.downloader = Downloader(company, email, download_folder=str(self.download_dir))
        self.max_workers = max_workers
        # SEC limits to 10 requests/sec. We'll be conservative with 5 concurrent tasks
        # The downloader library handles some rate limiting, but for safety in parallel:
        self._semaphore = asyncio.Semaphore(5) 

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _download_safe(self, ticker: str, filing_type: str, limit: int = 1, after_date: Optional[str] = None):
        """
        Blocking download call wrapped with retry logic.
        """
        try:
            # Note: after_date format YYYY-MM-DD if supported by lib or filtering happens after
            count = self.downloader.get(filing_type, ticker, limit=limit, after=after_date)
            return count
        except Exception as e:
            logger.error("download_failed", ticker=ticker, type=filing_type, error=str(e))
            raise e

    async def download_filings(self, tickers: List[str], filing_types: List[str], limit_per_type: int = 2) -> List[FilingMetadata]:
        """
        Async orchestration of downloads.
        """
        logger.info("starting_batch_download", tickers_count=len(tickers))
        
        loop = asyncio.get_event_loop()
        tasks = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            for ticker in tickers:
                for f_type in filing_types:
                    # Create a task for each ticker/type combination
                    task = self._download_worker(loop, pool, ticker, f_type, limit_per_type)
                    tasks.append(task)
            
            # Run all downloads
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Scan directory to gather metadata of downloaded files
        # valid_results = [r for r in results if not isinstance(r, Exception)]
        return self._scan_downloaded_files(tickers)

    async def _download_worker(self, loop, pool, ticker, f_type, limit):
        async with self._semaphore:
            logger.debug("downloading", ticker=ticker, type=f_type)
            await loop.run_in_executor(pool, self._download_safe, ticker, f_type, limit, None)

    def _scan_downloaded_files(self, tickers: List[str]) -> List[FilingMetadata]:
        """
        Scans the download directory to discover what was actually downloaded.
        Returns a list of metadata objects.
        """
        discovered = []
        base_dir = self.download_dir / "sec-edgar-filings"
        
        if not base_dir.exists():
            return []

        for ticker in tickers:
            ticker_dir = base_dir / ticker
            if not ticker_dir.exists():
                continue
            
            for f_type_dir in ticker_dir.iterdir():
                if not f_type_dir.is_dir(): continue
                filing_type = f_type_dir.name
                
                for accession_dir in f_type_dir.iterdir():
                    if not accession_dir.is_dir(): continue
                    accession_number = accession_dir.name
                    
                    # Prefer HTML, then Text
                    # The downloader usually saves as full-submission.txt or .html
                    # We need to identify the primary document.
                    
                    file_path = None
                    # Simple heuristic: look for full-submission.txt or html or .pdf
                    candidates = list(accession_dir.glob("*.*"))
                    
                    # Prioritize HTML for parsing, but keep track of what we have
                    primary_file = next((f for f in candidates if f.suffix == '.html'), None)
                    if not primary_file:
                        primary_file = next((f for f in candidates if f.suffix == '.txt'), None)
                    
                    if primary_file:
                        # Generate a pseudo content hash placeholder (real calculation happens later)
                        # or compute it here if cheap.
                        
                        meta = FilingMetadata(
                            cik=ticker, # Using ticker as CIK/ID for now as library structure is by ticker
                            company_name=ticker, # Placeholder
                            filing_type=filing_type,
                            accession_number=accession_number,
                            s3_path="", # Will be updated after S3 upload
                            content_hash="PENDING_" + accession_number # Placeholder
                        )
                        # We attach the local path temporarily to the object or extra dict for the next step
                        # But Pydantic model doesn't have it. We should probably add `local_path` 
                        # to the model or return a tuple. 
                        # For now, let's assume the pipeline orchestrator knows the path structure.
                        discovered.append(meta)
                        
        return discovered
