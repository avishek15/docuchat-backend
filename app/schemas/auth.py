"""Authentication schemas for API responses."""

from typing import Optional
from pydantic import BaseModel


class LoginSchema(BaseModel):
    """Login request schema."""

    email: str
    name: Optional[str] = None


class LoginResponseSchema(BaseModel):
    """Login response schema."""

    status: str
    email: str
    ip: str
    session_token: Optional[str] = None


class LogoutSchema(BaseModel):
    """Logout request schema."""

    email: str


class LogoutResponseSchema(BaseModel):
    """Logout response schema."""

    status: str
    message: str


class UserStatusSchema(BaseModel):
    """User status response schema."""

    id: str
    name: str
    email: str
    status: str
    last_accessed: str
    created_at: str
    ip_address: str
