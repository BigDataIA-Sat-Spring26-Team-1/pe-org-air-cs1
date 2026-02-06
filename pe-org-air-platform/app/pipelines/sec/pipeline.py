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
from app.services.registry import DocumentRegistry
from app.services.s3_storage import aws_service
from app.database.snowflake import db

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

    async def run(self, tickers: List[str], limit: int = 2):
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

        for meta in metadatas:
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
                    continue

                s3_raw_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/{target_file.name}"
                if aws_service.file_exists(s3_raw_key):
                    logger.info("raw_file_exists_skipping_upload", key=s3_raw_key)
                else:
                    aws_service.upload_file(str(target_file), s3_raw_key)

                sections = self.parser.parse(target_file, form_type=meta.filing_type)
                if not sections:
                    logger.warning("no_sections_extracted", file=meta.accession_number)
                    continue

                content_str = json.dumps(sections, sort_keys=True)
                content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

                if self.registry.is_processed(content_hash):
                    logger.info("duplicate_skipped", hash=content_hash)
                    results["skipped"] += 1
                    continue

                s3_key = f"sec/{meta.cik}/{meta.filing_type}/{meta.accession_number}/parsed.json"
                aws_service.upload_bytes(content_str.encode("utf-8"), s3_key, "application/json")

                all_chunks = []
                chunk_index_counter = 0

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

                print("=" * 10)
                print("All chunks: ", all_chunks)
                print("=" * 10)

                doc_id = f"{meta.cik}_{meta.accession_number}"

                db.execute_query(
                    """
                    MERGE INTO documents AS target
                    USING (SELECT %s AS id) AS source
                    ON target.document_id = source.id
                    WHEN MATCHED THEN UPDATE SET processing_status = 'UPDATED'
                    WHEN NOT MATCHED THEN INSERT (
                        document_id, cik, company_name, filing_type, 
                        accession_number, s3_raw_path, content_hash, processing_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'COMPLETED')
                    """,
                    (
                        doc_id,
                        doc_id, meta.cik, meta.company_name, meta.filing_type,
                        meta.accession_number, s3_key, content_hash
                    )
                )

                chunk_params = []
                for ch in all_chunks:
                    chunk_id = f"{doc_id}_{ch['index']}"
                    chunk_params.append((
                        chunk_id, doc_id, ch['index'],
                        ch['section'], ch['text'], ch['tokens']
                    ))

                if chunk_params:
                    db.execute_batch_insert(
                        """
                        INSERT INTO document_chunks (
                            chunk_id, document_id, chunk_index, 
                            section_name, chunk_text, token_count
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        chunk_params
                    )

                self.registry.add(content_hash)
                results["processed"] += 1

            except Exception as e:
                logger.error("processing_error", accession=meta.accession_number, error=str(e))
                results["errors"] += 1

        logger.info("pipeline_complete", results=results)
        return results
