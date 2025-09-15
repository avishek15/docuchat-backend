"""Authentication dependencies for FastAPI."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from app.services.auth_service import AuthService

# Security scheme for Bearer token
security = HTTPBearer()

# Global AuthService instance to maintain session state
_auth_service = None


def get_auth_service() -> AuthService:
    """Get or create global AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from session token.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(current_user: dict = Depends(get_current_user)):
            return {"user": current_user}
    """
    try:
        auth_service = get_auth_service()
        token = credentials.credentials

        # Validate the token
        session_data = auth_service.validate_token(token)

        if session_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return session_data

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication dependency - returns user if authenticated, None otherwise.

    Usage:
        @router.get("/optional-protected")
        async def optional_endpoint(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                return {"authenticated": True, "user": user}
            return {"authenticated": False}
    """
    if credentials is None:
        return None

    try:
        auth_service = get_auth_service()
        token = credentials.credentials
        return auth_service.validate_token(token)
    except Exception:
        return None
