"""Base SQLModel classes for the application."""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class TimestampMixin(SQLModel):
    """Mixin for timestamp fields."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the record was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="When the record was last updated"
    )


class BaseResponse(SQLModel):
    """Base response model for API responses."""

    status: str = Field(description="Response status")
    message: Optional[str] = Field(default=None, description="Response message")


class SuccessResponse(BaseResponse):
    """Standard success response."""

    status: str = Field(default="success", description="Success status")


class ErrorResponse(BaseResponse):
    """Standard error response."""

    status: str = Field(default="error", description="Error status")
    message: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    details: Optional[dict] = Field(
        default=None, description="Additional error details"
    )


class HealthResponse(BaseResponse):
    """Health check response."""

    status: str = Field(default="ok", description="Health status")
    version: Optional[str] = Field(default=None, description="API version")
    environment: Optional[str] = Field(default=None, description="Environment")
