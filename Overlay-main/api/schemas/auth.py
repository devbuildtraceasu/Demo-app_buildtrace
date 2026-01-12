"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response."""

    id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    profile_image_url: str | None = None


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

