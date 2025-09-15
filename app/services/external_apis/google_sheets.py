"""Google Sheets API integration."""

import gspread
from typing import List, Dict, Any, Optional
import structlog
from app.core.config import get_settings
from app.core.exceptions import ExternalAPIError
from .base import BaseAPIClient

logger = structlog.get_logger()


class GoogleSheetsClient(BaseAPIClient):
    """Google Sheets API client."""

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self._client = None
        self._spreadsheet = None
        self._worksheet = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Google Sheets client."""
        try:
            # Check if all required Google Sheets settings are provided
            if not all(
                [
                    self.settings.google_project_id,
                    self.settings.google_private_key_id,
                    self.settings.google_private_key,
                    self.settings.google_client_email,
                    self.settings.google_sheets_id,
                ]
            ):
                raise ExternalAPIError(
                    "Google Sheets configuration incomplete. Please set all required environment variables."
                )

            # Create service account credentials from environment variables
            service_account_info = {
                "type": "service_account",
                "project_id": self.settings.google_project_id,
                "private_key_id": self.settings.google_private_key_id,
                "private_key": self.settings.google_private_key.replace(
                    "\\n", "\n"
                ).replace('"', ""),
                "client_email": self.settings.google_client_email,
                "client_id": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{self.settings.google_client_email}",
            }

            self._client = gspread.service_account_from_dict(service_account_info)
            self._spreadsheet = self._client.open_by_key(self.settings.google_sheets_id)
            self._worksheet = self._spreadsheet.worksheet(
                self.settings.google_worksheet_name
            )

            self.logger.info("Google Sheets client initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize Google Sheets client", error=str(e))
            raise ExternalAPIError(f"Failed to initialize Google Sheets: {str(e)}")

    async def append_row(self, row_data: List[str]) -> bool:
        """Append a row to the worksheet."""
        try:
            self.logger.info("Appending row to Google Sheets", row_data=row_data)
            self._worksheet.append_row(row_data)
            return True

        except Exception as e:
            self.logger.error("Failed to append row to Google Sheets", error=str(e))
            raise ExternalAPIError(f"Failed to append row: {str(e)}")

    async def get_worksheet_data(self) -> List[List[str]]:
        """Get all data from the worksheet."""
        try:
            return self._worksheet.get_all_values()
        except Exception as e:
            self.logger.error("Failed to get worksheet data", error=str(e))
            raise ExternalAPIError(f"Failed to get worksheet data: {str(e)}")

    async def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find user by email using optimized search."""
        try:
            # First try the optimized column-based search
            row_index = await self._find_row_index_by_email(email)
            if row_index == -1:
                return None

            # Get only the specific row data (much faster than getting all data)
            row_data = self._worksheet.row_values(row_index)

            return {
                "row_index": row_index,
                "id": row_data[0] if len(row_data) > 0 else "",
                "name": row_data[1] if len(row_data) > 1 else "",
                "email": row_data[2] if len(row_data) > 2 else "",
                "created_at": row_data[3] if len(row_data) > 3 else "",
                "ip_address": row_data[4] if len(row_data) > 4 else "",
                "last_accessed": row_data[5] if len(row_data) > 5 else "",
                "status": row_data[6] if len(row_data) > 6 else "",
            }
        except Exception as e:
            self.logger.error("Failed to find user by email", error=str(e))
            raise ExternalAPIError(f"Failed to find user: {str(e)}")

    async def _find_row_index_by_email(self, email: str) -> int:
        """Find the row index for a given email (optimized for large datasets)."""
        try:
            # Use batch operations to find row index more efficiently
            # Get only the email column (column C) and search for the email
            email_column = self._worksheet.col_values(3)  # Column C (1-indexed)

            for i, cell_value in enumerate(
                email_column[1:], start=2
            ):  # Skip header, start from row 2
                if cell_value.strip().lower() == email.strip().lower():
                    return i

            return -1  # Not found
        except Exception as e:
            self.logger.error("Failed to find row index", error=str(e))
            return -1

    async def update_user_status(
        self, row_index: int, status: str, last_accessed: str = None
    ) -> bool:
        """Update user status and last accessed time."""
        try:
            if last_accessed:
                # Update both status and last accessed
                # Column 7 = Status (1-indexed), Column 6 = Last Accessed (1-indexed)
                self._worksheet.update_cell(row_index, 7, status)  # Status column
                self._worksheet.update_cell(
                    row_index, 6, last_accessed
                )  # Last accessed column
            else:
                # Update only status
                self._worksheet.update_cell(row_index, 7, status)  # Status column

            self.logger.info(
                "User status updated successfully", row_index=row_index, status=status
            )
            return True
        except Exception as e:
            self.logger.error("Failed to update user status", error=str(e))
            raise ExternalAPIError(f"Failed to update user status: {str(e)}")

    async def get_next_id(self) -> int:
        """Get the next available ID for new users (optimized)."""
        try:
            # Get only the ID column (column A) instead of all data
            id_column = self._worksheet.col_values(1)  # Column A (1-indexed)

            if not id_column or len(id_column) <= 1:  # No data or only header
                return 1

            max_id = 0
            for cell_value in id_column[1:]:  # Skip header
                if cell_value and cell_value.strip().isdigit():
                    max_id = max(max_id, int(cell_value.strip()))

            return max_id + 1
        except Exception as e:
            self.logger.error("Failed to get next ID", error=str(e))
            raise ExternalAPIError(f"Failed to get next ID: {str(e)}")

    async def health_check(self) -> bool:
        """Check if Google Sheets is accessible."""
        try:
            # Try to access the worksheet
            self._worksheet.get_all_values()
            return True
        except Exception as e:
            self.logger.error("Google Sheets health check failed", error=str(e))
            return False
