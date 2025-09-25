"""Authentication SQLModel classes."""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import EmailStr
from .base import TimestampMixin, BaseResponse


# Database Models (table=True)


class User(TimestampMixin, table=True):
    """User database model."""

    __tablename__ = "users"

    id: Optional[int] = Field(primary_key=True, description="User ID")
    email: str = Field(unique=True, index=True, description="User email address")
    name: Optional[str] = Field(
        default=None, max_length=255, description="User full name"
    )
    ip_address: Optional[str] = Field(default=None, description="Last known IP address")
    status: str = Field(default="Active", description="User status (Active/Inactive)")
    last_accessed: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last access timestamp",
    )


class UserSession(TimestampMixin, table=True):
    """User session database model."""

    __tablename__ = "user_sessions"

    id: Optional[int] = Field(primary_key=True, description="Session ID")
    user_id: int = Field(foreign_key="users.id", description="User ID")
    token: str = Field(unique=True, index=True, description="Session token")
    ip_address: str = Field(description="IP address of the session")
    expires_at: datetime = Field(description="Session expiration time")
    is_active: bool = Field(default=True, description="Whether session is active")


# Request/Response Models (table=False, default)


class LoginRequest(SQLModel):
    """Login request model."""

    email: EmailStr = Field(description="User email address")
    name: Optional[str] = Field(
        default=None, max_length=255, description="User full name"
    )


class LoginResponse(BaseResponse):
    """Login response model."""

    status: str = Field(default="success", description="Login status")
    email: str = Field(description="User email address")
    ip_address: str = Field(description="Client IP address")
    timestamp: str = Field(description="Login timestamp")
    session_token: Optional[str] = Field(default=None, description="Session token")


class LogoutRequest(SQLModel):
    """Logout request model."""

    email: str = Field(description="User email address")


class LogoutResponse(BaseResponse):
    """Logout response model."""

    status: str = Field(default="success", description="Logout status")
    message: str = Field(description="Logout message")


class UserStatusResponse(BaseResponse):
    """User status response model."""

    status: str = Field(default="success", description="Response status")
    user: "UserPublic" = Field(description="User information")


class UserPublic(SQLModel):
    """Public user information (no sensitive data)."""

    id: int = Field(description="User ID")
    email: str = Field(description="User email address")
    name: Optional[str] = Field(description="User full name")
    status: str = Field(description="User status")
    created_at: datetime = Field(description="Account creation date")
    last_accessed: Optional[datetime] = Field(description="Last access time")


# Read Models (for database queries)


class UserRead(User):
    """User read model with all fields."""

    pass


class UserCreate(SQLModel):
    """User creation model."""

    email: str = Field(description="User email address")
    name: Optional[str] = Field(
        default=None, max_length=255, description="User full name"
    )
    ip_address: Optional[str] = Field(default=None, description="IP address")


class UserUpdate(SQLModel):
    """User update model."""

    name: Optional[str] = Field(
        default=None, max_length=255, description="User full name"
    )
    status: Optional[str] = Field(default=None, description="User status")
    last_accessed: Optional[datetime] = Field(
        default=None, description="Last access time"
    )
    ip_address: Optional[str] = Field(default=None, description="IP address")


class SessionCreate(SQLModel):
    """Session creation model."""

    user_id: int = Field(description="User ID")
    token: str = Field(description="Session token")
    ip_address: str = Field(description="IP address")
    expires_at: datetime = Field(description="Expiration time")
