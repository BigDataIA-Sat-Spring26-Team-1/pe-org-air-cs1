from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class FilingMetadata(BaseModel):
    cik: str
    company_name: str
    filing_type: str
    accession_number: str
    filing_date: Optional[str] = None
    report_period: Optional[str] = None
    s3_path: str
    content_hash: str
    
class ProcessedChunk(BaseModel):
    chunk_index: int
    text: str
    tokens: int
    section: str  # "Item 1", "Item 7", etc.
    embedding: Optional[List[float]] = None

class PipelineStats(BaseModel):
    files_downloaded: int = 0
    files_parsed: int = 0
    chunks_generated: int = 0
    errors: List[str] = []
