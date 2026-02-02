from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    ticker: Optional[str] = Field(None, max_length=10)
    industry_id: UUID
    position_factor: float = Field(default=0.0, ge=-1.0, le=1.0)

    @field_validator('ticker')
    @classmethod
    def uppercase_ticker(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else None

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Tesla, Inc.",
                "ticker": "TSLA",
                "industry_id": "550e8400-e29b-41d4-a716-446655440001",
                "position_factor": 0.85
            }
        }
    }

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }