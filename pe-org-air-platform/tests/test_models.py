import pytest
from app.models.company import CompanyCreate, CompanyResponse
from app.models.assessment import AssessmentCreate, AssessmentResponse, AssessmentStatus
from app.models.dimension import DimensionScoreBase, DimensionScoreResponse, DimensionScoreCreate
from app.models.enums import AssessmentType, Dimension
from uuid import uuid4
from pydantic import ValidationError

def test_company_validations():
    # 1. Ticker Uppercasing
    c = CompanyCreate(name="Tesla", ticker="tsla", industry_id=uuid4())
    assert c.ticker == "TSLA"

    # 2. Position Factor Boundaries (Valid)
    CompanyCreate(name="T", industry_id=uuid4(), position_factor=-1.0)
    CompanyCreate(name="T", industry_id=uuid4(), position_factor=1.0)
    
    # 3. Position Factor Boundaries (Invalid)
    with pytest.raises(ValidationError):
        CompanyCreate(name="T", industry_id=uuid4(), position_factor=1.001)

def test_assessment_validations():
    # 1. Confidence interval logic
    with pytest.raises(ValidationError):
         AssessmentResponse(
            id=uuid4(), company_id=uuid4(), 
            assessment_type=AssessmentType.SCREENING, 
            created_at="2024-01-01T00:00:00",
            confidence_lower=80, confidence_upper=70 # Fails lower > upper
        )

def test_dimension_score_logic():
    # 1. Automatic Weight Calculation (The Formula mentioned in PDF Page 11)
    # data_infrastructure should default to 0.25
    ds = DimensionScoreCreate(
        assessment_id=uuid4(),
        dimension=Dimension.DATA_INFRASTRUCTURE,
        score=75.0
    )
    assert ds.weight == 0.25
    
    # talent_skills should default to 0.10
    ds2 = DimensionScoreCreate(
        assessment_id=uuid4(),
        dimension=Dimension.TALENT_SKILLS,
        score=50.0
    )
    assert ds2.weight == 0.15

    # 2. Manual weight override
    ds3 = DimensionScoreCreate(
        assessment_id=uuid4(),
        dimension=Dimension.CULTURE_CHANGE,
        score=50.0,
        weight=0.99 # Overrides default 0.05
    )
    assert ds3.weight == 0.99

    # 3. Score range validation
    with pytest.raises(ValidationError):
        DimensionScoreCreate(assessment_id=uuid4(), dimension=Dimension.AI_GOVERNANCE, score=101) # > 100

def test_type_casting():
    # Verify that string-numbers are cast to floats correctly
    ds = DimensionScoreCreate(
        assessment_id=uuid4(),
        dimension=Dimension.TECHNOLOGY_STACK,
        score="88.5" # String type
    )
    assert ds.score == 88.5
    assert isinstance(ds.score, float)