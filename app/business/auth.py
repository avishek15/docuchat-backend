"""Authentication business logic manager."""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import secrets
import hashlib
import structlog

logger = structlog.get_logger()


class AuthManager:
    """Authentication business logic manager.

    Handles complex authentication logic like session management,
    token generation, caching, etc. This is separate from database
    operations to keep business logic isolated.
    """

    def __init__(self):
        self.logger = logger.bind(service="AuthManager")

        # In-memory cache for user data (expires after 5 minutes)
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=5)

        # Session token management
        self._active_sessions: Dict[str, Dict[str, Any]] = {}  # token -> session_data
        self._session_expiry: Dict[str, datetime] = {}
        self._session_ttl = timedelta(hours=24)  # Sessions last 24 hours

    def generate_session_token(self, email: str) -> str:
        """Generate a secure session token."""
        # Create a unique token using email + timestamp + random
        timestamp = datetime.now(timezone.utc).isoformat()
        random_part = secrets.token_urlsafe(32)
        token_data = f"{email}:{timestamp}:{random_part}"

        # Hash the token data for security
        token = hashlib.sha256(token_data.encode()).hexdigest()
        return token

    def create_session(self, email: str, user_data: Dict[str, Any]) -> str:
        """Create a new session and return the token."""
        token = self.generate_session_token(email)
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

    def validate_session_token(self, token: str) -> Optional[Dict[str, Any]]:
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

    def invalidate_session(self, token: str) -> bool:
        """Invalidate a session token."""
        if token in self._active_sessions:
            del self._active_sessions[token]
        if token in self._session_expiry:
            del self._session_expiry[token]
        self.logger.info("Session invalidated", token=token[:8] + "...")
        return True

    def invalidate_user_sessions(self, email: str) -> int:
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

    def get_cached_user(self, email: str) -> Optional[Dict[str, Any]]:
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

    def cache_user(self, email: str, user_data: Dict[str, Any]) -> None:
        """Cache user data with expiry."""
        self._user_cache[email] = user_data
        self._cache_expiry[email] = datetime.now(timezone.utc) + self._cache_ttl
        self.logger.debug("User data cached", email=email)

    def invalidate_user_cache(self, email: str) -> None:
        """Invalidate user cache (used after updates)."""
        if email in self._user_cache:
            del self._user_cache[email]
        if email in self._cache_expiry:
            del self._cache_expiry[email]
        self.logger.debug("User cache invalidated", email=email)

    def calculate_session_expiry(self) -> datetime:
        """Calculate when a new session should expire."""
        return datetime.now(timezone.utc) + self._session_ttl

    def is_session_expired(self, expires_at: datetime) -> bool:
        """Check if a session timestamp is expired."""
        return datetime.now(timezone.utc) > expires_at

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions from memory. Returns count of cleaned sessions."""
        current_time = datetime.now(timezone.utc)
        expired_tokens = []

        for token, expiry_time in self._session_expiry.items():
            if current_time > expiry_time:
                expired_tokens.append(token)

        for token in expired_tokens:
            if token in self._active_sessions:
                del self._active_sessions[token]
            if token in self._session_expiry:
                del self._session_expiry[token]

        if expired_tokens:
            self.logger.info("Cleaned up expired sessions", count=len(expired_tokens))

        return len(expired_tokens)
