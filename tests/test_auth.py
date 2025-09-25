"""Tests for authentication endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
import tempfile
import os


@pytest.fixture
def mock_database_for_endpoints():
    """Mock database for endpoint tests."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name

    # Mock the database manager to use temp file
    with patch("app.core.database.get_settings") as mock_settings:
        mock_settings.return_value.turso_database_url = None
        mock_settings.return_value.turso_auth_token = None
        mock_settings.return_value.local_db_path = temp_path

        # Initialize database
        from app.core.database import init_database

        init_database()

        yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_login_endpoint_new_user(
    client, sample_login_data, mock_database_for_endpoints
):
    """Test login endpoint for new user."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        # Mock Google Sheets client
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.find_user_by_email.return_value = None
        mock_instance.get_next_id.return_value = 1
        mock_instance.append_row.return_value = True

        response = client.post("/api/v1/auth/login", json=sample_login_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["email"] == sample_login_data["email"]
        assert "session_token" in data
        assert data["session_token"] is not None


@pytest.mark.asyncio
async def test_login_endpoint_existing_user(
    client, sample_login_data, mock_database_for_endpoints
):
    """Test login endpoint for existing user."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.find_user_by_email.return_value = None
        mock_instance.get_next_id.return_value = 1
        mock_instance.append_row.return_value = True

        # First login
        response1 = client.post("/api/v1/auth/login", json=sample_login_data)
        assert response1.status_code == 200

        # Second login (existing user)
        response2 = client.post("/api/v1/auth/login", json=sample_login_data)
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["email"] == data2["email"]
        assert data1["session_token"] != data2["session_token"]  # Different sessions


@pytest.mark.asyncio
async def test_logout_endpoint(client, sample_login_data, mock_database_for_endpoints):
    """Test logout endpoint."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.find_user_by_email.return_value = None
        mock_instance.get_next_id.return_value = 1
        mock_instance.append_row.return_value = True
        mock_instance.update_user_status.return_value = True

        # Login first
        login_response = client.post("/api/v1/auth/login", json=sample_login_data)
        assert login_response.status_code == 200

        # Logout
        logout_data = {"email": sample_login_data["email"]}
        logout_response = client.post("/api/v1/auth/logout", json=logout_data)

        assert logout_response.status_code == 200
        data = logout_response.json()
        assert data["status"] == "success"


@pytest.mark.asyncio
async def test_validate_token_endpoint(
    client, sample_login_data, mock_database_for_endpoints
):
    """Test token validation endpoint."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.find_user_by_email.return_value = None
        mock_instance.get_next_id.return_value = 1
        mock_instance.append_row.return_value = True

        # Login to get token
        login_response = client.post("/api/v1/auth/login", json=sample_login_data)
        assert login_response.status_code == 200

        login_data = login_response.json()
        token = login_data["session_token"]

        # Validate token
        headers = {"Authorization": f"Bearer {token}"}
        validate_response = client.get("/api/v1/auth/validate", headers=headers)

        assert validate_response.status_code == 200
        data = validate_response.json()
        assert data["email"] == sample_login_data["email"]


@pytest.mark.asyncio
async def test_validate_invalid_token(client):
    """Test validation with invalid token."""
    headers = {"Authorization": "Bearer invalid_token_123"}
    response = client.get("/api/v1/auth/validate", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token(
    client, sample_login_data, mock_database_for_endpoints
):
    """Test accessing protected endpoint with valid token."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.find_user_by_email.return_value = None
        mock_instance.get_next_id.return_value = 1
        mock_instance.append_row.return_value = True

        # Login to get token
        login_response = client.post("/api/v1/auth/login", json=sample_login_data)
        token = login_response.json()["session_token"]

        # Access protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == sample_login_data["email"]


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client):
    """Test accessing protected endpoint without token."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403  # FastAPI returns 403 for missing auth


@pytest.mark.asyncio
async def test_user_status_endpoint(
    client, sample_login_data, mock_database_for_endpoints
):
    """Test user status endpoint."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.find_user_by_email.return_value = None
        mock_instance.get_next_id.return_value = 1
        mock_instance.append_row.return_value = True

        # Login first
        login_response = client.post("/api/v1/auth/login", json=sample_login_data)
        token = login_response.json()["session_token"]

        # Get user status
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(
            f"/api/v1/auth/status?email={sample_login_data['email']}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == sample_login_data["email"]
