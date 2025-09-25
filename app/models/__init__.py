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
    FileChunk,
    FileUploadRequest,
    FileUploadResponse,
    FileInfo,
    FileListResponse,
    FileDeleteResponse,
    FileRead,
    FileCreate,
    FileUpdate,
    ChunkCreate,
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