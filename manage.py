#!/usr/bin/env python3
"""Management script for DocuChat backend operations."""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_database_manager


def print_banner():
    """Print application banner."""
    print("=" * 60)
    print("🚀 DocuChat Backend Management")
    print("=" * 60)


def print_help():
    """Print help information."""
    print("""
Available commands:

Database Migration:
  generate-migration      Generate SQL file to recreate all tables
  apply-migration         Drop all tables and recreate from models (DATA LOSS!)
  
Database Info:
  db-info                 Show database connection info
  test-auth              Test authentication flow

Examples:
  uv run python manage.py generate-migration
  uv run python manage.py apply-migration
  uv run python manage.py test-auth
""")


def handle_db_info():
    """Handle database info command."""
    from app.core.config import get_settings

    settings = get_settings()
    print("🗄️  Database Configuration:")

    if settings.turso_database_url:
        print(f"   Type: Turso Cloud")
        print(f"   URL: {settings.turso_database_url}")
        print(
            f"   Auth Token: {'✅ Configured' if settings.turso_auth_token else '❌ Missing'}"
        )
    else:
        print(f"   Type: Local SQLite")
        print(f"   Path: {settings.local_db_path}")

    # Test connection
    try:
        db_manager = get_database_manager()
        conn = db_manager.get_connection()

        # Get database info
        result = conn.execute("SELECT sqlite_version()").fetchone()
        sqlite_version = result[0] if result else "Unknown"

        print(f"   SQLite Version: {sqlite_version}")
        print("   Connection: ✅ Successful")

        # Get table count
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        table_count = tables[0] if tables else 0

        print(f"   Tables: {table_count}")

    except Exception as e:
        print(f"   Connection: ❌ Failed ({e})")


async def test_auth_flow():
    """Test the complete authentication flow."""
    print("🧪 Testing authentication flow...")

    try:
        from app.services.auth_service import AuthService
        from app.models.auth import LoginRequest

        auth_service = AuthService()

        # Test login
        login_request = LoginRequest(email="test@manage-script.com", name="Test User")

        print("   Creating test user...")
        response = await auth_service.login(login_request, "127.0.0.1")

        print(f"   ✅ User created: {response.email}")
        print(f"   ✅ Session token: {response.session_token[:16]}...")

        # Test token validation
        print("   Validating session token...")
        session_data = await auth_service.validate_token(response.session_token)

        if session_data:
            print(f"   ✅ Token valid for user: {session_data['email']}")
        else:
            print("   ❌ Token validation failed")

        # Test logout
        print("   Testing logout...")
        logout_result = await auth_service.logout(response.email)

        if logout_result:
            print("   ✅ Logout successful")
        else:
            print("   ❌ Logout failed")

        print("🎉 Authentication flow test completed successfully!")

    except Exception as e:
        print(f"❌ Authentication flow test failed: {e}")
        import traceback

        traceback.print_exc()


def handle_test_auth():
    """Handle auth test command."""
    asyncio.run(test_auth_flow())


def handle_generate_migration():
    """Generate migration SQL file."""
    from app.db.migrations.simple_migration import SimpleMigrationGenerator

    generator = SimpleMigrationGenerator()
    print("🔄 Generating migration SQL...")

    filepath = generator.generate_and_save()
    print(f"✅ Migration SQL generated: {filepath}")
    print("⚠️  Review the SQL file before applying!")


def handle_apply_migration():
    """Apply migration (drops and recreates all tables)."""
    from app.db.migrations.simple_migration import SimpleMigrationGenerator

    print("⚠️  WARNING: This will DROP ALL TABLES and recreate them!")
    print("⚠️  ALL DATA WILL BE LOST!")

    confirm = input("Are you sure? Type 'yes' to continue: ").lower().strip()
    if confirm != "yes":
        print("❌ Migration cancelled")
        return

    generator = SimpleMigrationGenerator()
    print("🔄 Applying migration...")

    try:
        generator.generate_and_apply()
        print("✅ Migration applied successfully!")
        print("📤 Changes synced with Turso cloud database")
    except Exception as e:
        print(f"❌ Migration failed: {e}")


def main():
    """Main entry point."""
    print_banner()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    try:
        if command == "generate-migration":
            handle_generate_migration()
        elif command == "apply-migration":
            handle_apply_migration()
        elif command == "db-info":
            handle_db_info()
        elif command == "test-auth":
            handle_test_auth()
        elif command in ["help", "-h", "--help"]:
            print_help()
        else:
            print(f"❌ Unknown command: {command}")
            print_help()

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
