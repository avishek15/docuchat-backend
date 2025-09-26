"""FastAPI application main module."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.exceptions import DocuChatException
from app.services.database.auth import AuthDatabaseService
# from app.core.database import init_database

# from app.db.migrations.migration_manager import get_migration_manager
from app.models import HealthResponse
from app.api.v1.router import api_router
from app.utils.logging import configure_logging

# Configure logging
logger = configure_logging()

# Get settings
settings = get_settings()


async def background_cleanup():
    """Background task to clean up expired and inactive sessions."""
    auth_service = AuthDatabaseService()
    logger.info("Starting background cleanup task")

    try:
        while True:
            try:
                cleaned_count = await auth_service.cleanup_expired_sessions()
                if cleaned_count > 0:
                    logger.info(
                        "Background cleanup completed", sessions_cleaned=cleaned_count
                    )
                else:
                    logger.debug("No sessions to clean up")
            except Exception as e:
                logger.error("Background cleanup failed", error=str(e))
                # Don't let cleanup errors crash the server
                pass

            # Wait 5 minutes before next cleanup
            await asyncio.sleep(300)  # 5 minutes

    except asyncio.CancelledError:
        logger.info("Background cleanup task cancelled")
        raise
    except Exception as e:
        logger.error("Background cleanup task failed", error=str(e))
        # Don't let the task crash the entire application


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting up DocuChat API")
    try:
        # Initialize database connection
        # init_database()
        # logger.info("Database connection initialized")

        # Create tables using migration manager
        # migration_manager = get_migration_manager()
        # migration_manager.create_tables()
        logger.info("Database tables created successfully")

        # Start background cleanup task (non-blocking)
        cleanup_task = asyncio.create_task(background_cleanup())
        logger.info("Background session cleanup started")

    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down DocuChat API")
    if "cleanup_task" in locals():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Background cleanup task cancelled")


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
