from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional

class IndustryBase(BaseModel):
    name: str = Field(..., max_length=255)
    sector: str = Field(..., max_length=100)
    h_r_base: float = Field(..., ge=0, le=100)

class IndustryCreate(IndustryBase):
    pass

class IndustryResponse(IndustryBase):
    id: UUID
    created_at: datetime
    
    model_config = {
        "from_attributes": True
    }
