"""Main API router for v1."""

from fastapi import APIRouter
from app.models import HealthResponse
from .auth import router as auth_router
from .file_management import router as file_management_router
from .chat import router as chat_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(
    file_management_router, prefix="/files", tags=["file_management"]
)
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])


# Health check endpoint
@api_router.get("/health", response_model=HealthResponse)
async def api_health():
    """API health check."""
    return HealthResponse(status="ok", version="v1")
