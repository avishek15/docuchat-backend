"""Authentication database service for user and session operations."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import update, delete
import structlog
from app.models.auth import User, UserSession, UserCreate, UserUpdate, SessionCreate
from .base import BaseDatabaseService

logger = structlog.get_logger()


class AuthDatabaseService(BaseDatabaseService):
    """Database service for authentication-related operations."""

    def __init__(self):
        super().__init__()
        self.logger = logger.bind(service="AuthDatabaseService")

    # User operations
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        try:
            with self._get_session() as session:
                result = session.query(User).filter(User.email == email).first()
                return result
        except Exception as e:
            self.logger.error("Failed to get user by email", email=email, error=str(e))
            raise

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            with self._get_session() as session:
                result = session.query(User).filter(User.id == user_id).first()
                return result
        except Exception as e:
            self.logger.error("Failed to get user by ID", user_id=user_id, error=str(e))
            raise

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        try:
            with self._get_session() as session:
                user = User(
                    email=user_data.email,
                    name=user_data.name,
                    ip_address=user_data.ip_address,
                    status="Active",  # Default status for new users
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(user)
                session.commit()
                session.refresh(user)

                self.logger.info(
                    "User created successfully", user_id=user.id, email=user.email
                )
                return user
        except Exception as e:
            self.logger.error("Failed to create user", error=str(e))
            raise

    async def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """Update user information."""
        try:
            with self._get_session() as session:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return None

                # Update fields
                if user_data.name is not None:
                    user.name = user_data.name
                if user_data.status is not None:
                    user.status = user_data.status
                if user_data.ip_address is not None:
                    user.ip_address = user_data.ip_address

                user.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(user)

                self.logger.info("User updated successfully", user_id=user_id)
                return user
        except Exception as e:
            self.logger.error("Failed to update user", user_id=user_id, error=str(e))
            raise

    async def update_user_last_accessed(self, user_id: int, ip_address: str) -> bool:
        """Update user's last accessed timestamp."""
        try:
            with self._get_session() as session:
                session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        last_accessed=datetime.now(timezone.utc),
                        ip_address=ip_address,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                session.commit()
                return True
        except Exception as e:
            self.logger.error(
                "Failed to update user last accessed", user_id=user_id, error=str(e)
            )
            raise

    # Session operations
    async def create_session(self, session_data: SessionCreate) -> UserSession:
        """Create a new user session."""
        try:
            with self._get_session() as session:
                user_session = UserSession(
                    user_id=session_data.user_id,
                    token=session_data.token,
                    ip_address=session_data.ip_address,
                    expires_at=session_data.expires_at,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(user_session)
                session.commit()
                session.refresh(user_session)

                self.logger.info(
                    "Session created successfully", user_id=session_data.user_id
                )
                return user_session
        except Exception as e:
            self.logger.error("Failed to create session", error=str(e))
            raise

    async def get_session_by_token(self, token: str) -> Optional[UserSession]:
        """Get session by token."""
        try:
            with self._get_session() as session:
                result = (
                    session.query(UserSession)
                    .filter(UserSession.token == token, UserSession.is_active == True)
                    .first()
                )
                return result
        except Exception as e:
            self.logger.error("Failed to get session by token", error=str(e))
            raise

    async def invalidate_session(self, session_id: int) -> bool:
        """Invalidate a specific session."""
        try:
            with self._get_session() as session:
                session.execute(
                    update(UserSession)
                    .where(UserSession.id == session_id)
                    .values(is_active=False, updated_at=datetime.now(timezone.utc))
                )
                session.commit()
                return True
        except Exception as e:
            self.logger.error(
                "Failed to invalidate session", session_id=session_id, error=str(e)
            )
            raise

    async def invalidate_user_sessions(self, user_id: int) -> bool:
        """Invalidate all sessions for a user."""
        try:
            with self._get_session() as session:
                session.execute(
                    update(UserSession)
                    .where(UserSession.user_id == user_id)
                    .values(is_active=False, updated_at=datetime.now(timezone.utc))
                )
                session.commit()

                self.logger.info("All user sessions invalidated", user_id=user_id)
                return True
        except Exception as e:
            self.logger.error(
                "Failed to invalidate user sessions", user_id=user_id, error=str(e)
            )
            raise

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        try:
            current_time = datetime.now(timezone.utc)
            with self._get_session() as session:
                # Get count of expired sessions
                expired_count = (
                    session.query(UserSession)
                    .filter(
                        UserSession.expires_at < current_time,
                        UserSession.is_active == True,
                    )
                    .count()
                )

                # Mark expired sessions as inactive
                session.execute(
                    update(UserSession)
                    .where(UserSession.expires_at < current_time)
                    .values(is_active=False, updated_at=datetime.now(timezone.utc))
                )
                session.commit()

                # Hard cleanup: delete all inactive sessions
                delete_result = session.execute(
                    delete(UserSession).where(UserSession.is_active == False)
                )
                session.commit()

                total_cleaned = expired_count + (delete_result.rowcount or 0)
                self.logger.info(
                    "Expired/inactive sessions cleaned up",
                    expired_marked=expired_count,
                    inactive_deleted=delete_result.rowcount or 0,
                    count=total_cleaned,
                )
                return total_cleaned
        except Exception as e:
            self.logger.error("Failed to cleanup expired sessions", error=str(e))
            raise
