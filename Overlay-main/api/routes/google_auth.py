"""Google OAuth authentication routes."""

import httpx
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import jwt
from pydantic import BaseModel

from api.config import settings

router = APIRouter()


# Google OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleUserInfo(BaseModel):
    """Google user info response."""

    id: str
    email: str
    verified_email: bool = False
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expiration_hours)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_redirect_uri(request: Request) -> str:
    """Get the OAuth callback redirect URI."""
    # Use configured base URL or construct from request
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/api/auth/google/callback"


@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth login flow."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID environment variable.",
        )

    redirect_uri = get_redirect_uri(request)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
):
    """Handle Google OAuth callback."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth error: {error}",
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code",
        )

    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )

    redirect_uri = get_redirect_uri(request)

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )

        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code for tokens",
            )

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token in response",
            )

        # Get user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google",
            )

        google_user = GoogleUserInfo(**userinfo_response.json())

    # Find or create user in database
    # Note: In production, this would use proper SQLModel/Prisma models
    user_data = {
        "id": f"google_{google_user.id}",
        "email": google_user.email,
        "first_name": google_user.given_name,
        "last_name": google_user.family_name,
        "profile_image_url": google_user.picture,
        "google_id": google_user.id,
        "organization_id": "default-org",  # Assign to default org
    }

    # Create JWT token
    jwt_token = create_access_token(
        data={
            "sub": user_data["id"],
            "email": user_data["email"],
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "organization_id": user_data.get("organization_id"),
        }
    )

    # Redirect to frontend with token
    frontend_url = settings.cors_origins[0] if settings.cors_origins else "http://localhost:3000"
    return RedirectResponse(
        url=f"{frontend_url}/auth?token={jwt_token}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get("/google/url")
async def get_google_auth_url(request: Request):
    """Get the Google OAuth login URL for frontend-initiated auth."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )

    redirect_uri = get_redirect_uri(request)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {"url": auth_url}

