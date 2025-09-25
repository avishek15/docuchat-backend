"""Database connection management using SQLAlchemy with Turso remote-only connection."""

from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import structlog
from app.core.config import get_settings

logger = structlog.get_logger()


class DatabaseManager:
    """Database manager using SQLAlchemy with Turso remote-only connection."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = logger.bind(service="DatabaseManager")
        self._engine = None
        self._SessionLocal = None

    @property
    def engine(self):
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            self._create_engine()
        return self._engine

    @property
    def SessionLocal(self):
        """Get or create session factory."""
        if self._SessionLocal is None:
            self._SessionLocal = sessionmaker(bind=self.engine)
        return self._SessionLocal

    def _create_engine(self):
        """Create SQLAlchemy engine with Turso remote-only connection."""
        try:
            # Check if Turso credentials are provided
            if self.settings.turso_database_url and self.settings.turso_auth_token:
                # Use remote-only connection as per Turso docs
                self.logger.info("Connecting to Turso cloud database (remote-only)")

                # Format the URL for SQLAlchemy libSQL dialect
                database_url = f"sqlite+{self.settings.turso_database_url}?secure=true"

                self._engine = create_engine(
                    database_url,
                    connect_args={
                        "auth_token": self.settings.turso_auth_token,
                    },
                    poolclass=StaticPool,
                    pool_pre_ping=True,
                    echo=False,  # Set to True for SQL debugging
                )
                self.logger.info("Connected to Turso cloud database")
            else:
                # Fallback to local SQLite for development
                self.logger.info("Connecting to local SQLite database")
                self._engine = create_engine(
                    f"sqlite:///{self.settings.local_db_path}",
                    poolclass=StaticPool,
                    echo=False,
                )
                self.logger.info("Connected to local database")

        except Exception as e:
            self.logger.error("Failed to create database engine", error=str(e))
            raise

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def execute_sql(self, sql: str, params: tuple = None) -> any:
        """Execute a single SQL statement (for backward compatibility)."""
        try:
            with self.get_session() as session:
                result = session.execute(sql, params or ())
                session.commit()
                return result
        except Exception as e:
            self.logger.error("Failed to execute SQL", sql=sql, error=str(e))
            raise

    def execute_sql_script(self, sql_script: str) -> None:
        """Execute multiple SQL statements from a script."""
        try:
            with self.get_session() as session:
                for statement in sql_script.split(";"):
                    statement = statement.strip()
                    if statement:
                        session.execute(statement)
                session.commit()
        except Exception as e:
            self.logger.error("Failed to execute SQL script", error=str(e))
            raise

    def close(self) -> None:
        """Close database engine."""
        if self._engine:
            try:
                self._engine.dispose()
                self._engine = None
                self._SessionLocal = None
                self.logger.info("Database engine closed")
            except Exception as e:
                self.logger.error("Error closing database engine", error=str(e))


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


@asynccontextmanager
async def get_db_connection():
    """Async context manager for database connections."""
    db_manager = get_database_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()
