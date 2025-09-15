"""Base model classes."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default=None)


class BaseResponse(BaseModel):
    """Base response model."""

    status: str
    message: Optional[str] = None
    error_code: Optional[str] = None


class ErrorResponse(BaseResponse):
    """Error response model."""

    status: str = "error"
    details: Optional[dict] = None
