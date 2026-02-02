from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_conf import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger("app")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} API"}