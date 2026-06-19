"""Tests for the auth service endpoints."""
import pytest


class TestAuthLogin:
    async def test_login_missing_body_returns_422(self, auth_client):
        response = await auth_client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    async def test_login_invalid_credentials_returns_401(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrongpass"},
        )
        assert response.status_code == 401

    async def test_health_ping(self, auth_client):
        response = await auth_client.get("/api/v1/health/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestAuthRefresh:
    async def test_refresh_invalid_token_returns_401(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-real-token"},
        )
        assert response.status_code == 401

    async def test_refresh_missing_token_returns_422(self, auth_client):
        response = await auth_client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == 422


class TestLogout:
    async def test_logout_without_token_returns_401(self, auth_client):
        response = await auth_client.post("/api/v1/auth/logout")
        assert response.status_code == 401
