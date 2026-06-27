import pytest

import routes.auth as auth_routes
import routes.security as security_routes
from app import create_app
from config import AUTH_COOKIE_NAME


class FakeAuthService:
    def __init__(self):
        self.revoked = []

    def login(self, role, email, password):
        if role != "student" or email != "student@example.com" or password != "secret123":
            return None
        return {
            "id": "student-1",
            "name": "Student One",
            "email": email,
            "token": "token-login",
        }

    def register(self, role, name, email, password):
        return {
            "id": f"{role}-1",
            "name": name,
            "email": email,
            "token": "token-register",
        }

    def resolve_token(self, token):
        if token in {"token-login", "token-refresh"}:
            return {
                "role": "student",
                "user": {
                    "id": "student-1",
                    "name": "Student One",
                    "email": "student@example.com",
                },
            }
        return None

    def refresh_token(self, token):
        if token != "token-login":
            return None
        return {
            "role": "student",
            "user": {
                "id": "student-1",
                "name": "Student One",
                "email": "student@example.com",
                "token": "token-refresh",
            },
        }

    def revoke_token(self, token):
        self.revoked.append(token)
        return True


@pytest.fixture()
def fake_auth(monkeypatch):
    service = FakeAuthService()
    monkeypatch.setattr(auth_routes, "auth_service", service)
    monkeypatch.setattr(security_routes, "auth_service", service)
    monkeypatch.setattr(auth_routes, "audit", lambda *args, **kwargs: None)
    return service


@pytest.fixture()
def client(fake_auth):
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_login_sets_httponly_cookie_and_hides_token(client):
    response = client.post("/api/auth/login", json={
        "email": "student@example.com",
        "password": "secret123",
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["role"] == "student"
    assert "token" not in payload["student"]

    set_cookie = response.headers.get("Set-Cookie", "")
    assert f"{AUTH_COOKIE_NAME}=token-login" in set_cookie
    assert "HttpOnly" in set_cookie


def test_me_reads_auth_cookie(client):
    client.set_cookie(AUTH_COOKIE_NAME, "token-login")

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["role"] == "student"
    assert payload["user"]["id"] == "student-1"


def test_refresh_rotates_cookie_and_hides_token(client):
    client.set_cookie(AUTH_COOKIE_NAME, "token-login")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "token" not in payload["user"]
    assert f"{AUTH_COOKIE_NAME}=token-refresh" in response.headers.get("Set-Cookie", "")


def test_logout_revokes_and_clears_cookie(client, fake_auth):
    client.set_cookie(AUTH_COOKIE_NAME, "token-login")

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert fake_auth.revoked == ["token-login"]
    set_cookie = response.headers.get("Set-Cookie", "")
    assert f"{AUTH_COOKIE_NAME}=" in set_cookie
    assert "Max-Age=0" in set_cookie
