"""Authentication routes."""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from sqlmodel import select

from api.config import settings
from api.dependencies import OptionalUser, SessionDep
from api.models import Organization, User, generate_cuid
from api.schemas.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    # Bcrypt has a 72-byte limit
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expiration_hours)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, session: SessionDep):
    """Register a new user."""
    # Check if user already exists
    statement = select(User).where(User.email == user_data.email, User.deleted_at.is_(None))
    existing_user = session.exec(statement).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    # Create default organization for new user
    org = Organization(
        id=generate_cuid(),
        name=f"{user_data.email.split('@')[0]}'s Organization",
        slug=user_data.email.split('@')[0].lower().replace(' ', '-'),
    )
    session.add(org)
    session.commit()

    # Create user
    user = User(
        id=generate_cuid(),
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        organization_id=org.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Generate access token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "organization_id": user.organization_id,
        }
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, session: SessionDep):
    """Login with email and password."""
    # Find user by email
    statement = select(User).where(User.email == credentials.email, User.deleted_at.is_(None))
    user = session.exec(statement).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate access token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "email": user.email,
            "organization_id": user.organization_id,
        }
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiration_hours * 3600,
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_image_url=user.profile_image_url,
        ),
    )


@router.get("/me", response_model=UserResponse | None)
async def get_current_user_info(user: OptionalUser, session: SessionDep):
    """Get current user information from JWT token."""
    if user is None:
        return None

    # Fetch full user details from database
    user_id = user.get("sub")
    if not user_id:
        return None

    statement = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    db_user = session.exec(statement).first()

    if not db_user:
        return None

    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        profile_image_url=db_user.profile_image_url,
    )


@router.post("/logout")
async def logout():
    """Logout (client should discard token)."""
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, session: SessionDep):
    """Request password reset token."""
    import secrets

    # Find user by email
    statement = select(User).where(User.email == request.email, User.deleted_at.is_(None))
    user = session.exec(statement).first()

    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If the email exists, a reset link will be sent"}

    # Generate reset token (32 bytes = 64 hex chars)
    reset_token = secrets.token_urlsafe(32)

    # Token expires in 1 hour
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    # Update user with reset token
    user.password_reset_token = reset_token
    user.password_reset_expires = expires_at
    session.add(user)
    session.commit()

    # TODO: Send email with reset link
    # For now, we'll just log the token (in production, send via email service)
    print(f"Password reset token for {user.email}: {reset_token}")
    print(f"Reset link: {settings.frontend_url}/reset-password?token={reset_token}")

    return {"message": "If the email exists, a reset link will be sent"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, session: SessionDep):
    """Reset password with token."""
    # Find user with matching token
    statement = select(User).where(
        User.password_reset_token == request.token,
        User.deleted_at.is_(None),
    )
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check if token is expired
    if user.password_reset_expires is None or user.password_reset_expires < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Update password
    user.password_hash = get_password_hash(request.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    session.add(user)
    session.commit()

    return {"message": "Password reset successfully"}


# Google OAuth routes are handled by google_auth.router
# See api/routes/google_auth.py for full implementation

