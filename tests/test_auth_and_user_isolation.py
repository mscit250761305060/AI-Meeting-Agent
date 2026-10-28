import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.models import User, SessionRecord, GeneratedProject
from app.services.auth_service import hash_password, verify_password, create_access_token, decode_access_token
from tests.conftest import TestingSessionLocal


def test_password_hashing_and_verification():
    raw_pwd = "SecurePassword123!"
    hashed = hash_password(raw_pwd)

    assert hashed != raw_pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False


def test_jwt_token_creation_and_decoding():
    data = {"sub": "user-123", "username": "alice", "email": "alice@example.com"}
    token = create_access_token(data)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["username"] == "alice"
    assert payload["email"] == "alice@example.com"
    assert "exp" in payload


def test_user_registration_flow():
    client = TestClient(app)

    # 1. Register valid user
    res = client.post("/auth/register", json={
        "full_name": "Alice Wonderland",
        "username": "alice",
        "email": "alice@example.com",
        "password": "Password123!"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["user"]["username"] == "alice"
    assert "token" in data
    # Registration should not authenticate the browser session; user must log in explicitly
    assert "access_token" not in res.cookies or not res.cookies.get("access_token")

    # 2. Duplicate username registration should fail with 409 Conflict
    res_dup_user = client.post("/auth/register", json={
        "full_name": "Another Alice",
        "username": "alice",
        "email": "another@example.com",
        "password": "Password123!"
    })
    assert res_dup_user.status_code == 409
    assert "Username is already taken" in res_dup_user.json()["detail"]

    # 3. Duplicate email registration should fail with 409 Conflict
    res_dup_email = client.post("/auth/register", json={
        "full_name": "Alice Clone",
        "username": "alice_clone",
        "email": "alice@example.com",
        "password": "Password123!"
    })
    assert res_dup_email.status_code == 409
    assert "account with this email already exists" in res_dup_email.json()["detail"]


def test_user_login_and_logout_flow():
    client = TestClient(app)

    # Register user
    client.post("/auth/register", json={
        "full_name": "Bob Builder",
        "username": "bobbuilder",
        "email": "bob@example.com",
        "password": "Password123!"
    })

    # Successful login with username
    login_res1 = client.post("/auth/login", json={
        "username_or_email": "bobbuilder",
        "password": "Password123!"
    })
    assert login_res1.status_code == 200
    assert login_res1.json()["success"] is True
    assert "access_token" in login_res1.cookies

    # Successful login with email
    login_res2 = client.post("/auth/login", json={
        "username_or_email": "bob@example.com",
        "password": "Password123!"
    })
    assert login_res2.status_code == 200
    assert login_res2.json()["success"] is True

    # Failed login with incorrect password
    bad_res = client.post("/auth/login", json={
        "username_or_email": "bob@example.com",
        "password": "WrongPassword!"
    })
    assert bad_res.status_code == 401
    assert "Invalid username/email or password" in bad_res.json()["detail"]

    # Logout
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True


def test_user_data_isolation():
    client_a = TestClient(app)
    client_b = TestClient(app)

    # Create User A
    res_a = client_a.post("/auth/register", json={
        "username": "user_a",
        "email": "usera@example.com",
        "password": "Password123!"
    })
    token_a = res_a.json()["token"]
    user_a_id = res_a.json()["user"]["id"]

    # Create User B
    res_b = client_b.post("/auth/register", json={
        "username": "user_b",
        "email": "userb@example.com",
        "password": "Password123!"
    })
    token_b = res_b.json()["token"]
    user_b_id = res_b.json()["user"]["id"]

    # In database, simulate meetings owned by User A and User B
    with TestingSessionLocal() as db:
        session_a = SessionRecord(session_id="session-user-a", user_id=user_a_id, status="active", meeting_link="https://meet.google.com/aaa-bbbb-ccc")
        session_b = SessionRecord(session_id="session-user-b", user_id=user_b_id, status="active", meeting_link="https://meet.google.com/xxx-yyyy-zzz")
        db.add_all([session_a, session_b])
        db.commit()

    # Query history as User A
    hist_a = client_a.get("/meeting/history", headers={"Authorization": f"Bearer {token_a}"}).json()
    session_ids_a = [m["session_id"] for m in hist_a["meetings"]]
    assert "session-user-a" in session_ids_a
    assert "session-user-b" not in session_ids_a  # User B's session is isolated!

    # Query history as User B
    hist_b = client_b.get("/meeting/history", headers={"Authorization": f"Bearer {token_b}"}).json()
    session_ids_b = [m["session_id"] for m in hist_b["meetings"]]
    assert "session-user-b" in session_ids_b
    assert "session-user-a" not in session_ids_b  # User A's session is isolated!
