"""Authentication business logic service."""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import structlog
import secrets
import hashlib
from app.models.auth import LoginRequest, LoginResponse, UserCreate, SessionCreate
from app.services.external_apis.google_sheets import GoogleSheetsClient
from app.services.database_service import get_database_service
from app.core.exceptions import AuthenticationError

logger = structlog.get_logger()


class AuthService:
    """Authentication service handling business logic."""

    def __init__(self):
        # Initialize database service (primary storage)
        self.db_service = get_database_service()

        # Initialize Google Sheets client (backup storage)
        try:
            self.sheets_client = GoogleSheetsClient()
        except Exception as e:
            self.logger = logger.bind(service="AuthService")
            self.logger.warning(
                "Google Sheets client initialization failed", error=str(e)
            )
            self.sheets_client = None

        self.logger = logger.bind(service="AuthService")
        self._session_ttl = timedelta(hours=24)  # Sessions last 24 hours

    async def _save_to_google_sheets(
        self, user_data: Dict[str, Any], client_ip: str
    ) -> None:
        """Save user data to Google Sheets as backup."""
        if self.sheets_client is None:
            self.logger.debug("Google Sheets client not available, skipping backup")
            return

        try:
            # Check if user already exists in sheets
            existing_user = await self.sheets_client.find_user_by_email(
                user_data["email"]
            )

            if existing_user:
                # Update existing user
                current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                await self.sheets_client.update_user_status(
                    existing_user["row_index"], "Active", current_time
                )
                self.logger.debug(
                    "Updated existing user in Google Sheets", email=user_data["email"]
                )
            else:
                # Create new user in sheets
                new_id = await self.sheets_client.get_next_id()
                current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                row_data = [
                    str(new_id),
                    user_data.get("name", ""),
                    user_data["email"],
                    current_time,
                    client_ip,
                    current_time,
                    "Active",
                ]

                await self.sheets_client.append_row(row_data)
                self.logger.debug(
                    "Created new user in Google Sheets", email=user_data["email"]
                )

        except Exception as e:
            self.logger.error(
                "Failed to save to Google Sheets",
                error=str(e),
                email=user_data["email"],
            )
            # Don't raise exception - Google Sheets is backup only

    def _generate_session_token(self, email: str) -> str:
        """Generate a secure session token."""
        # Create a unique token using email + timestamp + random
        timestamp = datetime.now(timezone.utc).isoformat()
        random_part = secrets.token_urlsafe(32)
        token_data = f"{email}:{timestamp}:{random_part}"

        # Hash the token data for security
        token = hashlib.sha256(token_data.encode()).hexdigest()
        return token

    async def _create_session(self, user_data: Dict[str, Any], client_ip: str) -> str:
        """Create a new session in database and return the token."""
        token = self._generate_session_token(user_data["email"])
        expires_at = datetime.now(timezone.utc) + self._session_ttl

        session_create = SessionCreate(
            user_id=user_data["id"],
            token=token,
            ip_address=client_ip,
            expires_at=expires_at,
        )

        await self.db_service.create_session(session_create)
        self.logger.info(
            "Session created", email=user_data["email"], token=token[:8] + "..."
        )
        return token

    async def login(self, login_data: LoginRequest, client_ip: str) -> LoginResponse:
        """Process user login with database and Google Sheets integration."""
        try:
            self.logger.info(
                "Processing login request",
                email=login_data.email,
                name=login_data.name,
                client_ip=client_ip,
            )

            # 1. Check if user exists in database (primary storage)
            existing_user = await self.db_service.get_user_by_email(login_data.email)

            if existing_user:
                # User exists - update last accessed
                await self.db_service.update_user_last_accessed(
                    existing_user["id"], client_ip
                )

                self.logger.info(
                    "Existing user logged in",
                    email=login_data.email,
                    user_id=existing_user["id"],
                )

                user_data = existing_user
            else:
                # 2. Create new user in database
                user_create = UserCreate(
                    email=login_data.email, name=login_data.name, ip_address=client_ip
                )

                user_data = await self.db_service.create_user(user_create)

                self.logger.info(
                    "New user created and logged in",
                    email=login_data.email,
                    user_id=user_data["id"],
                )

            # 3. Create session in database
            session_token = await self._create_session(user_data, client_ip)

            # 4. Backup to Google Sheets (async, non-blocking)
            await self._save_to_google_sheets(user_data, client_ip)

            # 5. Return login response
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            return LoginResponse(
                status="success",
                email=login_data.email,
                ip_address=client_ip,
                timestamp=current_time,
                session_token=session_token,
            )

        except Exception as e:
            self.logger.error("Login processing failed", error=str(e))
            raise AuthenticationError(f"Login failed: {str(e)}")

    async def logout(self, email: str) -> bool:
        """Logout user and invalidate sessions."""
        try:
            # 1. Find user in database
            user = await self.db_service.get_user_by_email(email)
            if not user:
                raise AuthenticationError("User not found")

            # 2. Invalidate all sessions for this user
            sessions_invalidated = await self.db_service.invalidate_user_sessions(
                user["id"]
            )

            # 3. Update Google Sheets status (optional backup)
            if self.sheets_client:
                try:
                    sheets_user = await self.sheets_client.find_user_by_email(email)
                    if sheets_user:
                        current_time = datetime.now(timezone.utc).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        await self.sheets_client.update_user_status(
                            sheets_user["row_index"], "Inactive", current_time
                        )
                except Exception as e:
                    self.logger.error(
                        "Failed to update Google Sheets on logout", error=str(e)
                    )

            self.logger.info(
                "User logged out successfully",
                email=email,
                user_id=user["id"],
                sessions_invalidated=sessions_invalidated,
            )
            return True

        except Exception as e:
            self.logger.error("Logout failed", error=str(e))
            raise AuthenticationError(f"Logout failed: {str(e)}")

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a session token and return session data."""
        try:
            session_data = await self.db_service.get_session_by_token(token)

            if session_data:
                self.logger.debug(
                    "Token validated successfully", token=token[:8] + "..."
                )
                return {
                    "user_id": session_data["user_id"],
                    "email": session_data["email"],
                    "name": session_data["name"],
                    "session_id": session_data["id"],
                    "created_at": session_data["created_at"],
                    "last_accessed": session_data["updated_at"],
                    "expires_at": session_data["expires_at"],
                }

            self.logger.debug("Token validation failed", token=token[:8] + "...")
            return None

        except Exception as e:
            self.logger.error(
                "Token validation error", error=str(e), token=token[:8] + "..."
            )
            return None

    async def get_user_status(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user status and information."""
        try:
            user = await self.db_service.get_user_by_email(email)

            if not user:
                return None

            return {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "status": user["status"],
                "last_accessed": user["last_accessed"],
                "created_at": user["created_at"],
                "ip_address": user["ip_address"],
            }

        except Exception as e:
            self.logger.error("Failed to get user status", error=str(e))
            raise AuthenticationError(f"Failed to get user status: {str(e)}")

    async def health_check(self) -> bool:
        """Check if authentication service is healthy."""
        try:
            # Test database connection
            await self.db_service.get_user_by_email("health_check@test.com")

            # Test Google Sheets connection (optional)
            sheets_healthy = True
            if self.sheets_client:
                try:
                    sheets_healthy = await self.sheets_client.health_check()
                except Exception as e:
                    self.logger.warning(
                        "Google Sheets health check failed", error=str(e)
                    )
                    sheets_healthy = False

            self.logger.info(
                "Auth service health check completed",
                database_healthy=True,
                sheets_healthy=sheets_healthy,
            )
            return True

        except Exception as e:
            self.logger.error("Auth service health check failed", error=str(e))
            return False
