"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_login_data():
    """Sample login data for testing."""
    return {"email": "test@example.com", "name": "Test User"}
