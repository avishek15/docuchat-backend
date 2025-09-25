"""Simple migration system that generates and applies SQL migrations independently."""

from datetime import datetime
from pathlib import Path
import structlog
from app.core.config import get_settings
from app.core.database import get_database_manager
from app.db.sql_generator import get_sql_generator

logger = structlog.get_logger()


class SimpleMigrationGenerator:
    """Generates and applies SQL migrations independently."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = logger.bind(service="SimpleMigrationGenerator")
        self.db_manager = get_database_manager()
        self.sql_generator = get_sql_generator("sqlite")
        self.migrations_dir = Path(__file__).parent / "sql"
        self.migrations_dir.mkdir(exist_ok=True)

    def get_sqlmodel_classes(self):
        """Get all SQLModel classes that should be tables."""
        # Import all table models
        from app.models.auth import User, UserSession
        from app.models.files import File, FileChunk

        # Return all table models
        return [User, UserSession, File, FileChunk]

    def generate_migration_sql(self) -> str:
        """Generate complete migration SQL using SQLGenerator."""
        models = self.get_sqlmodel_classes()

        if not models:
            self.logger.warning("No SQLModel classes found!")
            return ""

        # Use SQLGenerator to generate complete migration SQL
        migration_sql = self.sql_generator.generate_migration_sql(models)

        self.logger.info(f"Generated migration SQL for {len(models)} models")
        return migration_sql

    def save_migration(self, sql_content: str) -> str:
        """Save migration SQL to a file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_recreate_all_tables.sql"
        filepath = self.migrations_dir / filename

        filepath.write_text(sql_content)
        self.logger.info(f"Migration saved to: {filepath}")

        return str(filepath)

    def apply_migration(self, sql_content: str) -> None:
        """Apply the migration to the database using DatabaseManager."""
        try:
            # Use DatabaseManager to execute the migration script
            self.db_manager.execute_sql_script(sql_content)
            self.logger.info("Migration applied and synced with Turso")

        except Exception as e:
            self.logger.error(f"Failed to apply migration: {e}")
            raise

    def generate_and_save(self) -> str:
        """Generate migration SQL and save to file."""
        sql_content = self.generate_migration_sql()
        filepath = self.save_migration(sql_content)
        return filepath

    def generate_and_apply(self) -> None:
        """Generate and immediately apply migration."""
        sql_content = self.generate_migration_sql()

        # Save for record keeping
        self.save_migration(sql_content)

        # Apply to database
        self.apply_migration(sql_content)

        self.logger.info("Migration generated and applied successfully!")

    def check_migration_status(self) -> bool:
        """Check if migrations table exists and get latest migration."""
        try:
            # Use DatabaseManager to execute queries
            result = self.db_manager.execute_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
            ).fetchone()

            if not result:
                self.logger.info("No migrations table found - fresh database")
                return False

            # Get latest migration
            latest = self.db_manager.execute_sql(
                "SELECT version, description, applied_at FROM migrations ORDER BY applied_at DESC LIMIT 1"
            ).fetchone()

            if latest:
                self.logger.info(
                    "Latest migration found",
                    version=latest[0],
                    description=latest[1],
                    applied_at=latest[2],
                )
            else:
                self.logger.info("Migrations table exists but no migrations recorded")

            return True

        except Exception as e:
            self.logger.error(f"Failed to check migration status: {e}")
            return False
