"""Tests for authentication endpoints."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_login_endpoint(client, sample_login_data):
    """Test login endpoint with mocked external service."""
    with patch("app.services.auth_service.GoogleSheetsClient") as mock_sheets:
        mock_instance = AsyncMock()
        mock_sheets.return_value = mock_instance
        mock_instance.append_row.return_value = True

        response = client.post("/api/v1/auth/login", json=sample_login_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["email"] == sample_login_data["email"]
