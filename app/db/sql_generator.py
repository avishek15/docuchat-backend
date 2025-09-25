"""SQL Generator for converting SQLModel classes to SQL statements."""

from typing import List, Dict, Any, Optional, Type
from sqlmodel import SQLModel, create_engine
from sqlalchemy.schema import CreateTable, DropTable
from sqlalchemy.sql import select, insert, update, delete
import structlog

logger = structlog.get_logger()


class SQLGenerator:
    """Generates SQL statements from SQLModel classes using SQLAlchemy."""

    def __init__(self, dialect: str = "sqlite"):
        """Initialize SQL generator with database dialect."""
        self.logger = logger.bind(service="SQLGenerator")
        self.dialect = dialect

        # Create engine for SQL compilation
        if dialect == "sqlite":
            self._engine = create_engine("sqlite:///:memory:")
        elif dialect == "postgresql":
            self._engine = create_engine("postgresql:///:memory:")
        elif dialect == "mysql":
            self._engine = create_engine("mysql:///:memory:")
        else:
            raise ValueError(f"Unsupported dialect: {dialect}")

    def get_table_models(self, models: List[Type[SQLModel]]) -> List[Type[SQLModel]]:
        """Filter models that have table=True."""
        table_models = []
        for model in models:
            if hasattr(model, "__table__") and model.__table__ is not None:
                table_models.append(model)
                self.logger.debug(
                    f"Found table model: {model.__name__} -> {model.__tablename__}"
                )
        return table_models

    def generate_create_table_sql(self, model: Type[SQLModel]) -> str:
        """Generate CREATE TABLE SQL for a SQLModel class."""
        if not hasattr(model, "__table__"):
            raise ValueError(f"Model {model.__name__} is not a table model")

        create_sql = str(CreateTable(model.__table__).compile(self._engine))
        self.logger.debug(f"Generated CREATE TABLE for {model.__name__}")
        return create_sql

    def generate_drop_table_sql(self, model: Type[SQLModel]) -> str:
        """Generate DROP TABLE SQL for a SQLModel class."""
        if not hasattr(model, "__table__"):
            raise ValueError(f"Model {model.__name__} is not a table model")

        drop_sql = str(DropTable(model.__table__).compile(self._engine))
        self.logger.debug(f"Generated DROP TABLE for {model.__name__}")
        return drop_sql

    def generate_insert_sql(
        self, model: Type[SQLModel], data: Dict[str, Any]
    ) -> tuple[str, tuple]:
        """Generate INSERT SQL for a SQLModel class with data."""
        if not hasattr(model, "__table__"):
            raise ValueError(f"Model {model.__name__} is not a table model")

        table = model.__table__

        # Filter data to only include valid columns
        valid_columns = {col.name for col in table.columns}
        filtered_data = {k: v for k, v in data.items() if k in valid_columns}

        if not filtered_data:
            raise ValueError("No valid data provided for insert")

        # Generate INSERT statement
        stmt = insert(table).values(**filtered_data)
        compiled = stmt.compile(self._engine)

        sql = str(compiled)
        params = tuple(compiled.params.values()) if compiled.params else ()

        self.logger.debug(f"Generated INSERT for {model.__name__}")
        return sql, params

    def generate_select_sql(
        self,
        model: Type[SQLModel],
        where_conditions: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> tuple[str, tuple]:
        """Generate SELECT SQL for a SQLModel class."""
        if not hasattr(model, "__table__"):
            raise ValueError(f"Model {model.__name__} is not a table model")

        table = model.__table__

        # Select specific columns or all
        if columns:
            selected_columns = [
                getattr(table.c, col) for col in columns if hasattr(table.c, col)
            ]
        else:
            selected_columns = [table]

        stmt = select(*selected_columns)

        # Add WHERE conditions
        params = []
        if where_conditions:
            for column_name, value in where_conditions.items():
                if hasattr(table.c, column_name):
                    column = getattr(table.c, column_name)
                    stmt = stmt.where(column == value)
                    params.append(value)

        # Add ORDER BY
        if order_by and hasattr(table.c, order_by):
            stmt = stmt.order_by(getattr(table.c, order_by))

        # Add LIMIT
        if limit:
            stmt = stmt.limit(limit)

        compiled = stmt.compile(self._engine)
        sql = str(compiled)

        self.logger.debug(f"Generated SELECT for {model.__name__}")
        return sql, tuple(params)

    def generate_update_sql(
        self,
        model: Type[SQLModel],
        data: Dict[str, Any],
        where_conditions: Dict[str, Any],
    ) -> tuple[str, tuple]:
        """Generate UPDATE SQL for a SQLModel class."""
        if not hasattr(model, "__table__"):
            raise ValueError(f"Model {model.__name__} is not a table model")

        table = model.__table__

        # Filter data to only include valid columns
        valid_columns = {col.name for col in table.columns}
        filtered_data = {k: v for k, v in data.items() if k in valid_columns}

        if not filtered_data:
            raise ValueError("No valid data provided for update")

        if not where_conditions:
            raise ValueError("WHERE conditions are required for UPDATE")

        stmt = update(table).values(**filtered_data)

        # Add WHERE conditions
        params = list(filtered_data.values())
        for column_name, value in where_conditions.items():
            if hasattr(table.c, column_name):
                column = getattr(table.c, column_name)
                stmt = stmt.where(column == value)
                params.append(value)

        compiled = stmt.compile(self._engine)
        sql = str(compiled)

        self.logger.debug(f"Generated UPDATE for {model.__name__}")
        return sql, tuple(params)

    def generate_delete_sql(
        self, model: Type[SQLModel], where_conditions: Dict[str, Any]
    ) -> tuple[str, tuple]:
        """Generate DELETE SQL for a SQLModel class."""
        if not hasattr(model, "__table__"):
            raise ValueError(f"Model {model.__name__} is not a table model")

        table = model.__table__

        if not where_conditions:
            raise ValueError("WHERE conditions are required for DELETE")

        stmt = delete(table)

        # Add WHERE conditions
        params = []
        for column_name, value in where_conditions.items():
            if hasattr(table.c, column_name):
                column = getattr(table.c, column_name)
                stmt = stmt.where(column == value)
                params.append(value)

        compiled = stmt.compile(self._engine)
        sql = str(compiled)

        self.logger.debug(f"Generated DELETE for {model.__name__}")
        return sql, tuple(params)

    def generate_migration_sql(self, models: List[Type[SQLModel]]) -> str:
        """Generate complete migration SQL for multiple models."""
        table_models = self.get_table_models(models)

        if not table_models:
            self.logger.warning("No table models found!")
            return ""

        # Generate DROP statements (in reverse order for foreign keys)
        drop_statements = []
        for model in reversed(table_models):
            drop_statements.append(f"DROP TABLE IF EXISTS {model.__tablename__};")

        # Generate CREATE statements
        create_statements = []
        for model in table_models:
            create_sql = self.generate_create_table_sql(model)
            create_statements.append(create_sql + ";")

        # Build migration content
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        migration_sql = f"""-- Auto-generated migration: {timestamp}
-- Generated from SQLModel classes using SQLAlchemy
-- WARNING: This will DROP all existing tables and recreate them

-- Step 1: Drop existing tables
{chr(10).join(drop_statements)}

-- Step 2: Create tables from SQLModel definitions
{chr(10).join(create_statements)}

-- Step 3: Create migrations tracking table
CREATE TABLE IF NOT EXISTS migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO migrations (version, description) 
VALUES ('{timestamp}', 'Auto-generated from SQLModel classes');
"""

        self.logger.info(f"Generated migration SQL for {len(table_models)} models")
        return migration_sql

    def get_model_info(self, model: Type[SQLModel]) -> Dict[str, Any]:
        """Get detailed information about a SQLModel class."""
        if not hasattr(model, "__table__"):
            return {"error": f"Model {model.__name__} is not a table model"}

        table = model.__table__

        columns_info = []
        for column in table.columns:
            col_info = {
                "name": column.name,
                "type": str(column.type),
                "nullable": column.nullable,
                "primary_key": column.primary_key,
                "unique": column.unique,
                "autoincrement": getattr(column, "autoincrement", False),
                "default": str(column.default) if column.default else None,
            }
            columns_info.append(col_info)

        foreign_keys = []
        for fk in table.foreign_keys:
            fk_info = {
                "column": fk.parent.name,
                "references_table": fk.column.table.name,
                "references_column": fk.column.name,
            }
            foreign_keys.append(fk_info)

        return {
            "model_name": model.__name__,
            "table_name": model.__tablename__,
            "columns": columns_info,
            "foreign_keys": foreign_keys,
            "indexes": [idx.name for idx in table.indexes],
        }

    def validate_data(
        self, model: Type[SQLModel], data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate data against SQLModel schema."""
        try:
            # Create an instance to validate
            instance = model(**data)
            return {"valid": True, "data": instance.dict()}
        except Exception as e:
            return {"valid": False, "error": str(e)}


# Global SQL generator instance
_sql_generator: Optional[SQLGenerator] = None


def get_sql_generator(dialect: str = "sqlite") -> SQLGenerator:
    """Get or create the global SQL generator instance."""
    global _sql_generator
    if _sql_generator is None or _sql_generator.dialect != dialect:
        _sql_generator = SQLGenerator(dialect)
    return _sql_generator
