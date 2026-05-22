"""Tests for student CRUD, role-based access, edge cases, and business logic."""

import pytest


# ── Helpers ──────────────────────────────────────────────────────

def _register_and_login(client, username, email, role="admin", password="pass1234"):
    client.post("/auth/register", json={
        "username": username, "email": email,
        "password": password, "role": role
    })
    r = client.post("/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def admin_headers(client):
    token = _register_and_login(client, "admin1", "admin@test.com", role="admin")
    return {"Authorization": f"Bearer {token}"}


def student_headers(client, username="stu1", email="stu@test.com"):
    token = _register_and_login(client, username, email, role="student")
    return {"Authorization": f"Bearer {token}"}


def create_student(client, headers, full_name="Ahmed Ali", department="CS",
                   gpa=3.5, year=2, user_id=1):
    return client.post("/students/", headers=headers, json={
        "full_name": full_name, "department": department,
        "gpa": gpa, "year": year, "user_id": user_id
    })


# ── CREATE ───────────────────────────────────────────────────────

def test_admin_can_create_student(client):
    headers = admin_headers(client)
    r = create_student(client, headers)
    assert r.status_code == 201
    assert r.json()["full_name"] == "Ahmed Ali"


def test_student_cannot_create_student(client):
    headers = student_headers(client)
    r = create_student(client, headers, user_id=99)
    assert r.status_code == 403


def test_unauthenticated_cannot_create(client):
    r = create_student(client, headers={})
    assert r.status_code == 401


def test_duplicate_student_profile_rejected(client):
    headers = admin_headers(client)
    create_student(client, headers, user_id=1)
    r = create_student(client, headers, user_id=1)  # same user_id
    assert r.status_code == 400


def test_gpa_boundary_valid(client):
    headers = admin_headers(client)
    r = create_student(client, headers, gpa=4.0)
    assert r.status_code == 201


# ── READ (list) ──────────────────────────────────────────────────

def test_admin_can_list_students(client):
    headers = admin_headers(client)
    create_student(client, headers, full_name="S1", user_id=1)
    create_student(client, headers, full_name="S2", user_id=2)
    r = client.get("/students/", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_student_cannot_list_all(client):
    admin_headers(client)          # registers admin with id=1
    headers = student_headers(client)  # registers student with id=2
    r = client.get("/students/", headers=headers)
    assert r.status_code == 403


def test_filter_by_department(client):
    headers = admin_headers(client)
    create_student(client, headers, department="CS",   user_id=1)
    create_student(client, headers, department="Math", user_id=2)
    r = client.get("/students/?department=CS", headers=headers)
    assert r.status_code == 200
    for s in r.json():
        assert "CS" in s["department"]


def test_filter_by_gpa_range(client):
    headers = admin_headers(client)
    create_student(client, headers, gpa=3.8, user_id=1)
    create_student(client, headers, gpa=2.5, user_id=2)
    r = client.get("/students/?min_gpa=3.0", headers=headers)
    assert r.status_code == 200
    for s in r.json():
        assert s["gpa"] >= 3.0


def test_pagination(client):
    headers = admin_headers(client)
    for i in range(1, 6):
        create_student(client, headers, full_name=f"S{i}", user_id=i)
    r = client.get("/students/?skip=0&limit=2", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


# ── READ (single) ────────────────────────────────────────────────

def test_admin_can_get_any_student(client):
    headers = admin_headers(client)
    sid = create_student(client, headers).json()["id"]
    r = client.get(f"/students/{sid}", headers=headers)
    assert r.status_code == 200


def test_get_nonexistent_student(client):
    headers = admin_headers(client)
    r = client.get("/students/9999", headers=headers)
    assert r.status_code == 404


# ── UPDATE ───────────────────────────────────────────────────────

def test_admin_can_update_student(client):
    headers = admin_headers(client)
    sid = create_student(client, headers).json()["id"]
    r = client.put(f"/students/{sid}", headers=headers, json={"gpa": 3.9})
    assert r.status_code == 200
    assert r.json()["gpa"] == 3.9


def test_update_with_no_fields_rejected(client):
    headers = admin_headers(client)
    sid = create_student(client, headers).json()["id"]
    r = client.put(f"/students/{sid}", headers=headers, json={})
    assert r.status_code == 400


def test_student_cannot_update_others_profile(client):
    a_headers = admin_headers(client)
    # Admin creates student linked to user_id=1
    sid = create_student(client, a_headers, user_id=1).json()["id"]
    # A different student (user_id=2) tries to update it
    s_headers = student_headers(client, username="stu2", email="stu2@test.com")
    r = client.put(f"/students/{sid}", headers=s_headers, json={"gpa": 1.0})
    assert r.status_code == 403


# ── DELETE ───────────────────────────────────────────────────────

def test_admin_can_delete_student(client):
    headers = admin_headers(client)
    sid = create_student(client, headers).json()["id"]
    r = client.delete(f"/students/{sid}", headers=headers)
    assert r.status_code == 200
    # Confirm gone
    r2 = client.get(f"/students/{sid}", headers=headers)
    assert r2.status_code == 404


def test_student_cannot_delete(client):
    a_headers = admin_headers(client)
    sid = create_student(client, a_headers).json()["id"]
    s_headers = student_headers(client)
    r = client.delete(f"/students/{sid}", headers=s_headers)
    assert r.status_code == 403


def test_delete_nonexistent_returns_404(client):
    headers = admin_headers(client)
    r = client.delete("/students/9999", headers=headers)
    assert r.status_code == 404


# ── /me endpoint ─────────────────────────────────────────────────

def test_student_can_get_own_profile_via_me(client):
    # Admin creates a student linked to user_id=1 (the admin itself)
    a_headers = admin_headers(client)
    create_student(client, a_headers, user_id=1)
    r = client.get("/students/me", headers=a_headers)
    assert r.status_code == 200
