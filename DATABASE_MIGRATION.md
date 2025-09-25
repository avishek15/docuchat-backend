# Database Migration System

## Overview

This project uses a **simple migration system** designed for rapid development. The system prioritizes simplicity over data preservation - it recreates all tables from SQLModel definitions on each migration.

## Key Principles

1. **Models are the single source of truth** - Your SQLModel classes define the database schema
2. **Clean slate migrations** - Each migration drops ALL tables and recreates them
3. **Turso cloud sync** - Changes are automatically synced with Turso cloud database

## How It Works

### 1. Model Definition

Define your models in the `app/models/` directory. Any model that needs database persistence must:

-   Inherit from SQLModel
-   Have `table=True` parameter
-   Will automatically have a `__tablename__` attribute

```python
from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    __tablename__ = "users"  # Explicit table name

    id: Optional[int] = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: Optional[str] = None
```

### 2. Migration Commands

#### Generate Migration SQL (Safe - Review First)

```bash
uv run python manage.py generate-migration
```

-   Creates a timestamped SQL file in `app/db/migrations/sql/`
-   Shows exactly what SQL will be executed
-   No database changes are made
-   Review the SQL before applying

#### Apply Migration (⚠️ DESTRUCTIVE - Data Loss!)

```bash
uv run python manage.py apply-migration
```

-   **WARNING**: Drops ALL tables and data
-   Recreates tables from current model definitions
-   Syncs changes with Turso cloud
-   Requires explicit confirmation

### 3. Database Architecture

```
┌─────────────────┐
│  SQLModel       │
│  Definitions    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Local SQLite   │ ◄─── Read/Write Operations
│  (local.db)     │
└────────┬────────┘
         │
         │ sync()
         ▼
┌─────────────────┐
│  Turso Cloud    │ ◄─── Backup & Multi-instance Sync
│  Database       │
└─────────────────┘
```

## Workflow

### Development Workflow

1. **Modify your models** in `app/models/`
2. **Generate migration** to see SQL changes
3. **Apply migration** when ready (accepts data loss)

### Adding a New Model

```python
# 1. Create model in app/models/your_model.py
class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(primary_key=True)
    name: str
    price: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 2. Import in app/models/__init__.py
from .your_model import Product

# 3. Generate and apply migration
uv run python manage.py generate-migration
uv run python manage.py apply-migration
```

### Modifying an Existing Model

```python
# 1. Update the model
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    name: Optional[str] = None
    phone: Optional[str] = None  # New field added

# 2. Apply migration (⚠️ loses existing data)
uv run python manage.py apply-migration
```

## Important Notes

### Pros ✅

-   **Simple and fast** - No complex migration files to manage
-   **Models are truth** - Database always matches model definitions
-   **Cloud sync** - Automatic sync with Turso cloud
-   **Clean migrations** - No migration conflicts or version issues

### Cons ⚠️

-   **Data loss on every migration** - All data is deleted
-   **No rollback** - Cannot undo migrations
-   **Not for production** - Only suitable for development

### When to Use This System

-   ✅ Early development phase
-   ✅ Prototyping and experimentation
-   ✅ When data can be easily recreated
-   ✅ Test environments

### When NOT to Use This System

-   ❌ Production environments
-   ❌ When you have important data
-   ❌ When you need migration rollbacks
-   ❌ When you need data transformations

## Turso Integration

The system uses Turso's embedded replica model:

-   **Local operations** - All reads/writes happen on local SQLite (fast!)
-   **Automatic sync** - Changes sync to Turso cloud after writes
-   **Multi-instance** - Multiple app instances can sync through Turso

### Environment Variables

```bash
# Required for Turso sync
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-auth-token

# Local database path
LOCAL_DB_PATH=local.db
```

## Troubleshooting

### Migration Fails

```bash
# Check database info
uv run python manage.py db-info

# Review generated SQL
uv run python manage.py generate-migration
# Check the file in app/db/migrations/sql/
```

### Sync Issues with Turso

-   Ensure `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set
-   Check network connectivity
-   Verify Turso database exists and is accessible

### Model Not Creating Table

-   Ensure model has `table=True` parameter
-   Import model in `app/models/__init__.py`
-   Check for SQLModel inheritance

## Future Improvements

When ready for production, consider:

1. Implementing Alembic for proper migrations
2. Adding data migration scripts
3. Implementing backup before migrations
4. Adding migration rollback capability

## Commands Reference

| Command              | Description                  | Data Safe? |
| -------------------- | ---------------------------- | ---------- |
| `generate-migration` | Generate SQL file only       | ✅ Yes     |
| `apply-migration`    | Drop and recreate all tables | ❌ No      |
| `db-info`            | Show database configuration  | ✅ Yes     |
| `test-auth`          | Test authentication flow     | ✅ Yes     |

---

**Remember**: This migration system is designed for **development speed**, not data safety. Always backup important data before running migrations!
