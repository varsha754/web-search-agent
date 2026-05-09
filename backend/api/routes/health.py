"""Health-check endpoints."""

from fastapi import APIRouter

from core.config import config


router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Return basic service status and feature flags."""
    return {
        "status": "healthy",
        "llm_enabled": config.USE_LLM,
        "cache_enabled": config.CACHE_ENABLED,
    }
