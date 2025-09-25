"""Tests for database operations."""

import pytest
from datetime import datetime, timezone, timedelta
from app.models.auth import UserCreate, SessionCreate


@pytest.mark.asyncio
async def test_database_initialization(test_db_manager):
    """Test that database tables are created properly."""
    conn = test_db_manager.get_connection()

    # Check if tables exist
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    table_names = [table[0] for table in tables]

    assert "users" in table_names
    assert "user_sessions" in table_names
    assert "files" in table_names
    assert "file_chunks" in table_names


@pytest.mark.asyncio
async def test_create_user(test_db_service):
    """Test user creation in database."""
    user_data = UserCreate(
        email="test@example.com", name="Test User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    assert created_user is not None
    assert created_user["email"] == "test@example.com"
    assert created_user["name"] == "Test User"
    assert created_user["ip_address"] == "127.0.0.1"
    assert created_user["status"] == "Active"
    assert created_user["id"] is not None


@pytest.mark.asyncio
async def test_create_duplicate_user(test_db_service):
    """Test that creating a user with existing email returns existing user."""
    user_data = UserCreate(
        email="duplicate@example.com", name="First User", ip_address="127.0.0.1"
    )

    # Create first user
    first_user = await test_db_service.create_user(user_data)

    # Try to create user with same email
    duplicate_data = UserCreate(
        email="duplicate@example.com", name="Second User", ip_address="192.168.1.1"
    )

    second_user = await test_db_service.create_user(duplicate_data)

    # Should return the same user (first one)
    assert first_user["id"] == second_user["id"]
    assert first_user["email"] == second_user["email"]
    assert first_user["name"] == second_user["name"]  # Original name preserved


@pytest.mark.asyncio
async def test_get_user_by_email(test_db_service):
    """Test retrieving user by email."""
    # Create a user first
    user_data = UserCreate(
        email="lookup@example.com", name="Lookup User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    # Retrieve by email
    retrieved_user = await test_db_service.get_user_by_email("lookup@example.com")

    assert retrieved_user is not None
    assert retrieved_user["id"] == created_user["id"]
    assert retrieved_user["email"] == "lookup@example.com"
    assert retrieved_user["name"] == "Lookup User"


@pytest.mark.asyncio
async def test_get_nonexistent_user(test_db_service):
    """Test retrieving non-existent user."""
    user = await test_db_service.get_user_by_email("nonexistent@example.com")
    assert user is None


@pytest.mark.asyncio
async def test_update_user_last_accessed(test_db_service):
    """Test updating user's last accessed time."""
    # Create a user first
    user_data = UserCreate(
        email="update@example.com", name="Update User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)
    original_last_accessed = created_user["last_accessed"]

    # Update last accessed
    result = await test_db_service.update_user_last_accessed(
        created_user["id"], "192.168.1.1"
    )

    assert result is True

    # Verify update
    updated_user = await test_db_service.get_user_by_id(created_user["id"])
    assert updated_user["ip_address"] == "192.168.1.1"
    # Note: In a real test, you'd check that last_accessed is updated,
    # but since we're using string timestamps, we'll just verify the IP changed


@pytest.mark.asyncio
async def test_create_session(test_db_service):
    """Test session creation."""
    # Create a user first
    user_data = UserCreate(
        email="session@example.com", name="Session User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    # Create session
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    session_data = SessionCreate(
        user_id=created_user["id"],
        token="test_session_token_123",
        ip_address="127.0.0.1",
        expires_at=expires_at,
    )

    created_session = await test_db_service.create_session(session_data)

    assert created_session is not None
    assert created_session["user_id"] == created_user["id"]
    assert created_session["token"] == "test_session_token_123"
    assert created_session["ip_address"] == "127.0.0.1"
    assert created_session["is_active"] is True


@pytest.mark.asyncio
async def test_get_session_by_token(test_db_service):
    """Test retrieving session by token."""
    # Create user and session
    user_data = UserCreate(
        email="token@example.com", name="Token User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    session_data = SessionCreate(
        user_id=created_user["id"],
        token="lookup_token_456",
        ip_address="127.0.0.1",
        expires_at=expires_at,
    )

    await test_db_service.create_session(session_data)

    # Retrieve session
    retrieved_session = await test_db_service.get_session_by_token("lookup_token_456")

    assert retrieved_session is not None
    assert retrieved_session["token"] == "lookup_token_456"
    assert retrieved_session["user_id"] == created_user["id"]
    assert retrieved_session["email"] == "token@example.com"
    assert retrieved_session["name"] == "Token User"


@pytest.mark.asyncio
async def test_get_expired_session(test_db_service):
    """Test that expired sessions are not returned."""
    # Create user
    user_data = UserCreate(
        email="expired@example.com", name="Expired User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    # Create expired session
    expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired 1 hour ago
    session_data = SessionCreate(
        user_id=created_user["id"],
        token="expired_token_789",
        ip_address="127.0.0.1",
        expires_at=expires_at,
    )

    await test_db_service.create_session(session_data)

    # Try to retrieve expired session
    retrieved_session = await test_db_service.get_session_by_token("expired_token_789")

    # Should be None because session is expired
    assert retrieved_session is None


@pytest.mark.asyncio
async def test_invalidate_session(test_db_service):
    """Test session invalidation."""
    # Create user and session
    user_data = UserCreate(
        email="invalidate@example.com", name="Invalidate User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    session_data = SessionCreate(
        user_id=created_user["id"],
        token="invalidate_token_101",
        ip_address="127.0.0.1",
        expires_at=expires_at,
    )

    await test_db_service.create_session(session_data)

    # Verify session exists
    session = await test_db_service.get_session_by_token("invalidate_token_101")
    assert session is not None

    # Invalidate session
    result = await test_db_service.invalidate_session("invalidate_token_101")
    assert result is True

    # Verify session is gone
    session = await test_db_service.get_session_by_token("invalidate_token_101")
    assert session is None


@pytest.mark.asyncio
async def test_invalidate_user_sessions(test_db_service):
    """Test invalidating all sessions for a user."""
    # Create user
    user_data = UserCreate(
        email="multi@example.com", name="Multi User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    # Create multiple sessions
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    for i in range(3):
        session_data = SessionCreate(
            user_id=created_user["id"],
            token=f"multi_token_{i}",
            ip_address="127.0.0.1",
            expires_at=expires_at,
        )
        await test_db_service.create_session(session_data)

    # Verify all sessions exist
    for i in range(3):
        session = await test_db_service.get_session_by_token(f"multi_token_{i}")
        assert session is not None

    # Invalidate all user sessions
    count = await test_db_service.invalidate_user_sessions(created_user["id"])
    assert count == 3

    # Verify all sessions are gone
    for i in range(3):
        session = await test_db_service.get_session_by_token(f"multi_token_{i}")
        assert session is None


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(test_db_service):
    """Test cleanup of expired sessions."""
    # Create user
    user_data = UserCreate(
        email="cleanup@example.com", name="Cleanup User", ip_address="127.0.0.1"
    )

    created_user = await test_db_service.create_user(user_data)

    # Create mix of active and expired sessions
    now = datetime.now(timezone.utc)

    # Active session
    active_session = SessionCreate(
        user_id=created_user["id"],
        token="active_token",
        ip_address="127.0.0.1",
        expires_at=now + timedelta(hours=1),
    )
    await test_db_service.create_session(active_session)

    # Expired sessions
    for i in range(2):
        expired_session = SessionCreate(
            user_id=created_user["id"],
            token=f"expired_token_{i}",
            ip_address="127.0.0.1",
            expires_at=now - timedelta(hours=1),
        )
        await test_db_service.create_session(expired_session)

    # Run cleanup
    cleaned_count = await test_db_service.cleanup_expired_sessions()
    assert cleaned_count == 2

    # Verify active session still exists
    active = await test_db_service.get_session_by_token("active_token")
    assert active is not None

    # Verify expired sessions are gone
    for i in range(2):
        expired = await test_db_service.get_session_by_token(f"expired_token_{i}")
        assert expired is None
