from fastapi import APIRouter
from app.models.dimension import DIMENSION_WEIGHTS
from app.services.redis_cache import cache
import json

router = APIRouter()

@router.get("/dimension-weights")
async def get_dimension_weights():
    cache_key = "config:dimension_weights"
    
    # Try cache
    cached = cache.client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # "Fetch" weights
    weights = DIMENSION_WEIGHTS
    
    # Cache for 24 hours (86400 seconds)
    cache.client.setex(cache_key, 86400, json.dumps(weights))
    
    return weights