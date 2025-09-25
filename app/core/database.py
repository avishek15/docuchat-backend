"""Database connection and session management for Turso."""

import os
from typing import Optional
from contextlib import asynccontextmanager
import libsql
import structlog
from sqlmodel import SQLModel, create_engine, Session
from app.core.config import get_settings

logger = structlog.get_logger()


class DatabaseManager:
    """Manages database connections and operations for Turso."""

    def __init__(self):
        self.settings = get_settings()
        self._connection: Optional[libsql.Connection] = None
        self.logger = logger.bind(service="DatabaseManager")

    def get_connection(self) -> libsql.Connection:
        """Get or create a Turso database connection."""
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection

    def _create_connection(self) -> libsql.Connection:
        """Create a new Turso database connection."""
        try:
            # Check if Turso credentials are provided
            if self.settings.turso_database_url and self.settings.turso_auth_token:
                # Connect with embedded replica (local + remote sync)
                self.logger.info("Connecting to Turso with embedded replica")
                conn = libsql.connect(
                    self.settings.local_db_path,
                    sync_url=self.settings.turso_database_url,
                    auth_token=self.settings.turso_auth_token,
                )
                # Initial sync to get latest data
                conn.sync()
                self.logger.info("Connected to Turso database with sync")
            else:
                # Local-only connection for development
                self.logger.info("Connecting to local SQLite database")
                conn = libsql.connect(self.settings.local_db_path)
                self.logger.info("Connected to local database")

            return conn

        except Exception as e:
            self.logger.error("Failed to connect to database", error=str(e))
            raise

    def sync(self) -> None:
        """Sync local database with remote Turso database."""
        if self._connection and self.settings.turso_database_url:
            try:
                self._connection.sync()
                self.logger.debug("Database synced successfully")
            except Exception as e:
                self.logger.error("Failed to sync database", error=str(e))
                raise

    def create_tables(self) -> None:
        """Create all database tables using migration system."""
        try:
            from app.db.migrations import run_migrations

            self.logger.info("Running database migrations")
            run_migrations()
            self.logger.info("Database tables created successfully via migrations")

        except Exception as e:
            self.logger.error("Failed to create database tables", error=str(e))
            raise

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            try:
                # Final sync before closing
                self.sync()
                self._connection.close()
                self._connection = None
                self.logger.info("Database connection closed")
            except Exception as e:
                self.logger.error("Error closing database connection", error=str(e))


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
    conn = db_manager.get_connection()
    try:
        yield conn
    finally:
        # Sync after operations
        db_manager.sync()


def init_database():
    """Initialize database and create tables."""
    db_manager = get_database_manager()
    db_manager.create_tables()
