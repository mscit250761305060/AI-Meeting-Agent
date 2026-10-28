import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.models import User, SessionRecord, MeetingSummary, GeneratedProject
from tests.conftest import TestingSessionLocal
from app.services.meeting_state import begin_meeting, reset_runtime_state
from app.services.ai.meeting_summary_service import MeetingSummaryService


def test_meeting_summary_access_isolation():
    client = TestClient(app)

    # 1. Register User A and User B
    res_a = client.post("/auth/register", json={
        "username": "sec_user_a",
        "email": "sec_a@example.com",
        "password": "Password123!"
    })
    token_a = res_a.json()["token"]
    user_a_id = res_a.json()["user"]["id"]

    res_b = client.post("/auth/register", json={
        "username": "sec_user_b",
        "email": "sec_b@example.com",
        "password": "Password123!"
    })
    token_b = res_b.json()["token"]
    user_b_id = res_b.json()["user"]["id"]

    session_id = f"sec-sess-{uuid.uuid4().hex[:8]}"

    # Add a session record and summary owned by User A
    with TestingSessionLocal() as db:
        s_rec = SessionRecord(
            session_id=session_id,
            user_id=user_a_id,
            status="completed",
            meeting_link="https://meet.google.com/sec-test-aaa"
        )
        summary = MeetingSummary(
            id=str(uuid.uuid4()),
            session_id=session_id,
            summary_text="User A private meeting summary",
            action_items=["Private action 1"],
            decisions=["Private decision 1"],
            key_points=["Key point 1", "Key point 2"]
        )
        db.add_all([s_rec, summary])
        db.commit()

    # 2. Unauthenticated request to User A's summary must return 403 Forbidden
    res_unauth = client.get(f"/meeting/summary/{session_id}")
    assert res_unauth.status_code == 403
    assert "Access denied" in res_unauth.json()["detail"] or "Not authorized" in res_unauth.json()["detail"]

    # 3. User B requesting User A's summary must return 403 Forbidden
    res_user_b = client.get(
        f"/meeting/summary/{session_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_user_b.status_code == 403
    assert "Access denied" in res_user_b.json()["detail"] or "Not authorized" in res_user_b.json()["detail"]

    # 4. User A requesting their own summary must succeed with 200 and include key_points
    res_user_a = client.get(
        f"/meeting/summary/{session_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_user_a.status_code == 200
    data = res_user_a.json()
    assert data["success"] is True
    assert data["summary"]["session_id"] == session_id
    assert "Key point 1" in data["summary"]["key_points"]
    assert "Key point 2" in data["summary"]["key_points"]


def test_meeting_control_isolation():
    client = TestClient(app)

    # Register User A and User B
    res_a = client.post("/auth/register", json={
        "username": "ctrl_user_a",
        "email": "ctrl_a@example.com",
        "password": "Password123!"
    })
    token_a = res_a.json()["token"]
    user_a_id = res_a.json()["user"]["id"]

    res_b = client.post("/auth/register", json={
        "username": "ctrl_user_b",
        "email": "ctrl_b@example.com",
        "password": "Password123!"
    })
    token_b = res_b.json()["token"]
    user_b_id = res_b.json()["user"]["id"]

    # Simulate an active meeting owned by User A
    session_id = f"ctrl-sess-{uuid.uuid4().hex[:8]}"
    begin_meeting(session_id, user_id=user_a_id)

    try:
        # User B tries to stop User A's active meeting -> must return 403 Forbidden
        res_stop_b = client.post(
            "/meeting/stop",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_stop_b.status_code == 403
        assert "Cannot stop another user" in res_stop_b.json()["detail"] or "Not authorized" in res_stop_b.json()["detail"]

        # User B queries status -> should show idle for User B, not User A's active session
        res_status_b = client.get(
            "/meeting/status",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert res_status_b.status_code == 200
        data_b = res_status_b.json()
        assert data_b["running"] is False
        assert data_b["join_status"] == "idle"
        assert data_b["session_id"] is None

        # User A queries status -> should show User A's active session
        res_status_a = client.get(
            "/meeting/status",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_status_a.status_code == 200
        data_a = res_status_a.json()
        assert data_a["session_id"] == session_id
        assert data_a["running"] is True

        # User A stops their own meeting -> should succeed
        res_stop_a = client.post(
            "/meeting/stop",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_stop_a.status_code == 200
        assert res_stop_a.json()["success"] is True

    finally:
        reset_runtime_state()


def test_project_multi_user_isolation(tmp_path):
    client = TestClient(app)

    # Register User A and User B
    res_a = client.post("/auth/register", json={
        "username": "proj_user_a",
        "email": "proj_a@example.com",
        "password": "Password123!"
    })
    token_a = res_a.json()["token"]
    user_a_id = res_a.json()["user"]["id"]

    res_b = client.post("/auth/register", json={
        "username": "proj_user_b",
        "email": "proj_b@example.com",
        "password": "Password123!"
    })
    token_b = res_b.json()["token"]
    user_b_id = res_b.json()["user"]["id"]

    project_id = f"proj-{uuid.uuid4().hex[:8]}"
    session_id = f"sess-proj-{uuid.uuid4().hex[:6]}"

    # Create dummy project directory on disk
    target_dir = tmp_path / project_id
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_text("<h1>Confidential Alpha</h1>", encoding="utf-8")

    # Add GeneratedProject linked to SessionRecord owned by User A
    with TestingSessionLocal() as db:
        sess = SessionRecord(
            session_id=session_id,
            user_id=user_a_id,
            status="completed"
        )
        proj = GeneratedProject(
            id=project_id,
            session_id=session_id,
            project_name="Confidential Project Alpha",
            project_path=str(target_dir),
            file_tree={}
        )
        db.add_all([sess, proj])
        db.commit()

    # 1. Unauthenticated request to /projects/{project_id} -> 403
    res_unauth = client.get(f"/projects/{project_id}")
    assert res_unauth.status_code == 403

    # 2. User B request to /projects/{project_id} -> 403
    res_user_b = client.get(
        f"/projects/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_user_b.status_code == 403

    # 3. User B request to /projects/{project_id}/files -> 403
    res_files_b = client.get(
        f"/projects/{project_id}/files",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_files_b.status_code == 403

    # 4. User B request to /projects/{project_id}/download -> 403
    res_dl_b = client.get(
        f"/projects/{project_id}/download",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_dl_b.status_code == 403

    # 5. User B request to /projects/{project_id}/run -> 403
    res_run_b = client.post(
        f"/projects/{project_id}/run",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_run_b.status_code == 403

    # 6. User B listing projects must NOT contain User A's project
    res_list_b = client.get(
        "/projects",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_list_b.status_code == 200
    listed_ids_b = [p["id"] for p in res_list_b.json()["projects"]]
    assert project_id not in listed_ids_b

    # 7. User A listing projects must contain User A's project
    res_list_a = client.get(
        "/projects",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_list_a.status_code == 200
    listed_ids_a = [p["id"] for p in res_list_a.json()["projects"]]
    assert project_id in listed_ids_a


def test_key_points_persistence_and_retrieval():
    session_id = f"kp-sess-{uuid.uuid4().hex[:8]}"
    transcript_text = (
        "Alice: We need to finalize the deployment plan. "
        "Bob: Action item: deploy canary build by tomorrow. "
        "Alice: We decided to approve the architecture changes. "
        "Charlie: Key takeaway: database sharding is deferred to next quarter."
    )

    with TestingSessionLocal() as db:
        # Create session record
        db.add(SessionRecord(session_id=session_id, status="completed", meeting_link="https://meet.google.com/test-kp"))
        db.commit()

        # Generate and persist summary
        result = MeetingSummaryService.generate_summary(
            transcript_text=transcript_text,
            session_id=session_id,
            db=db
        )
        assert result["success"] is True
        assert "key_points" in result["summary"]

        # Retrieve stored summary
        retrieved = MeetingSummaryService.get_summary_for_session(session_id, db=db)
        assert retrieved is not None
        assert retrieved["session_id"] == session_id
        assert isinstance(retrieved["key_points"], list)
        assert len(retrieved["key_points"]) > 0
        assert isinstance(retrieved["action_items"], list)
        assert isinstance(retrieved["decisions"], list)


def test_root_url_authentication_and_redirect_contract():
    client = TestClient(app)

    # 1. Logged-out user opening base URL '/' MUST redirect to '/login'
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code in (302, 303, 307)
    assert res_root.headers["location"] == "/login"

    # 2. '/login' MUST show the login page
    res_login = client.get("/login")
    assert res_login.status_code == 200
    assert "Sign in to your account" in res_login.text or "loginForm" in res_login.text

    # 3. '/register' MUST show registration page
    res_reg = client.get("/register")
    assert res_reg.status_code == 200
    assert "Create your account" in res_reg.text or "registerForm" in res_reg.text

    # 4. User registers
    test_username = f"reguser_{uuid.uuid4().hex[:6]}"
    res_post_reg = client.post("/auth/register", json={
        "full_name": "Test Redirect User",
        "username": test_username,
        "email": f"{test_username}@example.com",
        "password": "Password123!"
    })
    assert res_post_reg.status_code == 200

    # 5. After registration, user must NOT be automatically logged in (cookie must not be set)
    # Opening '/' directly before logging in must STILL redirect to '/login'
    res_root_after_reg = client.get("/", follow_redirects=False)
    assert res_root_after_reg.status_code in (302, 303, 307)
    assert res_root_after_reg.headers["location"] == "/login"

    # '/dashboard' directly must also redirect to '/login'
    res_dash_unauth = client.get("/dashboard", follow_redirects=False)
    assert res_dash_unauth.status_code in (302, 303, 307)
    assert res_dash_unauth.headers["location"] == "/login"

    # '/login' and '/register' pages must still show their forms
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200

    # 6. Only after successful login should the user access the meeting dashboard
    res_login_post = client.post("/auth/login", json={
        "username_or_email": test_username,
        "password": "Password123!"
    })
    assert res_login_post.status_code == 200
    assert "access_token" in res_login_post.cookies

    # Now authenticated user can access '/' and '/dashboard'
    res_root_auth = client.get("/", follow_redirects=False)
    assert res_root_auth.status_code == 200
    assert "AI Meeting Agent" in res_root_auth.text

    res_dash_auth = client.get("/dashboard", follow_redirects=False)
    assert res_dash_auth.status_code == 200
    assert "AI Meeting Agent" in res_dash_auth.text

    # 7. Authenticated user visiting /login or /register is redirected to dashboard '/'
    assert client.get("/login", follow_redirects=False).status_code in (302, 303, 307)
    assert client.get("/register", follow_redirects=False).status_code in (302, 303, 307)

    # 8. User logs out
    res_logout = client.post("/auth/logout")
    assert res_logout.status_code == 200

    # After logout, opening '/' once again redirects to '/login'
    res_root_logged_out = client.get("/", follow_redirects=False)
    assert res_root_logged_out.status_code in (302, 303, 307)
    assert res_root_logged_out.headers["location"] == "/login"

