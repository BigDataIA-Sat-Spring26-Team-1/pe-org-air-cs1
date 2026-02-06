import asyncio
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List
import structlog
import pdfkit
from concurrent.futures import ProcessPoolExecutor

from app.pipelines.sec.downloader import SecDownloader
from app.pipelines.sec.parser import SecParser
from app.pipelines.sec.chunker import SemanticChunker
from app.models.registry import DocumentRegistry
from app.services.s3_storage import AWSService
from app.services.snowflake import db
from app.services.redis_cache import cache

logger = structlog.get_logger()

def process_filing_worker(meta, download_dir: str):
    """
    Process filing in a separate process (CPU-bound).
    Must be a standalone function to be picklable.
    """
    registry = DocumentRegistry()
    parser = SecParser()
    chunker = SemanticChunker()
    # Use local S3 client for process safety
    aws = AWSService()
    
    # We must re-create logger context if needed, but simplistic is fine.
    
    results_chunk = {"processed": 0, "skipped": 0, "errors": 0, "doc_data": None}
    
    try:
        local_path = (
            Path(download_dir)
            / "sec-edgar-filings"
            / meta.cik
            / meta.filing_type
            / meta.accession_number
        )

        file_candidates = list(local_path.glob("*.*"))
        target_file = next(
            (f for f in file_candidates if f.suffix.lower() in ['.html', '.pdf', '.txt']),
            None
        )

        if not target_file:
            return results_chunk

        # 1. Upload Raw File
        s3_raw_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/{target_file.name}"
        
        try:
            if not aws.file_exists(s3_raw_key):
                aws.upload_file(str(target_file), s3_raw_key)
        except Exception:
            pass # creating race conditions or connection issues in process pool

        # 2. Auto-generate PDF for HTML/TXT filings
        if target_file.suffix.lower() in ['.html', '.htm', '.txt']:
            try:
                pdf_filename = target_file.stem + ".pdf"
                local_pdf_path = target_file.parent / pdf_filename
                s3_pdf_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/{pdf_filename}"
                
                # 2. Extract & Auto-generate PDF
                if target_file.suffix.lower() in ['.html', '.htm', '.txt']:
                    temp_html_path = target_file.with_name(f"{target_file.stem}_clean.html")
                    
                    try:
                        # Read content
                        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                        # Logic to extract HTML from full-submission.txt
                        html_content = content
                        if "<SEC-DOCUMENT>" in content or "<DOCUMENT>" in content:
                            # Try to find the specific document type matching the filing
                            # e.g. <TYPE>10-K...<TEXT>...
                            ftype = re.escape(meta.filing_type)
                            # Look for Document with matching TYPE, capture text inside <TEXT> tags
                            pattern = re.compile(r'<DOCUMENT>.*?>\s*<TYPE>.*?' + ftype + r'.*?<TEXT>(.*?)</TEXT>', re.DOTALL | re.IGNORECASE)
                            match = pattern.search(content)
                            
                            if match:
                                html_content = match.group(1).strip()
                            else:
                                # Fallback: take the first <TEXT> block found (usually the main doc)
                                match_any = re.search(r'<TEXT>(.*?)</TEXT>', content, re.DOTALL | re.IGNORECASE)
                                if match_any:
                                    html_content = match_any.group(1).strip()

                        # Ensure valid HTML structure
                        if "<html>" not in html_content.lower():
                             # Wrap plain text in <pre>
                             html_content = f"<html><body><pre>{html_content}</pre></body></html>"
                        
                        # Write clean HTML
                        with open(temp_html_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)

                        if not local_pdf_path.exists():
                            logger.info("pdf_gen_start", file=target_file.name)
                            # Convert CLEAN HTML
                            pdfkit.from_file(str(temp_html_path), str(local_pdf_path), options={
                                'quiet': '', 
                                'enable-local-file-access': ''
                            })
                            logger.info("pdf_gen_success", file=target_file.name)
                        
                        # Upload if valid
                        if local_pdf_path.exists():
                            if local_pdf_path.stat().st_size > 1024:
                                 aws.upload_file(str(local_pdf_path), s3_pdf_key)
                            else:
                                 logger.warning("pdf_gen_empty_file", file=target_file.name)
                                 local_pdf_path.unlink()

                        # Cleanup
                        if temp_html_path.exists():
                            temp_html_path.unlink()

                    except Exception as e:
                        logger.warning("pdf_gen_failed", file=target_file.name, error=str(e))
                        if temp_html_path.exists():
                            temp_html_path.unlink()
                        pass
            except Exception:
                pass

        # 3. Parse
        sections = parser.parse(target_file, form_type=meta.filing_type)
        if not sections:
            return results_chunk

        # 4. JSON Generation & Hash
        content_str = json.dumps(sections, sort_keys=True)
        content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

        if registry.is_processed(content_hash):
            results_chunk["skipped"] = 1
            return results_chunk

        # 5. Upload Parsed JSON
        s3_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/parsed.json"
        aws.upload_bytes(content_str.encode("utf-8"), s3_key, "application/json")

        # 6. Chunking
        all_chunks = []
        chunk_index_counter = 0

        for section_name, text in sections.items():
            chunks = chunker.chunk(text)
            for chunk_text in chunks:
                # TRUNCATE to avoid DB Crash. Snowflake limits can be hit.
                safe_text = chunk_text[:60000] # 60k chars safety limit
                
                all_chunks.append({
                    "section": section_name,
                    "text": safe_text, 
                    "index": chunk_index_counter,
                    "tokens": len(safe_text.split())
                })
                chunk_index_counter += 1

        doc_id = f"{meta.cik}_{meta.accession_number}"
        
        results_chunk["processed"] = 1
        results_chunk["doc_data"] = {
            "doc_id": doc_id,
            "meta": meta,
            "s3_key": s3_key,
            "content_hash": content_hash,
            "all_chunks": all_chunks
        }
        return results_chunk

    except Exception as e:
        results_chunk["errors"] = 1
        results_chunk["error_msg"] = str(e)
        return results_chunk


class SecPipeline:
    def __init__(self, download_dir: str = "./data/sec_downloads"):
        self.download_dir = download_dir
        self.downloader = SecDownloader(
            download_dir=download_dir,
            email="admin@pe-orgair.com",
            company="PE OrgAIR"
        )
        self.registry = DocumentRegistry()
        # Use ProcessPoolExecutor for CPU-bound tasks (Parsing, PDF Gen)
        # Max workers = 4 to match likely vCPU count and avoid OOM
        self.pool = ProcessPoolExecutor(max_workers=4)

    async def run(self, tickers: List[str], limit: int = 2):
        logger.info("pipeline_start", tickers=tickers)

        # 1. Download filings (I/O bound, uses asyncio internally)
        metadatas = await self.downloader.download_filings(
            tickers=tickers,
            filing_types=["10-K", "10-Q", "8-K", "DEF 14A"],
            limit_per_type=limit
        )

        logger.info("download_complete", count=len(metadatas))

        results = {
            "processed": 0,
            "skipped": 0,
            "errors": 0
        }

        if not metadatas:
            return results

        loop = asyncio.get_event_loop()
        
        # 2. Schedule Processing in Process Pool
        # We process in batches to avoid event loop congestion if many files
        
        process_tasks = []
        for meta in metadatas:
            # Offload to separate process
            # Note: meta must be picklable (it is a Pydantic model usually, or simple object)
            task = loop.run_in_executor(
                self.pool, 
                process_filing_worker, 
                meta, 
                self.download_dir
            )
            process_tasks.append(task)

        # Wait for all
        batch_results = await asyncio.gather(*process_tasks, return_exceptions=True)

        # Refresh DB connection to avoid SSL/Timeout errors after long processing
        await db.close()

        # 3. Aggregate results and Save to DB (I/O bound, main process)
        for res in batch_results:
            if isinstance(res, Exception):
                logger.error("task_execution_failed", error=str(res))
                results["errors"] += 1
                continue
            
            # Check for internal error in worker
            if res.get("errors"):
                logger.error("worker_processing_error", error=res.get("error_msg"))
                results["errors"] += 1
                continue

            doc_data = res.get("doc_data")
            if doc_data:
                # Save to DB (async, main process)
                try:
                    await self._save_to_db(doc_data)
                    results["processed"] += 1
                except Exception as e:
                    logger.error("db_save_failed", error=str(e))
                    results["errors"] += 1
            elif res.get("skipped"):
                results["skipped"] += 1
            else:
                 # No doc data, no error, no skipped? (e.g. file not found)
                 pass

        logger.info("pipeline_complete", results=results)
        return results

    async def _save_to_db(self, doc_data):
        doc_id = doc_data["doc_id"]
        content_hash = doc_data["content_hash"]
        all_chunks = doc_data["all_chunks"]

        # Use service helpers
        await db.create_sec_document(doc_data)

        chunk_params = []
        for ch in all_chunks:
            chunk_id = f"{doc_id}_{ch['index']}"
            chunk_params.append((
                chunk_id, doc_id, ch['index'],
                ch['section'], ch['text'], ch['tokens']
            ))

        if chunk_params:
            await db.create_sec_document_chunks_bulk(chunk_params)

        self.registry.add(content_hash)
        
        # Invalidate cache for this document so API sees latest status
        cache.delete(f"sec:doc:{doc_id}")
        # Invalidate 1st page of lists to show new doc
        cache.delete_pattern("sec:docs:*:*:50:0")

    def __del__(self):
        # Shutdown pool
        self.pool.shutdown(wait=False)
