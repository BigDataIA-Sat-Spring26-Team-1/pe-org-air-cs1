import pytest
import asyncio
import time

@pytest.mark.asyncio
async def test_simultaneous_reads(client):
    """
    Test that the API can handle multiple concurrent Read requests.
    """
    # Launch 10 concurrent requests to list industries
    tasks = [client.get("/api/v1/industries/") for _ in range(10)]
    responses = await asyncio.gather(*tasks)
    
    for res in responses:
        assert res.status_code == 200
        assert len(res.json()) > 0

@pytest.mark.asyncio
async def test_simultaneous_writes(client):
    """
    Test concurrent writes to ensure no session corruption.
    Note: Snowflake handles row-level locking or multi-versioning typically.
    """
    # 1. Get a valid industry
    ind_res = await client.get("/api/v1/industries/")
    industry_id = ind_res.json()[0]["id"]
    
    # 2. Launch 5 concurrent writes for DIFFERENT companies
    payloads = [
        {
            "name": f"Concurrent Co {i} - {int(time.time())}",
            "ticker": f"C{i}",
            "industry_id": industry_id,
            "position_factor": 0.1 * i
        }
        for i in range(5)
    ]
    
    tasks = [client.post("/api/v1/companies/", json=p) for p in payloads]
    responses = await asyncio.gather(*tasks)
    
    for res in responses:
        assert res.status_code == 201
        
    print(f"\nSimultaneously created {len(responses)} companies.")

@pytest.mark.asyncio
async def test_read_write_collision(client):
    """
    Perform a read while simultaneously performing a write to ensure isolation.
    """
    ind_res = await client.get("/api/v1/industries/")
    industry_id = ind_res.json()[0]["id"]
    
    write_payload = {
        "name": f"Collision Test {int(time.time())}",
        "ticker": "COL",
        "industry_id": industry_id
    }
    
    # Run Read and Write in parallel
    # Note: We clear the cache for companies first to force a DB read
    from app.services.redis_cache import cache
    cache.delete_pattern("companies:list:*")
    
    res_write, res_read = await asyncio.gather(
        client.post("/api/v1/companies/", json=write_payload),
        client.get("/api/v1/companies/")
    )
    
    assert res_write.status_code == 201
    assert res_read.status_code == 200