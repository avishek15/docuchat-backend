"""Models package for DocuChat backend."""

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
    User,
    UserSession,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    UserStatusResponse,
    UserPublic,
    UserRead,
    UserCreate,
    UserUpdate,
    SessionCreate,
)

# File management models
from .files import (
    File,
    FileUploadRequest,
    FileUploadResponse,
    FileInfo,
    FileListResponse,
    FileDeleteResponse,
    FileCountResponse,
    FileRead,
    FileCreate,
    FileUpdate,
)

__all__ = [
    # Base models
    "TimestampMixin",
    "BaseResponse",
    "SuccessResponse",
    "ErrorResponse",
    "HealthResponse",
    # Authentication models
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
    # File management models
    "File",
    "FileUploadRequest",
    "FileUploadResponse",
    "FileInfo",
    "FileListResponse",
    "FileDeleteResponse",
    "FileCountResponse",
    "FileRead",
    "FileCreate",
    "FileUpdate",
]
