"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestAuthentication:
    """Test suite for authentication endpoints."""

    def test_signup_success(self):
        """Test successful user signup."""
        response = client.post(
            "/api/auth/signup",
            json={
                "email": "test_user_001@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test_user_001@buildtrace.com"
        assert data["user"]["first_name"] == "Test"
        assert data["user"]["last_name"] == "User"

    def test_signup_duplicate_email(self):
        """Test signup with duplicate email fails."""
        # First signup
        client.post(
            "/api/auth/signup",
            json={
                "email": "duplicate@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "First",
                "last_name": "User",
            },
        )

        # Second signup with same email
        response = client.post(
            "/api/auth/signup",
            json={
                "email": "duplicate@buildtrace.com",
                "password": "DifferentPassword123",
                "first_name": "Second",
                "last_name": "User",
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_signup_invalid_email(self):
        """Test signup with invalid email fails."""
        response = client.post(
            "/api/auth/signup",
            json={
                "email": "not-an-email",
                "password": "TestPassword123",
                "first_name": "Test",
                "last_name": "User",
            },
        )
        assert response.status_code == 422

    def test_login_success(self):
        """Test successful login."""
        # First create a user
        client.post(
            "/api/auth/signup",
            json={
                "email": "login_test@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Login",
                "last_name": "Test",
            },
        )

        # Now login
        response = client.post(
            "/api/auth/login",
            json={
                "email": "login_test@buildtrace.com",
                "password": "TestPassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "login_test@buildtrace.com"

    def test_login_wrong_password(self):
        """Test login with wrong password fails."""
        # Create a user
        client.post(
            "/api/auth/signup",
            json={
                "email": "wrong_pass@buildtrace.com",
                "password": "CorrectPassword123",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Try to login with wrong password
        response = client.post(
            "/api/auth/login",
            json={
                "email": "wrong_pass@buildtrace.com",
                "password": "WrongPassword123",
            },
        )
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_nonexistent_user(self):
        """Test login with non-existent user fails."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@buildtrace.com",
                "password": "SomePassword123",
            },
        )
        assert response.status_code == 401

    def test_get_current_user_success(self):
        """Test getting current user with valid token."""
        # Signup and get token
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": "get_me_test@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "GetMe",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        # Get current user
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "get_me_test@buildtrace.com"
        assert data["first_name"] == "GetMe"
        assert data["last_name"] == "Test"

    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        # Should return null for invalid token
        assert response.status_code == 200
        assert response.json() is None

    def test_get_current_user_no_token(self):
        """Test getting current user without token."""
        response = client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json() is None

    def test_logout(self):
        """Test logout endpoint."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_password_truncation(self):
        """Test that passwords longer than 72 bytes are properly handled."""
        long_password = "a" * 100  # 100 character password
        response = client.post(
            "/api/auth/signup",
            json={
                "email": "long_pass@buildtrace.com",
                "password": long_password,
                "first_name": "Long",
                "last_name": "Password",
            },
        )
        assert response.status_code == 201

        # Should be able to login with same long password
        login_response = client.post(
            "/api/auth/login",
            json={
                "email": "long_pass@buildtrace.com",
                "password": long_password,
            },
        )
        assert login_response.status_code == 200

    def test_jwt_token_expiration(self):
        """Test that JWT token contains expiration."""
        response = client.post(
            "/api/auth/signup",
            json={
                "email": "jwt_test@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "JWT",
                "last_name": "Test",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "expires_in" in data
        assert data["expires_in"] == 86400  # 24 hours in seconds
