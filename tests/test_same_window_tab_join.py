import asyncio
import os
import threading
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


def test_join_defaults_to_same_window_tab_mode():
    """
    Test 1: Calling MeetingService.join() without explicit open_mode
    must default to 'same_window_tab' to reuse the user's active Chrome session.
    """
    agent = BrowserMeetingAgent()

    with patch("app.services.meeting_service.browser_agent", agent):
        with patch.object(agent, "start_join") as mock_start:
            mock_start.return_value = {
                "success": True,
                "status": JoinStatus.MANUAL_ACTION_REQUIRED.value,
                "platform": MeetingPlatform.GOOGLE_MEET.value,
                "mode": "same_window_tab",
                "cdp_attached": False,
                "message": "Manual action required: Meeting opened in a new tab of your active Chrome window."
            }

            res = MeetingService.join("https://meet.google.com/abc-defg-hij", user_id="user_1")

            assert res["success"] is True
            assert mock_start.called
            _, kwargs = mock_start.call_args
            assert kwargs.get("open_mode") == "same_window_tab"
            assert kwargs.get("user_id") == "user_1"


def test_same_window_tab_when_cdp_unavailable_sets_manual_action_required():
    """
    Test 2: When CDP is not available, start_join with same_window_tab
    starts an in-tab capture loop, reports MANUAL_ACTION_REQUIRED accurately,
    and NEVER invokes playwright persistent context launch.
    """
    agent = BrowserMeetingAgent()

    with patch("app.services.meeting_browser_agent.is_cdp_available", return_value=False), \
         patch.object(agent, "_trigger_audio_pipeline"), \
         patch("threading.Thread") as mock_thread:

        res = agent.start_join("https://meet.google.com/abc-defg-hij", open_mode="same_window_tab", user_id="user_1")

        assert res["success"] is True
        assert res["mode"] == "same_window_tab"
        assert res["cdp_attached"] is False
        assert agent.status == JoinStatus.MANUAL_ACTION_REQUIRED
        assert "Manual action required" in res["message"]
        # Thread started for in-tab loop
        assert mock_thread.called
        thread_kwargs = mock_thread.call_args[1]
        assert thread_kwargs.get("name") == "meeting-in-tab-thread"


@pytest.mark.asyncio
async def test_same_window_tab_cdp_finds_existing_page_and_brings_to_front():
    """
    Test 3: When CDP is active, _execute_join_flow attaches via CDP,
    finds the tab matching the meeting URL that was opened via window.open,
    and brings it to front without redundant navigation.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent.open_mode = "same_window_tab"

    # Mock page in CDP context that has the meeting URL
    mock_existing_page = AsyncMock()
    mock_existing_page.url = "https://meet.google.com/abc-defg-hij"
    mock_existing_page.bring_to_front = AsyncMock()

    mock_cdp_context = MagicMock()
    mock_cdp_context.pages = [mock_existing_page]

    mock_cdp_browser = MagicMock()
    mock_cdp_browser.contexts = [mock_cdp_context]

    mock_playwright = AsyncMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(return_value=mock_cdp_browser)

    with patch("app.services.meeting_browser_agent.is_cdp_available", return_value=True), \
         patch("playwright.async_api.async_playwright") as mock_pw_factory, \
         patch.object(agent, "_join_google_meet", new_callable=AsyncMock) as mock_join_meet:

        mock_pw_factory.return_value.start = AsyncMock(return_value=mock_playwright)

        await agent._execute_join_flow("https://meet.google.com/abc-defg-hij", user_id="user_1")

        assert agent.cdp_attached is True
        assert agent._page == mock_existing_page
        assert mock_existing_page.bring_to_front.called
        assert mock_join_meet.called


@pytest.mark.asyncio
async def test_same_window_tab_cdp_failure_falls_back_to_in_tab_mode():
    """
    Test 4: When CDP attachment fails (e.g. port error), _execute_join_flow
    must fall back safely to in-tab mode, report MANUAL_ACTION_REQUIRED,
    and NEVER launch a separate browser context with fresh profile.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent.open_mode = "same_window_tab"

    mock_playwright = AsyncMock()
    mock_playwright.chromium.connect_over_cdp = AsyncMock(side_effect=Exception("Connection refused on 9222"))

    with patch("app.services.meeting_browser_agent.is_cdp_available", return_value=True), \
         patch("playwright.async_api.async_playwright") as mock_pw_factory, \
         patch.object(agent, "_trigger_audio_pipeline"), \
         patch.object(agent, "_hold_in_tab_session", new_callable=AsyncMock) as mock_hold:

        mock_pw_factory.return_value.start = AsyncMock(return_value=mock_playwright)

        await agent._execute_join_flow("https://meet.google.com/abc-defg-hij", user_id="user_1")

        assert agent.cdp_attached is False
        assert agent.status == JoinStatus.MANUAL_ACTION_REQUIRED
        assert "Manual action required" in agent.message
        assert mock_hold.called
        # Verify launch_persistent_context was NOT called
        assert not hasattr(mock_playwright.chromium, "launch_persistent_context") or not mock_playwright.chromium.launch_persistent_context.called


@pytest.mark.asyncio
async def test_google_meet_lobby_detected_and_ask_to_join_clicked():
    """
    Test 5: In Google Meet lobby, agent detects 'Ask to join' button,
    clicks it, and sets status to REQUEST_SENT ('Request sent').
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._page.url = "https://meet.google.com/abc-defg-hij"
    agent._stop_event = asyncio.Event()

    # Mock lobby page body
    agent._page.inner_text = AsyncMock(return_value="Ready to join? abc-defg-hij")

    # Mock 'Ask to join' button
    mock_ask_btn = AsyncMock()
    mock_ask_btn.is_visible = AsyncMock(return_value=True)
    mock_ask_btn.inner_text = AsyncMock(return_value="Ask to join")
    mock_ask_btn.get_attribute = AsyncMock(return_value=None)  # not disabled
    mock_ask_btn.click = AsyncMock()

    mock_role_locator = MagicMock(first=mock_ask_btn)
    agent._page.get_by_role = MagicMock(return_value=mock_role_locator)

    with patch.object(agent, "_monitor_google_meet", new_callable=AsyncMock) as mock_monitor:
        await agent._join_google_meet("https://meet.google.com/abc-defg-hij")

        assert mock_ask_btn.click.called
        assert agent.status == JoinStatus.REQUEST_SENT
        assert "Request sent" in agent.message
        assert mock_monitor.called
        assert "ask" in mock_monitor.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_google_meet_lobby_detected_and_join_now_clicked():
    """
    Test 6: In Google Meet lobby, agent detects 'Join now' button,
    clicks it, and sets status to REQUEST_SENT.
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._page.url = "https://meet.google.com/abc-defg-hij"
    agent._stop_event = asyncio.Event()

    agent._page.inner_text = AsyncMock(return_value="Ready to join?")

    # Mock 'Join now' button
    mock_join_btn = AsyncMock()
    mock_join_btn.is_visible = AsyncMock(return_value=True)
    mock_join_btn.inner_text = AsyncMock(return_value="Join now")
    mock_join_btn.get_attribute = AsyncMock(return_value=None)
    mock_join_btn.click = AsyncMock()

    mock_role_locator = MagicMock(first=mock_join_btn)
    agent._page.get_by_role = MagicMock(return_value=mock_role_locator)

    with patch.object(agent, "_monitor_google_meet", new_callable=AsyncMock) as mock_monitor:
        await agent._join_google_meet("https://meet.google.com/abc-defg-hij")

        assert mock_join_btn.click.called
        assert agent.status == JoinStatus.REQUEST_SENT
        assert mock_monitor.called


@pytest.mark.asyncio
async def test_google_meet_waiting_for_host_and_admission():
    """
    Test 7: When waiting room text is displayed, status is WAITING_ADMISSION ('Waiting for host').
    When admitted, status transitions to JOINED ('Joined').
    """
    agent = BrowserMeetingAgent()
    agent.platform = MeetingPlatform.GOOGLE_MEET
    agent._page = AsyncMock()
    agent._page.is_closed = MagicMock(return_value=False)
    agent._stop_event = asyncio.Event()

    # Step 1: waiting for host
    agent._page.inner_text = AsyncMock(return_value="Someone will let you in soon")

    mock_in_call = AsyncMock()
    mock_in_call.is_visible = AsyncMock(return_value=False)
    agent._page.locator = MagicMock(return_value=MagicMock(first=mock_in_call))

    monitor_task = asyncio.create_task(agent._monitor_google_meet("Ask to join"))
    await asyncio.sleep(0.05)

    assert agent.status == JoinStatus.WAITING_ADMISSION
    assert agent.waiting_for_host is True
    assert "Waiting for host" in agent.message

    # Step 2: Host clicks admit -> in-call controls appear
    mock_in_call.is_visible = AsyncMock(return_value=True)
    with patch.object(agent, "_trigger_audio_pipeline"), \
         patch.object(agent, "_hold_active_session", new_callable=AsyncMock):
        await asyncio.sleep(1.1)
        assert agent.status == JoinStatus.JOINED
        assert agent.in_meeting is True
        assert agent.waiting_for_host is False

    agent._stop_event.set()
    await monitor_task


def test_confirm_joined_updates_status_in_tab():
    """
    Test 8: confirm_joined() transitions status to JOINED with in_meeting=True
    when user is participating in their active Chrome window.
    """
    agent = BrowserMeetingAgent()
    with patch.object(agent, "_trigger_audio_pipeline"):
        res = agent.confirm_joined()
        assert res["success"] is True
        assert agent.status == JoinStatus.JOINED
        assert agent.in_meeting is True
