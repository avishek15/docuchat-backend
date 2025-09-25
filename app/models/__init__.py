"""Unified SQLModel classes for DocuChat backend."""

# Base models
from .base import (
    TimestampMixin,
    BaseResponse,
    SuccessResponse,
    ErrorResponse,
    HealthResponse,
)

# Authentication models
from .auth import (
    # Database models
    User,
    UserSession,
    # Request/Response models
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    UserStatusResponse,
    UserPublic,
    # CRUD models
    UserRead,
    UserCreate,
    UserUpdate,
    SessionCreate,
)

# File models
from .files import (
    # Database models
    File,
    FileChunk,
    # Request/Response models
    FileUploadRequest,
    FileUploadResponse,
    FileInfo,
    FileListResponse,
    FileDeleteResponse,
    # CRUD models
    FileRead,
    FileCreate,
    FileUpdate,
    ChunkCreate,
)

# Export all models for easy importing
__all__ = [
    # Base
    "TimestampMixin",
    "BaseResponse",
    "SuccessResponse",
    "ErrorResponse",
    "HealthResponse",
    # Auth
    "User",
    "UserSession",
    "LoginRequest",
    "LoginResponse",
    "LogoutRequest",
    "LogoutResponse",
    "UserStatusResponse",
    "UserPublic",
    "UserRead",
    "UserCreate",
    "UserUpdate",
    "SessionCreate",
    # Files
    "File",
    "FileChunk",
    "FileUploadRequest",
    "FileUploadResponse",
    "FileInfo",
    "FileListResponse",
    "FileDeleteResponse",
    "FileRead",
    "FileCreate",
    "FileUpdate",
    "ChunkCreate",
]
