"""File management SQLModel classes."""

from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field
from .base import TimestampMixin, BaseResponse


# Database Models (table=True)


class File(TimestampMixin, table=True):
    """File database model."""

    __tablename__ = "files"

    id: Optional[int] = Field(primary_key=True, description="File ID")
    file_id: str = Field(unique=True, index=True, description="Unique file identifier")
    user_id: int = Field(foreign_key="users.id", description="Owner user ID")
    file_name: str = Field(description="Original file name")
    file_size: int = Field(ge=0, description="File size in bytes")
    file_type: Optional[str] = Field(
        default=None, description="MIME type or file extension"
    )
    content_hash: Optional[str] = Field(
        default=None, description="Content hash for deduplication"
    )
    storage_path: Optional[str] = Field(
        default=None, description="Storage location path"
    )
    status: str = Field(
        default="uploaded", description="File status (uploaded/processing/ready/error)"
    )
    processed_at: Optional[datetime] = Field(
        default=None, description="When file was processed"
    )


class FileChunk(TimestampMixin, table=True):
    """File chunk database model for vector storage."""

    __tablename__ = "file_chunks"

    id: Optional[int] = Field(primary_key=True, description="Chunk ID")
    file_id: int = Field(foreign_key="files.id", description="Parent file ID")
    chunk_index: int = Field(description="Chunk sequence number")
    content: str = Field(description="Chunk text content")
    embedding_id: Optional[str] = Field(
        default=None, description="Vector database embedding ID"
    )
    token_count: Optional[int] = Field(
        default=None, description="Number of tokens in chunk"
    )


# Request/Response Models (table=False, default)


class FileUploadRequest(SQLModel):
    """File upload request model."""

    file_name: str = Field(description="Name of the file")
    file_size: int = Field(ge=0, description="Size of the file in bytes")
    contents: str = Field(description="Text contents of the file")
    file_type: Optional[str] = Field(
        default=None, description="MIME type or file extension"
    )


class FileUploadResponse(BaseResponse):
    """File upload response model."""

    status: str = Field(default="success", description="Upload status")
    message: str = Field(description="Upload message")
    file_id: Optional[str] = Field(default=None, description="Unique file identifier")
    file_name: str = Field(description="File name")
    file_size: int = Field(description="File size in bytes")
    processed_at: str = Field(description="Processing timestamp")


class FileInfo(SQLModel):
    """Individual file information for lists."""

    file_id: str = Field(description="Unique file identifier")
    file_name: str = Field(description="File name")
    file_size: int = Field(description="File size in bytes")
    file_type: Optional[str] = Field(default=None, description="File type")
    uploaded_at: str = Field(description="Upload timestamp")
    status: str = Field(description="File status")


class FileListResponse(BaseResponse):
    """File list response model."""

    status: str = Field(default="success", description="Response status")
    files: List[FileInfo] = Field(description="List of files")
    total_count: int = Field(description="Total number of files")


class FileDeleteResponse(BaseResponse):
    """File deletion response model."""

    status: str = Field(default="success", description="Deletion status")
    message: str = Field(description="Deletion message")
    file_id: str = Field(description="Deleted file ID")


# Read Models (for database queries)


class FileRead(File):
    """File read model with all fields."""

    pass


class FileCreate(SQLModel):
    """File creation model."""

    file_id: str = Field(description="Unique file identifier")
    user_id: int = Field(description="Owner user ID")
    file_name: str = Field(description="File name")
    file_size: int = Field(ge=0, description="File size in bytes")
    file_type: Optional[str] = Field(default=None, description="File type")
    content_hash: Optional[str] = Field(default=None, description="Content hash")
    storage_path: Optional[str] = Field(default=None, description="Storage path")


class FileUpdate(SQLModel):
    """File update model."""

    file_name: Optional[str] = Field(default=None, description="File name")
    status: Optional[str] = Field(default=None, description="File status")
    processed_at: Optional[datetime] = Field(
        default=None, description="Processing timestamp"
    )
    storage_path: Optional[str] = Field(default=None, description="Storage path")


class ChunkCreate(SQLModel):
    """File chunk creation model."""

    file_id: int = Field(description="Parent file ID")
    chunk_index: int = Field(description="Chunk sequence number")
    content: str = Field(description="Chunk content")
    embedding_id: Optional[str] = Field(default=None, description="Embedding ID")
    token_count: Optional[int] = Field(default=None, description="Token count")
