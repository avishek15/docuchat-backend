"""Migration manager for handling database schema operations."""

import structlog
from app.core.database import get_database_manager
from app.db.migrations.simple_migration import SimpleMigrationGenerator

logger = structlog.get_logger()


class MigrationManager:
    """Manages database migrations independently."""

    def __init__(self):
        self.logger = logger.bind(service="MigrationManager")
        self.db_manager = get_database_manager()
        self.migration_generator = SimpleMigrationGenerator()

    def create_tables(self) -> None:
        """Create all database tables using migration generator."""
        try:
            self.logger.info("Creating database tables using migration generator")
            self.migration_generator.generate_and_apply()
            self.logger.info("Database tables created successfully")

        except Exception as e:
            self.logger.error("Failed to create database tables", error=str(e))
            raise

    def check_migration_status(self) -> bool:
        """Check migration status."""
        return self.migration_generator.check_migration_status()

    def generate_migration_only(self) -> str:
        """Generate migration SQL without applying."""
        return self.migration_generator.generate_and_save()


# Global migration manager instance
_migration_manager = None


def get_migration_manager() -> MigrationManager:
    """Get or create the global migration manager instance."""
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager()
    return _migration_manager
