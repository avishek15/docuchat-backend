"""Authentication business logic service."""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import structlog
import secrets
import hashlib
from app.models.auth import LoginRequest, LoginResponse, UserSession
from app.services.external_apis.google_sheets import GoogleSheetsClient
from app.core.exceptions import AuthenticationError

logger = structlog.get_logger()


class AuthService:
    """Authentication service handling business logic."""

    def __init__(self):
        try:
            self.sheets_client = GoogleSheetsClient()
        except Exception as e:
            self.logger = logger.bind(service="AuthService")
            self.logger.warning(
                "Google Sheets client initialization failed", error=str(e)
            )
            self.sheets_client = None
        self.logger = logger.bind(service="AuthService")

        # In-memory cache for user data (expires after 5 minutes)
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=5)

        # Session token management
        self._active_sessions: Dict[str, Dict[str, Any]] = {}  # token -> session_data
        self._session_expiry: Dict[str, datetime] = {}
        self._session_ttl = timedelta(hours=24)  # Sessions last 24 hours

    def _get_cached_user(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user from cache if not expired."""
        if email in self._user_cache and email in self._cache_expiry:
            if datetime.now(timezone.utc) < self._cache_expiry[email]:
                self.logger.debug("User data retrieved from cache", email=email)
                return self._user_cache[email]
            else:
                # Cache expired, remove it
                del self._user_cache[email]
                del self._cache_expiry[email]
        return None

    def _cache_user(self, email: str, user_data: Dict[str, Any]) -> None:
        """Cache user data with expiry."""
        self._user_cache[email] = user_data
        self._cache_expiry[email] = datetime.now(timezone.utc) + self._cache_ttl
        self.logger.debug("User data cached", email=email)

    def _invalidate_user_cache(self, email: str) -> None:
        """Invalidate user cache (used after updates)."""
        if email in self._user_cache:
            del self._user_cache[email]
        if email in self._cache_expiry:
            del self._cache_expiry[email]
        self.logger.debug("User cache invalidated", email=email)

    def _generate_session_token(self, email: str) -> str:
        """Generate a secure session token."""
        # Create a unique token using email + timestamp + random
        timestamp = datetime.now(timezone.utc).isoformat()
        random_part = secrets.token_urlsafe(32)
        token_data = f"{email}:{timestamp}:{random_part}"

        # Hash the token data for security
        token = hashlib.sha256(token_data.encode()).hexdigest()
        return token

    def _create_session(self, email: str, user_data: Dict[str, Any]) -> str:
        """Create a new session and return the token."""
        token = self._generate_session_token(email)
        session_data = {
            "email": email,
            "user_id": user_data.get("id"),
            "name": user_data.get("name"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
        }

        self._active_sessions[token] = session_data
        self._session_expiry[token] = datetime.now(timezone.utc) + self._session_ttl

        self.logger.info("Session created", email=email, token=token[:8] + "...")
        return token

    def _validate_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate session token and return session data if valid."""
        if token not in self._active_sessions:
            return None

        if token not in self._session_expiry:
            return None

        # Check if session has expired
        if datetime.now(timezone.utc) > self._session_expiry[token]:
            # Clean up expired session
            del self._active_sessions[token]
            del self._session_expiry[token]
            return None

        # Update last accessed time
        self._active_sessions[token]["last_accessed"] = datetime.now(
            timezone.utc
        ).isoformat()
        return self._active_sessions[token]

    def _invalidate_session(self, token: str) -> bool:
        """Invalidate a session token."""
        if token in self._active_sessions:
            del self._active_sessions[token]
        if token in self._session_expiry:
            del self._session_expiry[token]
        self.logger.info("Session invalidated", token=token[:8] + "...")
        return True

    def _invalidate_user_sessions(self, email: str) -> int:
        """Invalidate all sessions for a specific user."""
        tokens_to_remove = []

        # Find all tokens for this user
        for token, session_data in self._active_sessions.items():
            if session_data.get("email") == email:
                tokens_to_remove.append(token)

        # Remove all tokens for this user
        for token in tokens_to_remove:
            if token in self._active_sessions:
                del self._active_sessions[token]
            if token in self._session_expiry:
                del self._session_expiry[token]

        self.logger.info(
            "All sessions invalidated for user",
            email=email,
            sessions_invalidated=len(tokens_to_remove),
        )
        return len(tokens_to_remove)

    async def login(self, login_data: LoginRequest, client_ip: str) -> LoginResponse:
        """Process user login and record session."""
        try:
            self.logger.info(
                "Processing login request",
                email=login_data.email,
                name=login_data.name,
                client_ip=client_ip,
            )

            if self.sheets_client is None:
                raise AuthenticationError("Google Sheets service unavailable")

            # Check cache first, then Google Sheets
            existing_user = self._get_cached_user(login_data.email)
            if existing_user is None:
                existing_user = await self.sheets_client.find_user_by_email(
                    login_data.email
                )
                # Cache the result if found
                if existing_user:
                    self._cache_user(login_data.email, existing_user)

            if existing_user:
                # User exists - update their status to Active and last accessed time
                current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                await self.sheets_client.update_user_status(
                    existing_user["row_index"], "Active", current_time
                )

                # Invalidate cache after update
                self._invalidate_user_cache(login_data.email)

                self.logger.info(
                    "Existing user logged in",
                    email=login_data.email,
                    user_id=existing_user["id"],
                )

                # Create session token for existing user
                session_token = self._create_session(login_data.email, existing_user)

                return LoginResponse(
                    status="success",
                    email=login_data.email,
                    ip_address=client_ip,
                    timestamp=current_time,
                    session_token=session_token,
                )
            else:
                # New user - create new entry
                new_id = await self.sheets_client.get_next_id()
                current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                # Create new user entry
                row_data = [
                    str(new_id),  # ID
                    login_data.name or "",  # Name
                    login_data.email,  # Email
                    current_time,  # Created At
                    client_ip,  # IP Address
                    current_time,  # Last Accessed
                    "Active",  # Status
                ]

                await self.sheets_client.append_row(row_data)

                self.logger.info(
                    "New user created and logged in",
                    email=login_data.email,
                    user_id=new_id,
                )

                # Create session token for new user
                new_user_data = {
                    "id": str(new_id),
                    "name": login_data.name or "",
                    "email": login_data.email,
                }
                session_token = self._create_session(login_data.email, new_user_data)

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

    async def _record_user_session(self, session: UserSession) -> None:
        """Record user session in Google Sheets."""
        if self.sheets_client is None:
            self.logger.warning(
                "Google Sheets client not available, skipping session recording"
            )
            return

        row_data = [
            "",  # Empty column
            session.name or "",
            session.email,
            session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            session.ip_address,
            session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            session.status,
        ]

        await self.sheets_client.append_row(row_data)
        self.logger.info("User session recorded successfully", email=session.email)

    async def logout(self, email: str) -> bool:
        """Logout user and set status to Inactive."""
        try:
            if self.sheets_client is None:
                raise AuthenticationError("Google Sheets service unavailable")

            # Find user by email (check cache first)
            user = self._get_cached_user(email)
            if user is None:
                user = await self.sheets_client.find_user_by_email(email)
                if user:
                    self._cache_user(email, user)

            if not user:
                raise AuthenticationError("User not found")

            # Update status to Inactive
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            await self.sheets_client.update_user_status(
                user["row_index"], "Inactive", current_time
            )

            # Invalidate cache after update
            self._invalidate_user_cache(email)

            # Invalidate all sessions for this user
            self._invalidate_user_sessions(email)

            self.logger.info(
                "User logged out successfully", email=email, user_id=user["id"]
            )
            return True

        except Exception as e:
            self.logger.error("Logout failed", error=str(e))
            raise AuthenticationError(f"Logout failed: {str(e)}")

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a session token and return user session data."""
        return self._validate_session_token(token)

    async def get_user_status(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user status and session information."""
        try:
            if self.sheets_client is None:
                raise AuthenticationError("Google Sheets service unavailable")

            # Check cache first
            user = self._get_cached_user(email)
            if user is None:
                user = await self.sheets_client.find_user_by_email(email)
                if user:
                    self._cache_user(email, user)

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
            if self.sheets_client is None:
                self.logger.warning(
                    "Google Sheets client not available for health check"
                )
                return (
                    True  # Service is healthy even if external service is not available
                )
            return await self.sheets_client.health_check()
        except Exception as e:
            self.logger.error("Auth service health check failed", error=str(e))
            return False
