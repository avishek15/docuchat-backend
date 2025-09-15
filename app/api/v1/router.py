"""Main API router for v1."""

from fastapi import APIRouter
from .auth import router as auth_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])


# Health check endpoint
@api_router.get("/health")
async def api_health():
    """API health check."""
    return {"status": "ok", "version": "v1"}
