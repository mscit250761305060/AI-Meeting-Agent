import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services import meeting_state
from app.services.meeting_browser_agent import BrowserMeetingAgent, JoinStatus, MeetingPlatform
from app.services.meeting_service import MeetingService


@pytest.fixture(autouse=True)
def reset_state():
    """Ensure clean meeting state before and after each test."""
    meeting_state.reset_runtime_state()
    yield
    meeting_state.reset_runtime_state()


def test_retry_after_browser_worker_exits():
    """
    Test 1: Retry after a browser worker exits.
    When a browser worker exits (status FAILED / STOPPED / thread dead),
    a new join attempt must succeed in resetting stale meeting_running state
    and initiating a new browser join session without getting blocked.
    """
    agent = BrowserMeetingAgent()

    with patch("app.services.meeting_service.browser_agent", agent):
        # Simulate a previous session where worker exited with failure
        meeting_state.begin_meeting("stale_session_1")
        assert meeting_state.meeting_running is True

        # Simulate agent worker dead
        agent.status = JoinStatus.FAILED
        agent._thread = None
        assert agent.is_worker_alive() is False

        # Mock start_join for the new attempt
        with patch.object(agent, "start_join") as mock_start:
            mock_start.return_value = {
                "success": True,
                "status": JoinStatus.LAUNCHING_BROWSER.value,
                "platform": MeetingPlatform.GOOGLE_MEET.value,
                "message": "Browser join initiated."
            }
            res = MeetingService.join("https://meet.google.com/abc-defg-hij")

            assert res["success"] is True
            assert res["status"] == JoinStatus.LAUNCHING_BROWSER.value
            # Stale session was cleared and new session began
            assert res["session_id"] != "stale_session_1"
            assert mock_start.called


@pytest.mark.asyncio
async def test_login_required_browser_remains_open():
    """
    Test 2: Login-required browser remains open.
    When Google Meet redirects to accounts.google.com / signin,
    the agent must transition to LOGIN_REQUIRED and enter the wait loop,
    keeping the browser context open until sign-in or stop.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()

    # URL is initially at Google Signin
    agent._page.url = "https://accounts.google.com/signin/v2/identifier"

    # Start _await_google_login in background task
    task = asyncio.create_task(agent._await_google_login("https://meet.google.com/test-meet-code"))

    # Give it a moment to run the loop
    await asyncio.sleep(0.05)
    assert agent.requires_login is True
    assert not task.done()  # Window remains open and task is still running!

    # Simulate user completing sign-in: URL changes back to meet.google.com
    agent._page.url = "https://meet.google.com/test-meet-code"
    agent._page.inner_text.return_value = "Ready to join? Meeting lobby"

    # Await task completion with login success
    success = await task
    assert success is True
    assert agent.requires_login is False
    assert agent.status == JoinStatus.JOINING


@pytest.mark.asyncio
async def test_waiting_admission_browser_remains_open():
    """
    Test 3: Waiting-admission browser remains open.
    When in the waiting room waiting for host admission, the browser agent
    must not exit after a hardcoded loop. It must remain open in the waiting room
    until admitted, denied, or stopped.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()

    # Mock in-call check
    mock_elem = AsyncMock()
    mock_elem.is_visible = AsyncMock(return_value=False)
    agent._page.locator = MagicMock(return_value=MagicMock(first=mock_elem))
    agent._page.inner_text = AsyncMock(return_value="Someone will let you in soon")

    # Start monitor task
    monitor_task = asyncio.create_task(agent._monitor_google_meet("Ask to join"))
    await asyncio.sleep(0.05)

    assert agent.status == JoinStatus.WAITING_ADMISSION
    assert agent.waiting_for_host is True
    assert not monitor_task.done()  # Browser remains open and task is active!

    # Simulate host clicking "Admit" -> in-call controls appear
    mock_elem.is_visible = AsyncMock(return_value=True)

    with patch.object(agent, "_trigger_audio_pipeline"), patch.object(agent, "_hold_active_session", new_callable=AsyncMock) as mock_hold:
        mock_hold.return_value = None
        # Give monitor loop one tick to detect in-call (sleep in loop is 1.0s)
        await asyncio.sleep(1.1)
        assert agent.status == JoinStatus.JOINED
        assert agent.in_meeting is True
        assert agent.waiting_for_host is False
    
    agent._stop_event.set()
    await monitor_task


def test_stop_and_cleanup_reset_lifecycle():
    """
    Test 4: Stop and cleanup reset lifecycle correctly.
    Calling MeetingService.stop() cleans up browser resources, sets stop_event,
    and transitions meeting_running to False.
    """
    agent = BrowserMeetingAgent()
    agent.status = JoinStatus.JOINED
    agent.in_meeting = True

    with patch("app.services.meeting_service.browser_agent", agent):
        meeting_state.begin_meeting("session_test_stop")
        assert meeting_state.meeting_running is True

        with patch.object(agent, "stop") as mock_agent_stop:
            mock_agent_stop.return_value = {"success": True, "message": "Browser stopped."}
            res = MeetingService.stop()

            assert res["success"] is True
            assert meeting_state.meeting_running is False
            assert meeting_state.stop_event.is_set()


def test_duplicate_join_requests_do_not_create_duplicate_workers():
    """
    Test 5: Duplicate join requests do not create duplicate workers.
    When a browser worker is already alive and running, subsequent join requests
    return the current session status without spawning another worker thread.
    """
    agent = BrowserMeetingAgent()
    agent.status = JoinStatus.WAITING_ADMISSION
    agent.meeting_url = "https://meet.google.com/test-active-meet"

    # Simulate active thread
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True
    agent._thread = mock_thread

    assert agent.is_worker_alive() is True

    with patch("app.services.meeting_service.browser_agent", agent):
        meeting_state.begin_meeting("session_active_1")
        meeting_state.meeting_link = "https://meet.google.com/test-active-meet"
        meeting_state.platform = "google_meet"

        with patch.object(agent, "start_join") as mock_start:
            res = MeetingService.join("https://meet.google.com/test-active-meet")

            # Duplicate call should NOT call start_join again
            assert not mock_start.called
            assert res["success"] is True
            assert res["status"] == JoinStatus.WAITING_ADMISSION.value
            assert res["session_id"] == "session_active_1"


def test_browser_launch_failures_return_accurate_statuses():
    """
    Test 6: Browser launch failures return accurate statuses.
    If the browser launch fails, MeetingService.join() must return success=False,
    provide the failure message, and clean up meeting_state so meeting_running is False.
    """
    agent = BrowserMeetingAgent()

    with patch("app.services.meeting_service.browser_agent", agent):
        # Simulate browser launch failure in start_join
        with patch.object(agent, "start_join") as mock_start:
            mock_start.return_value = {
                "success": False,
                "status": JoinStatus.FAILED.value,
                "platform": MeetingPlatform.GOOGLE_MEET.value,
                "message": "Browser launch failed: TargetClosedError: Browser crashed on startup."
            }
            res = MeetingService.join("https://meet.google.com/abc-defg-hij")

            assert res["success"] is False
            assert res["status"] == JoinStatus.FAILED.value
            assert "Browser launch failed" in res["message"]
            # meeting_state must NOT remain in a zombie running state!
            assert meeting_state.meeting_running is False


@pytest.mark.asyncio
async def test_google_meet_denial_unauthenticated_guest_diagnosed():
    """
    Regression Test 7: Google Meet 'You can't join this video call' (Unauthenticated Guest).
    When Google Meet displays 'You can't join this video call' and user is not authenticated,
    the agent must diagnose this as an unauthenticated guest, transition to LOGIN_REQUIRED,
    trigger Google sign-in navigation, and NEVER report JOINED or in_meeting=True.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()
    agent._context = None  # No cookies

    agent._page.url = "https://meet.google.com/abc-defg-hij"
    agent._page.inner_text = AsyncMock(return_value="You can't join this video call. Sign in with a Google Account")

    # Mock sign in button
    mock_signin_btn = AsyncMock()
    mock_signin_btn.is_visible = AsyncMock(return_value=True)
    mock_invisible = AsyncMock()
    mock_invisible.is_visible = AsyncMock(return_value=False)

    def _mock_locator(sel):
        if "Switch account" in sel or "different account" in sel:
            return MagicMock(first=mock_invisible)
        if "Sign in" in sel:
            return MagicMock(first=mock_signin_btn)
        return MagicMock(first=mock_invisible)

    agent._page.locator = MagicMock(side_effect=_mock_locator)

    with patch.object(agent, "_await_google_login", new_callable=AsyncMock) as mock_await:
        mock_await.return_value = False  # User doesn't finish in this test
        await agent._join_google_meet("https://meet.google.com/abc-defg-hij")

        assert agent.status == JoinStatus.LOGIN_REQUIRED
        assert agent.in_meeting is False
        assert "Google Sign-In Required" in agent.message or "login is required" in agent.message
        assert mock_await.called


@pytest.mark.asyncio
async def test_google_meet_denial_domain_restriction_switch_account():
    """
    Regression Test 8: Google Meet 'You can't join this video call' (Domain Restriction).
    When Google Meet shows 'Switch account' / organization domain restriction,
    the agent must diagnose account mismatch, set LOGIN_REQUIRED with domain advice,
    and never report JOINED or in_meeting=True.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()

    agent._page.url = "https://meet.google.com/corp-team-meet"
    agent._page.inner_text = AsyncMock(return_value="You can't join this video call. Switch to an account that has access. Switch account")

    mock_switch_btn = AsyncMock()
    mock_switch_btn.is_visible = AsyncMock(return_value=True)
    mock_invisible = AsyncMock()
    mock_invisible.is_visible = AsyncMock(return_value=False)

    agent._page.locator = MagicMock(
        side_effect=lambda sel: MagicMock(first=mock_switch_btn) if "Switch account" in sel else MagicMock(first=mock_invisible)
    )

    with patch.object(agent, "_await_google_login", new_callable=AsyncMock) as mock_await:
        mock_await.return_value = False
        await agent._join_google_meet("https://meet.google.com/corp-team-meet")

        assert agent.status == JoinStatus.LOGIN_REQUIRED
        assert agent.in_meeting is False
        assert "Organization Domain Restriction" in agent.message
        assert mock_switch_btn.click.called


@pytest.mark.asyncio
async def test_google_meet_host_denied_admission():
    """
    Regression Test 9: Host Explicitly Denies Admission.
    When Google Meet displays 'The host has denied your request',
    the agent must transition to ADMISSION_DENIED with actionable advice,
    stop waiting, and NEVER report in_meeting=True.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()

    agent._page.url = "https://meet.google.com/abc-defg-hij"
    agent._page.inner_text = AsyncMock(return_value="You can't join this video call. Someone in the call denied your request to join.")

    mock_locator = MagicMock()
    mock_locator.first.is_visible = AsyncMock(return_value=False)
    agent._page.locator = MagicMock(return_value=mock_locator)

    await agent._join_google_meet("https://meet.google.com/abc-defg-hij")

    assert agent.status == JoinStatus.ADMISSION_DENIED
    assert agent.in_meeting is False
    assert "Host Denied Admission" in agent.message


@pytest.mark.asyncio
async def test_google_meet_meeting_expired_or_invalid():
    """
    Regression Test 10: Meeting Expired or Invalid Meeting Code.
    When Google Meet displays 'This meeting has expired' or 'This video call has ended',
    the agent must transition to FAILED with instructions to verify the URL,
    and NEVER report in_meeting=True.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()

    agent._page.url = "https://meet.google.com/old-meeting-code"
    agent._page.inner_text = AsyncMock(return_value="You can't join this video call. This meeting has expired.")

    mock_locator = MagicMock()
    mock_locator.first.is_visible = AsyncMock(return_value=False)
    agent._page.locator = MagicMock(return_value=mock_locator)

    await agent._join_google_meet("https://meet.google.com/old-meeting-code")

    assert agent.status == JoinStatus.FAILED
    assert agent.in_meeting is False
    assert "Meeting Unavailable" in agent.message


def test_open_auth_window_user_profile_isolation_and_lock_cleanup():
    """
    Regression Test 11: open_auth_window must cleanly resolve user profile path,
    clean stale SingletonLock files, and launch Chrome without NameError.
    """
    from pathlib import Path
    from app.services.meeting_browser_agent import clean_stale_singleton_locks, get_user_browser_profile_dir

    test_user_id = "test_user_99"
    _, user_dir = get_user_browser_profile_dir(test_user_id)
    lock_file = Path(user_dir) / "SingletonLock"
    lock_file.touch()
    assert lock_file.exists()

    clean_stale_singleton_locks(user_dir)
    assert not lock_file.exists()

    agent = BrowserMeetingAgent()
    with patch("app.services.meeting_browser_agent.get_chrome_executable", return_value="C:\\dummy\\chrome.exe"), \
         patch("subprocess.Popen") as mock_popen:
        res = agent.open_auth_window(user_id=test_user_id)
        assert res["success"] is True
        assert test_user_id in res["profile_path"]
        assert mock_popen.called
