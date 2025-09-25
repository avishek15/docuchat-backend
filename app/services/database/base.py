"""Base database service for common functionality."""

from typing import Optional
from sqlalchemy.orm import Session
import structlog
from app.core.database import get_database_manager

logger = structlog.get_logger()


class BaseDatabaseService:
    """Base database service with common functionality."""

    def __init__(self):
        self.logger = logger.bind(service=self.__class__.__name__)
        self.db_manager = get_database_manager()

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.db_manager.get_session()
