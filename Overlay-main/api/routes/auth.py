"""Authentication routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt

from api.config import settings
from api.dependencies import OptionalUser
from api.schemas.auth import TokenResponse, UserLogin, UserResponse

router = APIRouter()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expiration_hours)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password (placeholder for demo)."""
    # In production, validate against database
    # For now, accept any credentials for demo purposes
    user_data = {
        "id": "demo-user-1",
        "email": credentials.email,
        "first_name": "Demo",
        "last_name": "User",
    }

    access_token = create_access_token(
        data={"sub": user_data["id"], "email": user_data["email"]}
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user=UserResponse(**user_data),
    )


@router.get("/me", response_model=UserResponse | None)
async def get_current_user_info(user: OptionalUser):
    """Get current user information."""
    if user is None:
        return None

    return UserResponse(
        id=user.get("sub", "unknown"),
        email=user.get("email", ""),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
    )


@router.post("/logout")
async def logout():
    """Logout (client should discard token)."""
    return {"message": "Logged out successfully"}


# Google OAuth routes are handled by google_auth.router
# See api/routes/google_auth.py for full implementation

