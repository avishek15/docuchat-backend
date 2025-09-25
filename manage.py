#!/usr/bin/env python3
"""Management script for DocuChat backend operations."""

import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.migrations import MigrationRunner
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

Database Management:
  migrate                 Run all pending migrations
  migrate <version>       Run migrations up to specific version
  rollback <version>      Rollback to specific migration version
  migration-status        Show current migration status
  db-info                 Show database connection info

Examples:
  python manage.py migrate
  python manage.py migrate 003
  python manage.py rollback 002
  python manage.py migration-status
  python manage.py db-info
""")


def handle_migrate(args):
    """Handle migration commands."""
    runner = MigrationRunner()

    if len(args) == 0:
        # Run all migrations
        print("🔄 Running all pending migrations...")
        runner.run_migrations()
        print("✅ All migrations completed successfully!")
    else:
        # Run migrations up to specific version
        target_version = args[0]
        print(f"🔄 Running migrations up to version {target_version}...")
        runner.run_migrations(target_version)
        print(f"✅ Migrations completed up to version {target_version}!")


def handle_rollback(args):
    """Handle rollback commands."""
    if len(args) == 0:
        print("❌ Error: Target version required for rollback")
        print("Usage: python manage.py rollback <version>")
        return

    target_version = args[0]
    runner = MigrationRunner()

    print(f"🔄 Rolling back to version {target_version}...")
    print("⚠️  This will undo migrations and may result in data loss!")

    confirm = input("Are you sure? (y/N): ").lower().strip()
    if confirm not in ["y", "yes"]:
        print("❌ Rollback cancelled")
        return

    runner.rollback_migration(target_version)
    print(f"✅ Rollback to version {target_version} completed!")


def handle_migration_status():
    """Handle migration status command."""
    runner = MigrationRunner()
    status = runner.get_migration_status()

    print("📊 Migration Status:")
    print(f"   Applied: {status['applied_migrations']}/{status['total_migrations']}")
    print(f"   Pending: {status['pending_migrations']}")
    print()

    print("📋 Migrations:")
    for migration in status["migrations"]:
        status_icon = "✅" if migration["applied"] else "⏳"
        print(f"   {status_icon} {migration['version']}: {migration['description']}")


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


def main():
    """Main entry point."""
    print_banner()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    try:
        if command == "migrate":
            handle_migrate(args)
        elif command == "rollback":
            handle_rollback(args)
        elif command == "migration-status":
            handle_migration_status()
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
