"""FastAPI application main module."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.exceptions import DocuChatException
from app.core.database import init_database
from app.models import HealthResponse
from app.api.v1.router import api_router
from app.utils.logging import configure_logging

# Configure logging
logger = configure_logging()

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting up DocuChat API")
    try:
        # Initialize database and create tables
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down DocuChat API")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="DocuChat API",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint."""
    return HealthResponse(
        status="ok",
        message="DocuChat API",
        version="1.0.0",
        environment=settings.environment,
    )


# Global exception handler
@app.exception_handler(DocuChatException)
async def docuchat_exception_handler(request, exc):
    """Handle custom DocuChat exceptions."""
    logger.error("DocuChat exception", error=exc.message, error_code=exc.error_code)
    return {"status": "error", "message": exc.message, "error_code": exc.error_code}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
