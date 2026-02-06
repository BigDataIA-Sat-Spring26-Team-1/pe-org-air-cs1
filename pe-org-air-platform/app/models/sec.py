from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class SecDocument(BaseModel):
    document_id: str
    cik: str
    company_name: str
    filing_type: str
    accession_number: str
    filing_date: Optional[str] = None
    s3_raw_path: Optional[str] = None
    content_hash: Optional[str] = None
    processing_status: str = "PENDING"
    created_at: Optional[datetime] = None

class SecDocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    section_name: Optional[str] = None
    chunk_text: str
    token_count: Optional[int] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None

class SecCollectRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, description="List of tickers to collect filings for")
    company_name: Optional[str] = Field(None, description="Optional company name for validation")
    limit: int = Field(2, ge=1, le=10, description="Max filings per ticker")

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
    section: str 
    embedding: Optional[List[float]] = None

class PipelineStats(BaseModel):
    files_downloaded: int = 0
    files_parsed: int = 0
    chunks_generated: int = 0
    errors: List[str] = []
