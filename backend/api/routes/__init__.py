"""FastAPI route registry."""

from fastapi import APIRouter

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router
from api.routes.search import router as search_router
from api.routes.web import router as web_router


router = APIRouter()
router.include_router(web_router)
router.include_router(health_router)
router.include_router(search_router, prefix="/api", tags=["search"])
router.include_router(chat_router, prefix="/api", tags=["chat"])
