"""Authentication related models."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from .base import TimestampMixin


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=255)


class LoginResponse(BaseModel):
    """Login response model."""

    status: str = "success"
    email: str
    ip_address: str
    timestamp: str
    session_token: Optional[str] = None


class UserSession(TimestampMixin):
    """User session model."""

    email: str
    name: Optional[str] = None
    ip_address: str
    status: str = "Active"
