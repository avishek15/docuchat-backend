"""Standard response schemas."""

from typing import Any, Optional
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """Standard success response."""

    status: str = "success"
    data: Optional[Any] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    status: str = "error"
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None
