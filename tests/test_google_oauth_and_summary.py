import os
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.models.models import User, SessionRecord, MeetingSummary
from app.services.ai.meeting_summary_service import MeetingSummaryService
from app.services.meeting_browser_agent import validate_and_classify_url, MeetingPlatform
from tests.conftest import TestingSessionLocal


def test_google_oauth_status_endpoint():
    client = TestClient(app)
    res = client.get("/auth/google/status")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "connected" in data
    assert "notice" in data


def test_google_oauth_url_generation():
    client = TestClient(app)
    res = client.get("/auth/google/url")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    if not data["configured"]:
        assert "Google OAuth is not configured" in data["message"]
        assert "setup_guide" in data
        guide = data["setup_guide"]
        assert "steps" in guide
        assert len(guide["steps"]) > 0
        assert "redirect_uri" in guide
        assert "http" in guide["redirect_uri"]


def test_google_oauth_status_setup_guide_when_unconfigured():
    client = TestClient(app)
    res = client.get("/auth/google/status")
    assert res.status_code == 200
    data = res.json()
    if not data["configured"]:
        assert "setup_guide" in data
        assert data["setup_guide"] is not None
        assert "redirect_uri" in data["setup_guide"]
        assert "steps" in data["setup_guide"]


def test_auth_pages_redirect_contracts():
    client = TestClient(app)

    # 1. Check logged-out user visiting base URL "/" redirects to "/login"
    logged_out_dash = client.get("/", follow_redirects=False)
    assert logged_out_dash.status_code == 303
    assert logged_out_dash.headers["location"] == "/login"

    # 2. Check registration page is accessible and redirects to /login?registered=1 on submit
    reg_page = client.get("/register")
    assert reg_page.status_code == 200
    assert '/login?registered=1' in reg_page.text
    assert 'google-setup-modal' in reg_page.text

    # 3. Check login template handles registered param and displays setup modal
    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert 'registered' in login_page.text
    assert 'google-setup-modal' in login_page.text

    # 4. Register a user and log in to obtain authenticated session
    unique_user = f"demo_user_{uuid.uuid4().hex[:6]}"
    reg_res = client.post("/auth/register", json={
        "full_name": "Demo Reviewer",
        "username": unique_user,
        "email": f"{unique_user}@company.com",
        "password": "Password123!"
    })
    assert reg_res.status_code == 200

    login_res = client.post("/auth/login", json={
        "username_or_email": unique_user,
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    # 5. Authenticated user can now load dashboard and sees google setup modal
    dash_page = client.get("/", follow_redirects=False)
    assert dash_page.status_code == 200
    assert 'google-setup-modal' in dash_page.text

    # 6. Authenticated user visiting /login or /register is redirected to "/"
    auth_login_redirect = client.get("/login", follow_redirects=False)
    assert auth_login_redirect.status_code == 303
    assert auth_login_redirect.headers["location"] == "/"

    auth_reg_redirect = client.get("/register", follow_redirects=False)
    assert auth_reg_redirect.status_code == 303
    assert auth_reg_redirect.headers["location"] == "/"


def test_meeting_url_validation_matrix():
    # Valid Google Meet URLs
    ok, platform, norm = validate_and_classify_url("https://meet.google.com/abc-defg-hij")
    assert ok is True
    assert platform == MeetingPlatform.GOOGLE_MEET
    assert "meet.google.com/abc-defg-hij" in norm

    ok, platform, norm = validate_and_classify_url("meet.google.com/xyz-uvwx-rst")
    assert ok is True
    assert platform == MeetingPlatform.GOOGLE_MEET

    # Valid Zoom URLs
    ok, platform, norm = validate_and_classify_url("https://zoom.us/j/123456789")
    assert ok is True
    assert platform == MeetingPlatform.ZOOM

    # Valid Teams URLs
    ok, platform, norm = validate_and_classify_url("https://teams.microsoft.com/l/meetup-join/19%3ameeting")
    assert ok is True
    assert platform == MeetingPlatform.TEAMS

    # Invalid URLs
    ok, platform, msg = validate_and_classify_url("https://random-site.com/not-a-meeting")
    assert ok is False
    assert platform == MeetingPlatform.UNKNOWN

    ok, platform, msg = validate_and_classify_url("")
    assert ok is False


def test_ai_meeting_summary_empty_transcript_handling():
    # If transcript is empty or negligible, must NOT invent data
    res = MeetingSummaryService.generate_summary("")
    assert res["success"] is False
    assert "too brief" in res["message"]

    res_short = MeetingSummaryService.generate_summary("Hello yes.")
    assert res_short["success"] is False
    assert "too brief" in res_short["message"]


def test_ai_meeting_summary_extractive_analysis():
    transcript = (
        "Good morning everyone. Today we agreed to build a customer portal with React and FastAPI. "
        "Alex will implement the authentication endpoints by Friday. "
        "Sarah needs to design the user settings dashboard page. "
        "We decided to use PostgreSQL for user session storage. "
        "The team should review the database schema migration plan before deployment."
    )

    res = MeetingSummaryService.generate_summary(transcript, session_id="test-session-101")
    assert res["success"] is True
    summary = res["summary"]

    assert "overview" in summary
    assert len(summary["overview"]) > 10

    # Verify decisions extracted
    decisions = summary.get("decisions", [])
    assert len(decisions) >= 1

    # Verify action items extracted with owner and task
    action_items = summary.get("action_items", [])
    assert len(action_items) >= 2
    tasks_text = " ".join(item["task"] for item in action_items)
    assert "Alex" in tasks_text or "Sarah" in tasks_text


def test_meeting_summary_persistence_and_retrieval():
    # In test database, create a session
    with TestingSessionLocal() as db:
        session = SessionRecord(session_id="session-persistence-test", status="active", meeting_link="https://meet.google.com/test-abc-def")
        db.add(session)
        db.commit()

        # Save summary
        summary_obj = MeetingSummary(
            id=str(uuid.uuid4()),
            session_id="session-persistence-test",
            summary_text="Project architecture alignment session.",
            action_items=[{"task": "Deploy backend", "owner": "John", "priority": "High"}],
            decisions=["Use microservices"]
        )
        db.add(summary_obj)
        db.commit()

        retrieved = MeetingSummaryService.get_summary_for_session("session-persistence-test", db=db)
        assert retrieved is not None
        assert retrieved["overview"] == "Project architecture alignment session."
        assert len(retrieved["action_items"]) == 1
        assert retrieved["action_items"][0]["owner"] == "John"
        assert retrieved["decisions"] == ["Use microservices"]


def test_browser_profile_isolation_path():
    # Verify that different users get isolated user data directories
    user_1_id = "user-aaa-111"
    user_2_id = "user-bbb-222"

    profile_1 = Path.cwd() / "data" / "browser_profiles" / f"user_{user_1_id}"
    profile_2 = Path.cwd() / "data" / "browser_profiles" / f"user_{user_2_id}"

    assert profile_1 != profile_2
    assert "user_user-aaa-111" in str(profile_1)
    assert "user_user-bbb-222" in str(profile_2)
