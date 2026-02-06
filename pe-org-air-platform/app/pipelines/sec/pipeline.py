import asyncio
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List
import structlog

from app.pipelines.sec.downloader import SecDownloader
from app.pipelines.sec.parser import SecParser
from app.pipelines.sec.chunker import SemanticChunker
from app.models.registry import DocumentRegistry
from app.services.s3_storage import aws_service
from app.services.snowflake import db

logger = structlog.get_logger()


class SecPipeline:
    def __init__(self, download_dir: str = "./data/sec_downloads"):
        self.download_dir = download_dir
        self.downloader = SecDownloader(
            download_dir=download_dir,
            email="admin@pe-orgair.com",
            company="PE OrgAIR"
        )
        self.parser = SecParser()
        self.chunker = SemanticChunker()
        self.registry = DocumentRegistry()

    async def run_old(self, tickers: List[str], limit: int = 2):
        logger.info("pipeline_start", tickers=tickers)

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

    def _process_filing_sync(self, meta):
        """
        Synchronous processing method to be run in a thread pool.
        Includes File I/O, S3 upload, Parsing (BS4/PDF), and Chunking.
        """
        results_chunk = {"processed": 0, "skipped": 0, "errors": 0, "doc_data": None}
        
        try:
            local_path = (
                Path(self.download_dir)
                / "sec-edgar-filings"
                / meta.cik
                / meta.filing_type
                / meta.accession_number
            )

            file_candidates = list(local_path.glob("*.*"))
            target_file = next(
                (f for f in file_candidates if f.suffix in ['.html', '.pdf', '.txt']),
                None
            )

            if not target_file:
                logger.warning("file_not_found", path=str(local_path))
                return results_chunk

            s3_raw_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/{target_file.name}"
            # s3 calls are blocking (boto3)
            if aws_service.file_exists(s3_raw_key):
                logger.debug("raw_file_exists_skipping_upload", key=s3_raw_key)
            else:
                aws_service.upload_file(str(target_file), s3_raw_key)

            # Parsing is CPU blocking
            sections = self.parser.parse(target_file, form_type=meta.filing_type)
            if not sections:
                logger.warning("no_sections_extracted", file=meta.accession_number)
                return results_chunk

            content_str = json.dumps(sections, sort_keys=True)
            content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

            if self.registry.is_processed(content_hash):
                logger.info("duplicate_skipped", hash=content_hash)
                results_chunk["skipped"] = 1
                return results_chunk

            s3_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/parsed.json"
            aws_service.upload_bytes(content_str.encode("utf-8"), s3_key, "application/json")

            all_chunks = []
            chunk_index_counter = 0

            # Chunking is CPU blocking
            for section_name, text in sections.items():
                chunks = self.chunker.split_text(text)
                for chunk_text in chunks:
                    all_chunks.append({
                        "index": chunk_index_counter,
                        "section": section_name,
                        "text": chunk_text,
                        "tokens": len(chunk_text.split())
                    })
                    chunk_index_counter += 1

            # Prepare data for async DB insertion
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
            logger.error("processing_error", accession=meta.accession_number, error=str(e))
            results_chunk["errors"] = 1
            return results_chunk

    async def run(self, tickers: List[str], limit: int = 2):
        logger.info("pipeline_start", tickers=tickers)

        # 1. Download (Async/Threaded inside)
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

        loop = asyncio.get_event_loop()
        
        # 2. Process each filling in thread pool to avoid blocking event loop
        # (Parsing and S3 uploads are synchronous/blocking)
        for meta in metadatas:
            # Run sync processing in thread
            res_chunk = await loop.run_in_executor(None, self._process_filing_sync, meta)
            
            results["processed"] += res_chunk["processed"]
            results["skipped"] += res_chunk["skipped"]
            results["errors"] += res_chunk["errors"]
            
            doc_data = res_chunk.get("doc_data")
            
            if doc_data:
                # 3. DB writes are async, so we do them here in the main loop
                await self._save_to_db(doc_data)

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
