"""Pytest configuration and fixtures."""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import DatabaseManager, get_database_manager
from app.services.database_service import DatabaseService
from app.services.auth_service import AuthService


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def test_db_manager(temp_db_path):
    """Create a test database manager with temporary database."""
    # Mock the settings to use our test database
    import app.core.database

    original_get_settings = app.core.database.get_settings

    class MockSettings:
        turso_database_url = None
        turso_auth_token = None
        local_db_path = temp_db_path

    app.core.database.get_settings = lambda: MockSettings()

    # Create and initialize test database
    db_manager = DatabaseManager()
    db_manager.create_tables()

    yield db_manager

    # Restore original settings
    app.core.database.get_settings = original_get_settings
    db_manager.close()


@pytest.fixture
def test_db_service(test_db_manager):
    """Create a test database service."""
    # Mock the global database manager
    import app.services.database_service

    original_get_db_manager = app.services.database_service.get_database_manager
    app.services.database_service.get_database_manager = lambda: test_db_manager

    db_service = DatabaseService()

    yield db_service

    # Restore original function
    app.services.database_service.get_database_manager = original_get_db_manager


@pytest.fixture
def test_auth_service(test_db_service):
    """Create a test auth service with mocked dependencies."""
    # Mock the database service getter
    import app.services.auth_service

    original_get_db_service = app.services.auth_service.get_database_service
    app.services.auth_service.get_database_service = lambda: test_db_service

    # Create auth service (Google Sheets will be mocked in individual tests)
    auth_service = AuthService()

    yield auth_service

    # Restore original function
    app.services.auth_service.get_database_service = original_get_db_service


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_login_data():
    """Sample login data for testing."""
    return {"email": "test@example.com", "name": "Test User"}


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": 1,
        "email": "test@example.com",
        "name": "Test User",
        "ip_address": "127.0.0.1",
        "status": "Active",
    }
