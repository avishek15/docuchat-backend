"""Authentication API endpoints."""

from fastapi import APIRouter, Request, HTTPException, status, Depends
import structlog
from app.models import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    UserStatusResponse,
    ErrorResponse,
)
from app.core.exceptions import AuthenticationError
from app.core.auth import get_current_user, get_auth_service

logger = structlog.get_logger()
router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def login(request: Request, login_data: LoginRequest):
    """User login endpoint."""
    try:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Convert schema to model
        login_request = LoginRequest(email=login_data.email, name=login_data.name)

        # Process login
        auth_service = get_auth_service()
        result = await auth_service.login(login_request, client_ip)

        # Return the result directly (it's already a LoginResponse)
        return result

    except AuthenticationError as e:
        logger.error("Authentication error", error=str(e))
        # Check if it's a rate limiting error
        if "Too many login attempts" in str(e):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:
        logger.error("Unexpected error during login", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def logout(logout_data: LogoutRequest, request: Request):
    """User logout endpoint."""
    try:
        auth_service = get_auth_service()

        # Check if this is a token-based logout (user is authenticated)
        # If so, we can invalidate just that specific session
        token = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        success = await auth_service.logout(logout_data.email, token)

        if success:
            return LogoutResponse(
                status="success", message="User logged out successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Logout failed"
            )

    except AuthenticationError as e:
        logger.error("Authentication error during logout", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except Exception as e:
        logger.error("Unexpected error during logout", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/logout-token",
    response_model=LogoutResponse,
    responses={
        401: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def logout_with_token(current_user: dict = Depends(get_current_user)):
    """Secure logout endpoint that requires authentication."""
    try:
        auth_service = get_auth_service()
        email = current_user.get("email")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User email not found in session",
            )

        success = await auth_service.logout(email)

        if success:
            return LogoutResponse(
                status="success",
                message="User logged out successfully (token invalidated)",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Logout failed"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during token logout", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/status/{email}",
    response_model=UserStatusResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_user_status(email: str):
    """Get user status and session information."""
    try:
        auth_service = get_auth_service()
        user_status = await auth_service.get_user_status(email)

        if user_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserStatusResponse(**user_status)

    except AuthenticationError as e:
        logger.error("Authentication error getting user status", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error getting user status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    return {
        "user": current_user,
        "authenticated": True,
        "message": "You are successfully authenticated!",
    }


@router.get("/validate")
async def validate_session(current_user: dict = Depends(get_current_user)):
    """Validate session token and return validation status."""
    return {
        "valid": True,
        "user_id": current_user.get("user_id"),
        "email": current_user.get("email"),
        "name": current_user.get("name"),
        "session_id": current_user.get("session_id"),
        "created_at": current_user.get("created_at"),
        "expires_at": current_user.get("expires_at"),
        "last_accessed": current_user.get("last_accessed"),
    }


@router.get(
    "/user-info",
    response_model=UserStatusResponse,
    responses={401: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_user_info(current_user: dict = Depends(get_current_user)):
    """Get authenticated user's detailed information."""
    try:
        auth_service = get_auth_service()
        email = current_user.get("email")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User email not found in session",
            )

        # Get detailed user information from Google Sheets
        user_status = await auth_service.get_user_status(email)

        if user_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserStatusResponse(**user_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user info", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        auth_service = get_auth_service()
        is_healthy = await auth_service.health_check()

        if is_healthy:
            return {"status": "healthy"}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unhealthy",
            )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health check failed",
        )
