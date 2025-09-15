"""Base class for external API integrations."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import httpx
import structlog
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError

logger = structlog.get_logger()


class BaseAPIClient(ABC):
    """Base class for external API clients."""

    def __init__(self):
        self.settings = get_settings()
        self.timeout = self.settings.api_timeout
        self.max_retries = self.settings.max_retries
        self.logger = logger.bind(service=self.__class__.__name__)

    async def make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    self.logger.info(
                        "Making API request",
                        method=method,
                        url=url,
                        attempt=attempt + 1,
                    )

                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=data,
                        params=params,
                    )

                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPError as e:
                    self.logger.error(
                        "API request failed",
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                    )

                    if attempt == self.max_retries:
                        raise ExternalAPIError(
                            f"API request failed after {self.max_retries} retries: {str(e)}"
                        )

                    # Exponential backoff
                    await asyncio.sleep(2**attempt)

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the external service is healthy."""
        pass
