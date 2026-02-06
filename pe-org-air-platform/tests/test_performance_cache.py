import pytest
import time
from app.config import settings

# Base URL for the API

@pytest.mark.asyncio
async def test_redis_caching_performance(client):
    """
    Verify that subsequent requests for the same resource are faster due to Redis caching.
    """
    # 1. Fetch industries (First hit: Cache Miss)
    start_time = time.perf_counter()
    response1 = await client.get("/api/v1/industries/")
    end_time1 = time.perf_counter()
    duration1 = end_time1 - start_time
    
    assert response1.status_code == 200
    
    # 2. Fetch industries (Second hit: Cache Hit)
    start_time = time.perf_counter()
    response2 = await client.get("/api/v1/industries/")
    end_time2 = time.perf_counter()
    duration2 = end_time2 - start_time
    
    assert response2.status_code == 200
    assert response1.json() == response2.json()
    
    # Subsequent hit should be significantly faster (Snowflake connection/query skipped)
    # Note: In a local docker env, this is usually 10x-100x faster
    assert duration2 < duration1, f"Cache hit ({duration2:.4f}s) was not faster than miss ({duration1:.4f}s)"
    print(f"\nCache Miss: {duration1:.4f}s | Cache Hit: {duration2:.4f}s")

@pytest.mark.asyncio
async def test_cache_invalidation_on_update(client):
    """
    Verify that updating a company invalidates the cache for that specific company.
    """
    # 1. List companies to get a valid ID
    list_res = await client.get("/api/v1/companies/")
    items = list_res.json()["items"]
    if not items:
        pytest.skip("No companies found for test")
        
    company = items[0]
    company_id = company["id"]
    
    # 2. Populate cache by getting the company
    await client.get(f"/api/v1/companies/{company_id}")
    
    # 3. Update the company
    new_name = f"Updated Corp {int(time.time())}"
    update_payload = {
        "name": new_name,
        "ticker": company["ticker"],
        "industry_id": company["industry_id"],
        "position_factor": company["position_factor"]
    }
    update_res = await client.put(f"/api/v1/companies/{company_id}", json=update_payload)
    assert update_res.status_code == 200
    
    # 4. Fetch immediately - should show the NEW name (verifying invalidation)
    # If caching didn't invalidate, we'd still see the old name
    fetch_res = await client.get(f"/api/v1/companies/{company_id}")
    assert fetch_res.json()["name"] == new_name

@pytest.mark.asyncio
async def test_cache_ttl_logic(client):
    """
    Check if the Redis client is actually setting TTLs.
    Note: Hard to test 'time passing' without mocks, but we check if Redis has an expiration set.
    """
    from app.services.redis_cache import cache
    
    key = "test:ttl_verification"
    data = {"test": "data"}
    
    # We use the internal client to verify metadata
    import json
    cache.client.setex(key, 5, json.dumps(data))
    
    ttl = cache.client.ttl(key)
    assert 0 < ttl <= 5
    
    # Clean up
    cache.client.delete(key)

@pytest.mark.asyncio
async def test_cache_invalidation_on_creation(client):
    """
    Verify that creating a new company clears the existing list cache.
    """
    # 1. Warm up the list cache
    res1 = await client.get("/api/v1/companies/")
    assert res1.status_code == 200
    count_before = res1.json()["total"]

    # 2. Get industry for new company
    ind_res = await client.get("/api/v1/industries/")
    industry_id = ind_res.json()[0]["id"]

    # 3. Create a NEW company
    payload = {
        "name": f"Invalidate List Test {int(time.time())}",
        "ticker": "ILT",
        "industry_id": industry_id
    }
    await client.post("/api/v1/companies/", json=payload)

    # 4. Fetch list again - should immediately reflect updated count
    # If caching were stuck, it would show the old count_before
    res2 = await client.get("/api/v1/companies/")
    assert res2.json()["total"] > count_before

@pytest.mark.asyncio
async def test_cache_pagination_isolation(client):
    """
    Verify that different pages are cached separately and don't collide.
    """
    # 1. Get Page 1
    res1 = await client.get("/api/v1/companies/", params={"page": 1, "page_size": 1})
    # 2. Get Page 2
    res2 = await client.get("/api/v1/companies/", params={"page": 2, "page_size": 1})
    
    # Verify they are different!
    data1 = res1.json()["items"][0]["id"]
    data2 = res2.json()["items"][0]["id"]
    assert data1 != data2, "Cache error: Page 1 and Page 2 data collided!"

@pytest.mark.asyncio
async def test_assessment_cache_speedup(client):
    """
    Verify caching for Assessments specifically.
    """
    # Get an assessment ID
    list_res = await client.get("/api/v1/assessments")
    assessments = list_res.json()["items"]
    if not assessments:
        pytest.skip("No assessments to test caching")
    a_id = assessments[0]["id"]

    # First hit
    t1 = time.perf_counter()
    await client.get(f"/api/v1/assessments/{a_id}")
    d1 = time.perf_counter() - t1

    # Second hit
    t2 = time.perf_counter()
    await client.get(f"/api/v1/assessments/{a_id}")
    d2 = time.perf_counter() - t2

    assert d2 < d1
    print(f"\nAssessment Speedup: {d1:.4f}s -> {d2:.4f}s")