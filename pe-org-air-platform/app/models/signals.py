from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

class SignalCategory(str, Enum):
    TECHNOLOGY_HIRING = "technology_hiring"
    INNOVATION_ACTIVITY = "innovation_activity"
    DIGITAL_PRESENCE = "digital_presence"
    LEADERSHIP_SIGNALS = "leadership_signals"

class SignalCollectionRequest(BaseModel):
    ticker: Optional[str] = Field(None, description="Company ticker symbol")
    company_name: Optional[str] = Field(None, description="Full company name")
    company_id: Optional[str] = None

    job_days: int = Field(7, ge=1, le=90, description="Lookback period for job postings in days")
    patent_years: int = Field(5, ge=1, le=20, description="Lookback period for patents in years")
    force_refresh: bool = Field(False, description="Whether to bypass cache and force a new run")

    @root_validator(pre=True)
    def check_identity(cls, values):
        ticker = values.get('ticker')
        company_name = values.get('company_name')
        if not ticker and not company_name:
            raise ValueError("Either 'ticker' or 'company_name' must be provided.")
        return values


class SignalEvidenceItem(BaseModel):
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    date: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CollectorResult(BaseModel):
    category: SignalCategory
    normalized_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    raw_value: str
    evidence: List[SignalEvidenceItem] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict) # High-level pulse metadata only
    signal_date: str = Field(default_factory=lambda: datetime.now().date().isoformat())
    source: str

class ExternalSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_hash: Optional[str] = None # SHA256(company_id + source + raw_identifier) for deduplication
    company_id: str
    category: SignalCategory
    source: str
    signal_date: str
    raw_value: str
    normalized_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    metadata: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SignalEvidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str
    company_id: str
    category: SignalCategory
    source: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    evidence_date: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CompanySignalSummary(BaseModel):
    company_id: str
    ticker: str
    technology_hiring_score: float = Field(default=0.0, ge=0, le=100)
    innovation_activity_score: float = Field(default=0.0, ge=0, le=100)
    digital_presence_score: float = Field(default=0.0, ge=0, le=100)
    leadership_signals_score: float = Field(default=0.0, ge=0, le=100)
    composite_score: float = Field(default=0.0, ge=0, le=100)
    signal_count: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)