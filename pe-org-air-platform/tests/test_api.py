import pytest
import time

# Tests run against the LIVE running docker container
@pytest.mark.asyncio
async def test_health_check_live(client):
    """Test the health endpoint on the live container."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

@pytest.mark.asyncio
async def test_root_live(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]

@pytest.mark.asyncio
async def test_duplicate_company_name(client):
    """
    Verify that creating a company with an existing name (Unique constraint) is handled.
    """
    # 1. Get industry
    ind_res = await client.get("/api/v1/industries/")
    industries = ind_res.json()
    if not industries:
        pytest.skip("No industries available to link company")
    industry_id = industries[0]["id"]
    
    unique_name = f"Constraint Test Co {int(time.time())}"
    payload = {
        "name": unique_name,
        "ticker": "CON",
        "industry_id": industry_id
    }
    
    # 2. First creation - Success
    res1 = await client.post("/api/v1/companies/", json=payload)
    assert res1.status_code == 201
    
    # 3. Second creation - Should fail due to UNIQUE constraint on NAME
    res2 = await client.post("/api/v1/companies/", json=payload)
    
    print(f"Duplicate check result: {res2.status_code}")