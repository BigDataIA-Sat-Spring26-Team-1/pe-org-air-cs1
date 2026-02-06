import pytest
import pytest_asyncio
import httpx

# Shared test configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0  # Increased timeout for Snowflake connection delays

@pytest_asyncio.fixture
async def client():
    """Provide an async HTTP client with extended timeout for integration tests."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        yield client
