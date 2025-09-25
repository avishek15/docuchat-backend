"""Tests for authentication service with database integration."""

import pytest
from unittest.mock import AsyncMock, patch
from app.models.auth import LoginRequest


@pytest.mark.asyncio
async def test_auth_service_initialization(test_auth_service):
    """Test that auth service initializes properly."""
    assert test_auth_service is not None
    assert test_auth_service.db_service is not None


@pytest.mark.asyncio
async def test_login_new_user(test_auth_service, sample_login_data):
    """Test login flow for a new user."""
    with patch.object(test_auth_service, 'sheets_client', None):
        # Mock the _save_to_google_sheets method
        with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
            login_request = LoginRequest(**sample_login_data)
            
            response = await test_auth_service.login(login_request, "127.0.0.1")
            
            assert response.status == "success"
            assert response.email == sample_login_data["email"]
            assert response.ip_address == "127.0.0.1"
            assert response.session_token is not None
            assert len(response.session_token) == 64  # SHA256 hash length


@pytest.mark.asyncio
async def test_login_existing_user(test_auth_service, sample_login_data):
    """Test login flow for an existing user."""
    with patch.object(test_auth_service, 'sheets_client', None):
        with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
            login_request = LoginRequest(**sample_login_data)
            
            # First login - creates user
            first_response = await test_auth_service.login(login_request, "127.0.0.1")
            
            # Second login - existing user
            second_response = await test_auth_service.login(login_request, "192.168.1.1")
            
            assert first_response.email == second_response.email
            assert first_response.session_token != second_response.session_token  # Different sessions
            assert second_response.ip_address == "192.168.1.1"


@pytest.mark.asyncio
async def test_login_with_google_sheets_backup(test_auth_service, sample_login_data):
    """Test login with Google Sheets backup enabled."""
    # Mock Google Sheets client
    mock_sheets_client = AsyncMock()
    mock_sheets_client.find_user_by_email.return_value = None
    mock_sheets_client.get_next_id.return_value = 1
    mock_sheets_client.append_row.return_value = True
    
    test_auth_service.sheets_client = mock_sheets_client
    
    login_request = LoginRequest(**sample_login_data)
    response = await test_auth_service.login(login_request, "127.0.0.1")
    
    assert response.status == "success"
    assert response.session_token is not None
    
    # Verify Google Sheets was called
    mock_sheets_client.find_user_by_email.assert_called_once()
    mock_sheets_client.get_next_id.assert_called_once()
    mock_sheets_client.append_row.assert_called_once()


@pytest.mark.asyncio
async def test_validate_token_valid(test_auth_service, sample_login_data):
    """Test token validation with valid token."""
    with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
        # Login to get a valid token
        login_request = LoginRequest(**sample_login_data)
        login_response = await test_auth_service.login(login_request, "127.0.0.1")
        
        # Validate the token
        session_data = await test_auth_service.validate_token(login_response.session_token)
        
        assert session_data is not None
        assert session_data["email"] == sample_login_data["email"]
        assert session_data["name"] == sample_login_data["name"]
        assert session_data["user_id"] is not None


@pytest.mark.asyncio
async def test_validate_token_invalid(test_auth_service):
    """Test token validation with invalid token."""
    session_data = await test_auth_service.validate_token("invalid_token_123")
    assert session_data is None


@pytest.mark.asyncio
async def test_logout_user(test_auth_service, sample_login_data):
    """Test user logout functionality."""
    with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
        # Login first
        login_request = LoginRequest(**sample_login_data)
        login_response = await test_auth_service.login(login_request, "127.0.0.1")
        
        # Verify token is valid
        session_data = await test_auth_service.validate_token(login_response.session_token)
        assert session_data is not None
        
        # Logout
        result = await test_auth_service.logout(sample_login_data["email"])
        assert result is True
        
        # Verify token is now invalid
        session_data = await test_auth_service.validate_token(login_response.session_token)
        assert session_data is None


@pytest.mark.asyncio
async def test_logout_nonexistent_user(test_auth_service):
    """Test logout with non-existent user."""
    with pytest.raises(Exception):  # Should raise AuthenticationError
        await test_auth_service.logout("nonexistent@example.com")


@pytest.mark.asyncio
async def test_get_user_status_existing(test_auth_service, sample_login_data):
    """Test getting user status for existing user."""
    with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
        # Create user by logging in
        login_request = LoginRequest(**sample_login_data)
        await test_auth_service.login(login_request, "127.0.0.1")
        
        # Get user status
        user_status = await test_auth_service.get_user_status(sample_login_data["email"])
        
        assert user_status is not None
        assert user_status["email"] == sample_login_data["email"]
        assert user_status["name"] == sample_login_data["name"]
        assert user_status["status"] == "Active"
        assert user_status["ip_address"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_get_user_status_nonexistent(test_auth_service):
    """Test getting user status for non-existent user."""
    user_status = await test_auth_service.get_user_status("nonexistent@example.com")
    assert user_status is None


@pytest.mark.asyncio
async def test_health_check(test_auth_service):
    """Test auth service health check."""
    result = await test_auth_service.health_check()
    assert result is True


@pytest.mark.asyncio
async def test_multiple_sessions_same_user(test_auth_service, sample_login_data):
    """Test that a user can have multiple active sessions."""
    with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
        login_request = LoginRequest(**sample_login_data)
        
        # Create multiple sessions
        session1 = await test_auth_service.login(login_request, "127.0.0.1")
        session2 = await test_auth_service.login(login_request, "192.168.1.1")
        
        # Both sessions should be valid
        data1 = await test_auth_service.validate_token(session1.session_token)
        data2 = await test_auth_service.validate_token(session2.session_token)
        
        assert data1 is not None
        assert data2 is not None
        assert data1["email"] == data2["email"]
        assert data1["session_id"] != data2["session_id"]


@pytest.mark.asyncio
async def test_logout_invalidates_all_sessions(test_auth_service, sample_login_data):
    """Test that logout invalidates all sessions for a user."""
    with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
        login_request = LoginRequest(**sample_login_data)
        
        # Create multiple sessions
        session1 = await test_auth_service.login(login_request, "127.0.0.1")
        session2 = await test_auth_service.login(login_request, "192.168.1.1")
        
        # Verify both sessions are valid
        data1 = await test_auth_service.validate_token(session1.session_token)
        data2 = await test_auth_service.validate_token(session2.session_token)
        assert data1 is not None
        assert data2 is not None
        
        # Logout
        await test_auth_service.logout(sample_login_data["email"])
        
        # Verify both sessions are invalid
        data1 = await test_auth_service.validate_token(session1.session_token)
        data2 = await test_auth_service.validate_token(session2.session_token)
        assert data1 is None
        assert data2 is None


@pytest.mark.asyncio
async def test_session_token_uniqueness(test_auth_service, sample_login_data):
    """Test that session tokens are unique."""
    with patch.object(test_auth_service, '_save_to_google_sheets', new_callable=AsyncMock):
        login_request = LoginRequest(**sample_login_data)
        
        # Generate multiple tokens
        tokens = []
        for _ in range(5):
            response = await test_auth_service.login(login_request, "127.0.0.1")
            tokens.append(response.session_token)
        
        # Verify all tokens are unique
        assert len(set(tokens)) == len(tokens)


@pytest.mark.asyncio 
async def test_google_sheets_failure_doesnt_break_login(test_auth_service, sample_login_data):
    """Test that Google Sheets failure doesn't prevent login."""
    # Mock Google Sheets client to fail
    mock_sheets_client = AsyncMock()
    mock_sheets_client.find_user_by_email.side_effect = Exception("Google Sheets error")
    
    test_auth_service.sheets_client = mock_sheets_client
    
    # Login should still work
    login_request = LoginRequest(**sample_login_data)
    response = await test_auth_service.login(login_request, "127.0.0.1")
    
    assert response.status == "success"
    assert response.session_token is not None
    
    # Token should be valid
    session_data = await test_auth_service.validate_token(response.session_token)
    assert session_data is not None

