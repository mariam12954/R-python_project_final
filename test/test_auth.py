"""Tests for authentication: registration, login, token validation."""

import pytest


# ── Helpers ──────────────────────────────────────────────────────

def register(client, username="user1", email="user@test.com",
             password="pass1234", role="student"):
    return client.post("/auth/register", json={
        "username": username, "email": email,
        "password": password, "role": role
    })


def login(client, username="user1", password="pass1234"):
    return client.post("/auth/login", json={"username": username, "password": password})


# ── Registration ─────────────────────────────────────────────────

def test_register_success(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "user1"
    assert body["role"] == "student"
    assert "hashed_password" not in body  # never expose


def test_register_duplicate_username(client):
    register(client)
    r = register(client)  # same username
    assert r.status_code == 400
    assert "Username" in r.json()["detail"]


def test_register_duplicate_email(client):
    register(client, username="user1")
    r = register(client, username="user2")  # same email
    assert r.status_code == 400


def test_register_admin_role(client):
    r = register(client, username="admin1", email="admin@test.com", role="admin")
    assert r.status_code == 201
    assert r.json()["role"] == "admin"


# ── Login ────────────────────────────────────────────────────────

def test_login_success(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client):
    register(client)
    r = login(client, password="wrongpassword")
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = login(client, username="nobody")
    assert r.status_code == 401


# ── Token / Protected endpoint ───────────────────────────────────

def test_get_me_with_valid_token(client):
    register(client)
    token = login(client).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "user1"


def test_get_me_without_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_get_me_with_invalid_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer this.is.garbage"})
    assert r.status_code == 401


def test_token_grants_correct_role(client):
    register(client, username="adminX", email="ax@test.com", role="admin")
    token = login(client, username="adminX").json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["role"] == "admin"
