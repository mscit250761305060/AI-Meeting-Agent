"""
app/services/meeting_browser_agent.py

Playwright-based meeting automation agent for AI Meeting Agent.
Handles URL validation, platform identification, automated browser join flow,
permission handling, waiting rooms, host admission, authentication requirements,
and process cleanup.
"""

import asyncio
import logging
import os
import re
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class MeetingPlatform(str, Enum):
    GOOGLE_MEET = "google_meet"
    ZOOM = "zoom"
    TEAMS = "teams"
    UNKNOWN = "unknown"


class JoinStatus(str, Enum):
    IDLE = "idle"
    VALIDATING = "validating"
    LAUNCHING_BROWSER = "launching_browser"
    NAVIGATING = "navigating"
    JOINING = "joining"
    REQUEST_SENT = "request_sent"
    WAITING_ADMISSION = "waiting_admission"
    JOINED = "joined"
    LOGIN_REQUIRED = "login_required"
    MANUAL_ACTION_REQUIRED = "manual_action_required"
    PASSCODE_REQUIRED = "passcode_required"
    ADMISSION_DENIED = "admission_denied"
    MEETING_ENDED = "meeting_ended"
    FAILED = "failed"
    STOPPED = "stopped"


def validate_and_classify_url(url: str) -> Tuple[bool, MeetingPlatform, str]:
    """
    Validates the meeting URL and classifies the platform.
    Returns (is_valid, platform, message_or_normalized_url).
    """
    if not url or not isinstance(url, str):
        return False, MeetingPlatform.UNKNOWN, "Meeting link cannot be empty."

    cleaned = url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        cleaned = "https://" + cleaned

    lower = cleaned.lower()

    # Google Meet pattern: meet.google.com/xxx-yyyy-zzz or meet.google.com/[a-z0-9-]+
    if "meet.google.com" in lower:
        match = re.search(r"meet\.google\.com/([a-zA-Z0-9\-]+)", cleaned)
        if match:
            code = match.group(1).split("?")[0]
            if len(code) >= 9 or "-" in code:
                return True, MeetingPlatform.GOOGLE_MEET, cleaned
        return False, MeetingPlatform.GOOGLE_MEET, "Invalid Google Meet code format. Expected format: https://meet.google.com/xxx-yyyy-zzz"

    # Zoom pattern: zoom.us/j/123456789 or zoom.us/wc/123456789/join
    if "zoom.us" in lower:
        if "/j/" in lower or "/wc/" in lower or "zoommtg" in lower:
            return True, MeetingPlatform.ZOOM, cleaned
        return False, MeetingPlatform.ZOOM, "Invalid Zoom link format. Expected format: https://zoom.us/j/{meeting_id}"

    # Microsoft Teams pattern
    if "teams.microsoft.com" in lower or "teams.live.com" in lower:
        if "meet" in lower or "join" in lower or "l/meetup-join" in lower:
            return True, MeetingPlatform.TEAMS, cleaned
        return False, MeetingPlatform.TEAMS, "Invalid Microsoft Teams meeting link format."

    return False, MeetingPlatform.UNKNOWN, f"Unsupported meeting link '{url}'. Currently supported platforms: Google Meet, Zoom, Microsoft Teams."


def get_chrome_executable() -> Optional[str]:
    """Finds installed Google Chrome binary path on Windows system."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def get_user_browser_profile_dir(user_id: Optional[str] = None) -> Tuple[str, str]:
    """Returns (profile_folder_name, absolute_path_to_profile_dir) for user-isolated browser data."""
    profile_folder = f"user_{user_id}" if user_id else "default_user"
    user_data_dir = os.path.join(Path.cwd(), "data", "browser_profiles", profile_folder)
    os.makedirs(user_data_dir, exist_ok=True)
    return profile_folder, user_data_dir


def clean_stale_singleton_locks(profile_dir: str):
    """Removes stale Chromium Singleton lock files left by interrupted processes on Windows."""
    lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock in lock_files:
        p = Path(profile_dir) / lock
        try:
            if p.exists() or p.is_symlink():
                p.unlink(missing_ok=True)
        except Exception:
            pass


async def is_google_authenticated(context) -> bool:
    """Checks whether the browser context contains active Google authentication cookies."""
    if not context:
        return False
    try:
        cookies = await context.cookies(["https://accounts.google.com", "https://meet.google.com"])
        google_auth_cookie_names = {"SID", "SSID", "SAPISID", "HSID", "__Secure-1PSID", "__Secure-3PSID"}
        return any(c.get("name") in google_auth_cookie_names for c in cookies)
    except Exception:
        return False


def is_cdp_available(cdp_url: Optional[str] = None) -> bool:
    """Checks whether a Chrome instance is listening on the remote debugging port."""
    import urllib.request
    target = cdp_url or os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")
    try:
        url = target.rstrip("/") + "/json/version"
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Meeting-Agent"})
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            return resp.status == 200
    except Exception:
        return False


class BrowserMeetingAgent:
    """
    Autonomous Playwright agent to join supported meeting platforms.
    Runs asynchronously on a dedicated worker thread with event loop.
    Supports both direct CDP attachment to active Chrome windows and in-tab same-window sessions.
    """

    def __init__(self, participant_name: str = "AI Meeting Agent"):
        self.participant_name = participant_name
        self.platform: MeetingPlatform = MeetingPlatform.UNKNOWN
        self.status: JoinStatus = JoinStatus.IDLE
        self.message: str = "Agent is idle."
        self.meeting_url: Optional[str] = None
        self.in_meeting: bool = False
        self.requires_login: bool = False
        self.waiting_for_host: bool = False
        self.open_mode: Optional[str] = None
        self.cdp_attached: bool = False

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._stop_event = asyncio.Event()
        self._monitor_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._launch_event: Optional[threading.Event] = None
        self._launch_error: Optional[str] = None

    def is_worker_alive(self) -> bool:
        """Returns True if the browser worker thread is alive and browser session is active."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                return False
            if self.status in (JoinStatus.FAILED, JoinStatus.STOPPED, JoinStatus.MEETING_ENDED, JoinStatus.ADMISSION_DENIED):
                return False
            if self._page is not None:
                try:
                    if self._page.is_closed():
                        return False
                except Exception:
                    return False
            return True

    def get_status_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "platform": self.platform.value if self.platform else None,
                "join_status": self.status.value,
                "message": self.message,
                "in_meeting": self.in_meeting,
                "requires_login": self.requires_login,
                "waiting_for_host": self.waiting_for_host,
                "meeting_url": self.meeting_url,
                "open_mode": self.open_mode,
                "cdp_attached": self.cdp_attached,
            }

    def _set_status(self, status: JoinStatus, message: str, in_meeting: bool = False,
                    requires_login: bool = False, waiting_for_host: bool = False):
        with self._lock:
            self.status = status
            self.message = message
            self.in_meeting = in_meeting
            self.requires_login = requires_login
            self.waiting_for_host = waiting_for_host
            logger.info(f"[BrowserMeetingAgent] Status -> {status.value}: {message}")

        from app.services.ws_manager import manager
        try:
            manager.broadcast_sync({
                "action": "meeting_status",
                "join_status": status.value,
                "message": message,
                "platform": self.platform.value if self.platform else None
            })
        except Exception:
            pass

    def start_join(
        self,
        url: str,
        wait_for_launch_timeout: float = 6.0,
        user_id: Optional[str] = None,
        open_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Thread-safe entry point to validate and start the join flow.
        When open_mode is 'same_window_tab', reuses the user's active Chrome window/session:
        - If CDP is available on the remote debugging port (9222), connects over CDP to automate the tab in that window.
        - If CDP is not active, does NOT launch a separate empty Chrome window; keeps the meeting tab active
          in the user's Chrome session while starting background discussion capture and AI synthesis.
        """
        is_valid, platform, msg_or_norm = validate_and_classify_url(url)
        if not is_valid:
            self._set_status(JoinStatus.FAILED, msg_or_norm)
            return {
                "success": False,
                "status": JoinStatus.FAILED.value,
                "platform": platform.value,
                "message": msg_or_norm
            }

        # Prevent launching duplicate browser workers if one is already actively running
        if self.is_worker_alive():
            with self._lock:
                return {
                    "success": True,
                    "status": self.status.value,
                    "platform": self.platform.value if self.platform else platform.value,
                    "message": self.message,
                    "link": self.meeting_url,
                    "open_mode": self.open_mode,
                    "cdp_attached": self.cdp_attached
                }

        self.meeting_url = msg_or_norm
        self.platform = platform
        self.open_mode = open_mode or "same_window_tab"
        self._set_status(JoinStatus.VALIDATING, f"Validated {platform.value} link: {self.meeting_url}")

        self._launch_event = threading.Event()
        self._launch_error = None
        self._stop_event = asyncio.Event()

        cdp_url = os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")
        cdp_active = is_cdp_available(cdp_url)

        if self.open_mode == "same_window_tab" and not cdp_active:
            # Reuses the user's active Chrome tab without launching a separate window
            logger.info("Meeting joined in user's active Chrome tab. Running in-tab discussion capture session...")
            self.cdp_attached = False
            self._set_status(
                JoinStatus.MANUAL_ACTION_REQUIRED,
                "Manual action required: Meeting opened in a new tab of your active Chrome window (reusing your existing Google session). "
                "Because standard Chrome restricts external background automation, please click 'Ask to join' or 'Join now' in the meeting tab. "
                "(Tip: Click 'Launch Automation-Ready Chrome' for automatic clicking). Discussion capture and AI project synthesis are actively running."
            )
            self._launch_event.set()

            self._thread = threading.Thread(
                target=self._run_in_tab_loop,
                args=(self.meeting_url, user_id),
                name="meeting-in-tab-thread",
                daemon=True
            )
            self._thread.start()

            return {
                "success": True,
                "status": self.status.value,
                "platform": platform.value,
                "mode": "same_window_tab",
                "cdp_attached": False,
                "message": self.message,
                "link": self.meeting_url
            }

        # Either CDP is active, or standard browser launch was requested (open_mode is None or cdp_active is True)
        self._thread = threading.Thread(
            target=self._run_async_loop,
            args=(self.meeting_url, user_id),
            name="meeting-browser-thread",
            daemon=True
        )
        self._thread.start()

        # Wait briefly for browser initialization to confirm launch
        launched = self._launch_event.wait(timeout=wait_for_launch_timeout)

        if self._launch_error:
            return {
                "success": False,
                "status": JoinStatus.FAILED.value,
                "platform": platform.value,
                "message": f"Browser launch failed: {self._launch_error}"
            }

        if not launched and (self._thread is None or not self._thread.is_alive()):
            return {
                "success": False,
                "status": JoinStatus.FAILED.value,
                "platform": platform.value,
                "message": self.message or "Browser worker exited unexpectedly during startup."
            }

        return {
            "success": True,
            "status": self.status.value,
            "platform": platform.value,
            "mode": "same_window_tab" if open_mode == "same_window_tab" else "browser",
            "cdp_attached": self.cdp_attached,
            "message": self.message or f"Launching automated browser session for {platform.value}."
        }

    def _run_in_tab_loop(self, url: str, user_id: Optional[str] = None):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._trigger_audio_pipeline()
            self._loop.run_until_complete(self._hold_in_tab_session())
        except Exception as e:
            logger.exception("Error in in-tab meeting loop: %s", e)
            self._set_status(JoinStatus.FAILED, f"Meeting session error: {e}")
        finally:
            self._loop.close()
            try:
                from app.services import meeting_state
                meeting_state.end_meeting(final_status=self.status.value, final_message=self.message)
            except Exception:
                pass

    async def _hold_in_tab_session(self):
        """Maintains in-tab meeting session while user is participating in their active Chrome window."""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.5)

    def confirm_joined(self) -> Dict[str, Any]:
        """Marks meeting status as active call confirmed when participating in active Chrome tab."""
        self._set_status(
            JoinStatus.JOINED,
            "In Meeting (Active Call Confirmed). Discussion capture and automated project synthesis active.",
            in_meeting=True
        )
        self._trigger_audio_pipeline()
        return {"success": True, "status": JoinStatus.JOINED.value, "message": "In-call status confirmed."}

    def launch_cdp_browser(self, target_url: str = "http://127.0.0.1:8000/dashboard", user_id: Optional[str] = None, port: int = 9222):
        """
        Launches Google Chrome with --remote-debugging-port so Playwright can attach
        directly to tabs in this same Chrome window for hands-free automation.
        """
        import subprocess
        chrome_exe = get_chrome_executable()
        if not chrome_exe:
            return {"success": False, "message": "Google Chrome executable not detected on system."}

        profile_folder, user_data_dir = get_user_browser_profile_dir(user_id)
        clean_stale_singleton_locks(user_data_dir)

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            target_url
        ]
        try:
            subprocess.Popen(cmd)
            return {
                "success": True,
                "port": port,
                "profile_path": user_data_dir,
                "message": f"Google Chrome launched with Remote Debugging on port {port}. You can sign in and use the AI Meeting Agent in this window."
            }
        except Exception as e:
            return {"success": False, "message": f"Failed to launch Chrome with remote debugging: {e}"}

    def _run_async_loop(self, url: str, user_id: Optional[str] = None):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._execute_join_flow(url, user_id))
        except Exception as e:
            logger.exception("Error in browser agent event loop: %s", e)
            self._launch_error = str(e)
            self._set_status(JoinStatus.FAILED, f"Browser automation error: {str(e)}")
            if self._launch_event:
                self._launch_event.set()
        finally:
            try:
                self._loop.run_until_complete(self._cleanup_playwright())
            except Exception:
                pass
            self._loop.close()
            # Synchronize lifecycle: when browser worker ends completely
            try:
                from app.services import meeting_state
                if not self.in_meeting or self.status in (JoinStatus.FAILED, JoinStatus.STOPPED, JoinStatus.MEETING_ENDED, JoinStatus.ADMISSION_DENIED):
                    meeting_state.end_meeting(final_status=self.status.value, final_message=self.message)
            except Exception:
                pass

    async def _execute_join_flow(self, url: str, user_id: Optional[str] = None):
        from playwright.async_api import async_playwright

        self._set_status(JoinStatus.LAUNCHING_BROWSER, "Starting browser instance with audio permissions...")

        # By default, use headed mode (headless=False) so user can see Google Meet, sign in if needed, and observe admission
        headless = os.getenv("HEADLESS_MEETING", "false").lower() in ("true", "1", "yes")
        cdp_url = os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")

        # 1. First, check if a running Chrome instance is available over CDP to reuse the user's existing window!
        if is_cdp_available(cdp_url):
            logger.info("Found active Chrome remote debugging endpoint at %s. Connecting over CDP...", cdp_url)
            self._set_status(JoinStatus.NAVIGATING, "Connecting to your active Chrome window over CDP...")
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
                self.cdp_attached = True

                contexts = self._browser.contexts
                self._context = contexts[0] if contexts else await self._browser.new_context()

                # Find if a tab with this meeting URL is already open in that Chrome window
                target_page = None
                normalized_base = url.lower().split("?")[0].rstrip("/")
                for _ in range(5):
                    for p in self._context.pages:
                        p_url = p.url.lower().split("?")[0].rstrip("/")
                        if normalized_base in p_url or (p_url in normalized_base and len(p_url) > 15):
                            target_page = p
                            break
                    if target_page:
                        break
                    await asyncio.sleep(0.4)

                if target_page:
                    self._page = target_page
                    try:
                        await self._page.bring_to_front()
                    except Exception:
                        pass
                else:
                    self._page = await self._context.new_page()

                self._launch_error = None
                if self._launch_event:
                    self._launch_event.set()

                self._set_status(JoinStatus.NAVIGATING, f"Navigating to meeting in active Chrome window: {url}")

                if self.platform == MeetingPlatform.GOOGLE_MEET:
                    await self._join_google_meet(url)
                elif self.platform == MeetingPlatform.ZOOM:
                    await self._join_zoom(url)
                elif self.platform == MeetingPlatform.TEAMS:
                    await self._join_teams(url)
                else:
                    self._set_status(JoinStatus.FAILED, "Unsupported platform.")
                return
            except Exception as cdp_err:
                logger.warning("CDP connection failed: %s. Using in-tab session fallback.", cdp_err)
                self.cdp_attached = False
                if self.open_mode == "same_window_tab":
                    self._set_status(
                        JoinStatus.MANUAL_ACTION_REQUIRED,
                        "Manual action required: Meeting opened in a new tab of your active Chrome window (reusing your existing Google session). "
                        "CDP automation could not attach. Please click 'Ask to join' or 'Join now' in the meeting tab. "
                        "Discussion capture and AI project synthesis are actively running."
                    )
                    if self._launch_event:
                        self._launch_event.set()
                    self._trigger_audio_pipeline()
                    await self._hold_in_tab_session()
                    return

        # 2. If CDP is not available, launch persistent context (used in standalone/test mode)
        profile_folder, user_data_dir = get_user_browser_profile_dir(user_id)
        clean_stale_singleton_locks(user_data_dir)

        chrome_exe = get_chrome_executable()
        use_chrome = chrome_exe is not None

        try:
            self._playwright = await async_playwright().start()
            browser_args = [
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            launch_kwargs = {
                "user_data_dir": user_data_dir,
                "headless": headless,
                "permissions": ["microphone", "camera"],
                "args": browser_args,
                "viewport": {"width": 1280, "height": 720},
            }
            if use_chrome:
                launch_kwargs["channel"] = "chrome"

            try:
                self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as exc:
                logger.warning("Persistent context launch failed: %s. Falling back gracefully.", exc)
                if "channel" in launch_kwargs:
                    launch_kwargs.pop("channel", None)
                    try:
                        self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
                    except Exception as exc2:
                        logger.warning("Persistent profile directory in use or locked: %s. Launching standard browser.", exc2)
                        self._browser = await self._playwright.chromium.launch(headless=headless, args=browser_args)
                        self._context = await self._browser.new_context(
                            permissions=["microphone", "camera"],
                            viewport={"width": 1280, "height": 720}
                        )
                else:
                    logger.warning("Persistent profile directory in use: %s. Launching standard browser.", exc)
                    self._browser = await self._playwright.chromium.launch(headless=headless, args=browser_args)
                    self._context = await self._browser.new_context(
                        permissions=["microphone", "camera"],
                        viewport={"width": 1280, "height": 720}
                    )

            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            self._launch_error = None
            if self._launch_event:
                self._launch_event.set()

            self._set_status(JoinStatus.NAVIGATING, f"Navigating to meeting: {url}")

            if self.platform == MeetingPlatform.GOOGLE_MEET:
                await self._join_google_meet(url)
            elif self.platform == MeetingPlatform.ZOOM:
                await self._join_zoom(url)
            elif self.platform == MeetingPlatform.TEAMS:
                await self._join_teams(url)
            else:
                self._set_status(JoinStatus.FAILED, "Unsupported platform.")

        except Exception as e:
            logger.exception("Join execution failed: %s", e)
            self._launch_error = str(e)
            self._set_status(JoinStatus.FAILED, f"Meeting join failed: {str(e)}")
            if self._launch_event:
                self._launch_event.set()

    async def _await_google_login(self, target_url: str) -> bool:
        """Keeps browser window visible and open while user completes Google sign-in."""
        page = self._page
        self.requires_login = True
        logger.info("[BrowserMeetingAgent] Waiting for user to complete Google sign-in in browser window...")
        start_wait = time.time()
        login_timeout = 180

        while not self._stop_event.is_set() and self.requires_login and (time.time() - start_wait < login_timeout):
            try:
                if page.is_closed():
                    self._set_status(JoinStatus.STOPPED, "Browser window closed by user.")
                    return False

                curr = page.url.lower()
                body = ""
                try:
                    body = await page.inner_text("body")
                except Exception:
                    pass

                has_auth = await is_google_authenticated(self._context)
                on_meet_page = "meet.google.com" in curr or curr.startswith(target_url.lower())

                is_denied = any(h in body for h in [
                    "You can't join this video call",
                    "You can't join this call",
                    "You can't join this meeting",
                    "You aren't allowed to join this call",
                    "Can't join meeting",
                ])

                sign_in_completed = False
                if has_auth and not is_denied:
                    sign_in_completed = True
                elif has_auth and "accounts.google.com" not in curr:
                    sign_in_completed = True
                elif on_meet_page and "accounts.google.com" not in curr and "signin" not in curr and not is_denied:
                    if not any(msg in body for msg in ["You must be signed in", "Sign in with a Google Account", "Sign in to join", "Switch account"]):
                        sign_in_completed = True

                if sign_in_completed:
                    logger.info("[BrowserMeetingAgent] Google authentication verified! Returning to meeting lobby...")
                    self.requires_login = False
                    self._set_status(JoinStatus.JOINING, "Authentication successful. Entering meeting lobby...")
                    if not on_meet_page or is_denied:
                        try:
                            await page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                        except Exception:
                            pass
                    await asyncio.sleep(1.5)
                    return True

            except Exception as e:
                logger.debug("Error while awaiting Google sign-in: %s", e)
            await asyncio.sleep(1.0)

        if time.time() - start_wait >= login_timeout:
            self._set_status(JoinStatus.FAILED, "Google sign-in timed out. Please sign in via 'Connect Google' or authentication browser.")
            return False

        return False

    async def _join_google_meet(self, url: str):
        page = self._page
        logger.info("Navigating to Google Meet: %s", url)
        self._set_status(JoinStatus.NAVIGATING, f"Connecting to Google Meet: {url}")

        normalized_base = url.lower().split("?")[0].rstrip("/")
        if normalized_base not in page.url.lower():
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except Exception as e:
                self._set_status(JoinStatus.FAILED, f"Failed to navigate to Google Meet: {str(e)}")
                return
            await asyncio.sleep(1.0)
        else:
            logger.info("Meeting page already loaded in active tab (%s).", page.url)
            await asyncio.sleep(0.2)

        # 1. Check for immediate Google Sign-in / URL redirection
        current_url = page.url.lower()
        if "accounts.google.com" in current_url or "signin" in current_url:
            self._set_status(
                JoinStatus.LOGIN_REQUIRED,
                "Google account login is required to join this meeting. Please sign in to your Google Account in the browser window.",
                requires_login=True
            )
            logged_in = await self._await_google_login(url)
            if not logged_in:
                return

        # 2. Check for invalid or expired code
        body_initial = await page.inner_text("body")
        if any(msg in body_initial for msg in ["Invalid meeting code", "Check your meeting code", "No such meeting", "This meeting has expired"]):
            self._set_status(
                JoinStatus.FAILED,
                "Meeting Unavailable: Google Meet meeting code is invalid or has expired. Next step: Verify the meeting code or request a fresh link."
            )
            return

        # 3. Enter lobby preparation loop: dismiss popups, set participant name, mute mic/cam, and find join button
        self._set_status(JoinStatus.JOINING, "Initializing lobby devices and preparing to join...")

        async def _dismiss_popups():
            dismiss_candidates = [
                "button:has-text('Dismiss')",
                "button:has-text('Got it')",
                "button:has-text('Close')",
                "button:has-text('Continue without microphone')",
                "button:has-text('Continue without camera')",
                "button:has-text('Don\\'t allow')",
                "[aria-label='Close' i]",
                "[aria-label='Close dialog' i]",
            ]
            for sel in dismiss_candidates:
                try:
                    for elem in await page.locator(sel).all():
                        if await elem.is_visible():
                            await elem.click()
                            await asyncio.sleep(0.2)
                except Exception:
                    pass

        async def _mute_media():
            try:
                mic_btn = page.locator("[aria-label*='turn off microphone' i], [aria-label*='mute mic' i]").first
                if await mic_btn.is_visible(timeout=500):
                    await mic_btn.click()
            except Exception:
                pass
            try:
                cam_btn = page.locator("[aria-label*='turn off camera' i], [aria-label*='turn off video' i]").first
                if await cam_btn.is_visible(timeout=500):
                    await cam_btn.click()
            except Exception:
                pass

        async def _fill_name_if_needed():
            name_selectors = [
                "input[aria-label*='name' i]",
                "input[placeholder*='name' i]",
                "input[jsname='YPqjbf']",
                "input[type='text']:not([readonly])",
            ]
            for sel in name_selectors:
                try:
                    field = page.locator(sel).first
                    if await field.is_visible(timeout=500):
                        current_val = await field.input_value()
                        if not current_val or current_val.strip() != self.participant_name:
                            await field.click()
                            await field.fill(self.participant_name)
                            await field.press("Tab")
                            await asyncio.sleep(0.3)
                        return True
                except Exception:
                    pass
            return False

        async def _find_join_button():
            # Method 1: Playwright accessible role locators
            try:
                role_btn = page.get_by_role("button", name=re.compile(r"^(ask to join|join now|join meeting|join)$", re.I)).first
                if await role_btn.is_visible(timeout=400):
                    btn_text = (await role_btn.inner_text()).strip()
                    if not any(ign in btn_text.lower() for ign in ["phone", "present", "switch", "cast", "share"]):
                        is_disabled = (
                            await role_btn.get_attribute("disabled") is not None
                            or await role_btn.get_attribute("aria-disabled") == "true"
                        )
                        if not is_disabled:
                            return role_btn, btn_text or "Join"
                        return role_btn, "disabled"
            except Exception:
                pass

            # Method 2: Broader role matching
            try:
                role_btn = page.get_by_role("button", name=re.compile(r"ask to join|join now", re.I)).first
                if await role_btn.is_visible(timeout=400):
                    btn_text = (await role_btn.inner_text()).strip()
                    if not any(ign in btn_text.lower() for ign in ["phone", "present", "switch", "cast", "share"]):
                        is_disabled = (
                            await role_btn.get_attribute("disabled") is not None
                            or await role_btn.get_attribute("aria-disabled") == "true"
                        )
                        if not is_disabled:
                            return role_btn, btn_text or "Join"
                        return role_btn, "disabled"
            except Exception:
                pass

            # Method 3: Primary Google Meet JSName CTA button (jsname='Qx7uuf')
            try:
                for sel in ["button[jsname='Qx7uuf']", "[role='button'][jsname='Qx7uuf']"]:
                    cta_btn = page.locator(sel).first
                    if await cta_btn.is_visible(timeout=400):
                        btn_text = (await cta_btn.inner_text()).strip()
                        if not any(ign in btn_text.lower() for ign in ["phone", "present", "switch", "cast", "share"]):
                            is_disabled = (
                                await cta_btn.get_attribute("disabled") is not None
                                or await cta_btn.get_attribute("aria-disabled") == "true"
                            )
                            if not is_disabled:
                                return cta_btn, btn_text or "Join"
                            return cta_btn, "disabled"
            except Exception:
                pass

            # Method 4: Text and CSS selector candidates
            text_selectors = [
                "button:has-text('Ask to join')",
                "button:has-text('Join now')",
                "button:has-text('Join')",
                "[role='button']:has-text('Ask to join')",
                "[role='button']:has-text('Join now')",
                "[role='button']:has-text('Join')",
                "[aria-label*='Ask to join' i]",
                "[aria-label*='Join now' i]",
                "[aria-label*='Join meeting' i]",
                "//button[contains(., 'Ask to join') or contains(., 'Join now') or contains(., 'Join')]",
                "//div[@role='button'][contains(., 'Ask to join') or contains(., 'Join now')]",
            ]
            for sel in text_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=300):
                        text = (await btn.inner_text()).strip()
                        if any(ign in text.lower() for ign in ["phone", "present", "switch", "cast", "share"]):
                            continue
                        is_disabled = (
                            await btn.get_attribute("disabled") is not None
                            or await btn.get_attribute("aria-disabled") == "true"
                        )
                        if not is_disabled:
                            return btn, text or "Join"
                        return btn, "disabled"
                except Exception:
                    pass

            return None, None

        # 4. Polling loop: Wait for lobby initialization, fill name, and click join button (up to 30 seconds)
        clicked_button_text = None
        start_time = time.time()
        timeout_seconds = 30

        while (time.time() - start_time < timeout_seconds) and not self._stop_event.is_set():
            await _dismiss_popups()
            await _mute_media()

            # Check for Google Meet access denial / inability to join first
            body_text = await page.inner_text("body")
            is_denied_heading = any(h in body_text for h in [
                "You can't join this video call",
                "You can't join this call",
                "You can't join this meeting",
                "You aren't allowed to join this call",
                "Can't join meeting",
            ])

            if is_denied_heading:
                logger.info("[BrowserMeetingAgent] Google Meet displayed access restriction. Diagnosing root cause...")
                has_google_auth = await is_google_authenticated(self._context)

                # Diagnosis 1: Domain Restriction / Wrong Account ("Switch account")
                switch_btn = page.locator("button:has-text('Switch account'), a:has-text('Switch account'), [role='button']:has-text('Switch account'), button:has-text('Sign in with a different account')").first
                is_switch_visible = False
                try:
                    is_switch_visible = await switch_btn.is_visible(timeout=500)
                except Exception:
                    pass

                is_domain_text = any(d in body_text for d in [
                    "Switch to an account that has access",
                    "You aren't allowed to join this call",
                    "Your domain is not allowed",
                    "Ask the meeting organizer to give you access",
                    "Only people in",
                ])

                if is_switch_visible or (has_google_auth and is_domain_text) or "switch account" in body_text.lower():
                    logger.info("[BrowserMeetingAgent] Restriction diagnosed as organization domain restriction / account mismatch.")
                    if is_switch_visible:
                        try:
                            await switch_btn.click()
                        except Exception:
                            pass
                    else:
                        try:
                            await page.goto("https://accounts.google.com/AccountChooser", wait_until="domcontentloaded")
                        except Exception:
                            pass

                    self._set_status(
                        JoinStatus.LOGIN_REQUIRED,
                        "Organization Domain Restriction: Google Meet requires an authorized organization account. Next step: Please switch to or sign in with your authorized organization Google Workspace account in the open browser window.",
                        requires_login=True
                    )
                    logged_in = await self._await_google_login(url)
                    if not logged_in:
                        return
                    start_time = time.time()
                    continue

                # Diagnosis 2: Host Explicitly Denied Admission
                if any(denied_msg in body_text for denied_msg in [
                    "The host has denied your request",
                    "The host denied your request to join",
                    "Someone in the call denied your request",
                    "Your request to join was denied",
                    "Someone in the meeting removed you",
                    "You've been removed from the meeting",
                ]):
                    logger.info("[BrowserMeetingAgent] Restriction diagnosed as host admission denial.")
                    self._set_status(
                        JoinStatus.ADMISSION_DENIED,
                        "Host Denied Admission: The meeting host declined admission to the AI Meeting Agent. Next step: Ask the meeting host to admit the agent when you request to join again.",
                        waiting_for_host=False
                    )
                    return

                # Diagnosis 3: Meeting Code Expired / Ended / Invalid
                if any(expired_msg in body_text for expired_msg in [
                    "This meeting has expired",
                    "This video call has ended",
                    "Check your meeting code and try again",
                    "No such meeting",
                    "Invalid meeting code",
                ]):
                    logger.info("[BrowserMeetingAgent] Restriction diagnosed as invalid or expired meeting code.")
                    self._set_status(
                        JoinStatus.FAILED,
                        "Meeting Unavailable: The meeting code has expired, ended, or does not exist. Next step: Verify the meeting code or ask the organizer for an active meeting link."
                    )
                    return

                # Diagnosis 4: Unauthenticated User / Sign-in required (Guest access disabled by host)
                sign_in_btn = page.locator("button:has-text('Sign in'), a:has-text('Sign in'), [role='button']:has-text('Sign in'), button:has-text('Sign in to join')").first
                is_signin_visible = False
                try:
                    is_signin_visible = await sign_in_btn.is_visible(timeout=500)
                except Exception:
                    pass

                is_signin_text = any(s in body_text for s in [
                    "You must be signed in with a Google Account",
                    "Sign in with a Google Account",
                    "Sign in to join this meeting",
                    "Sign in to join this video call",
                    "You're not signed in to a Google Account",
                ])

                if is_signin_visible or is_signin_text or not has_google_auth:
                    logger.info("[BrowserMeetingAgent] Restriction diagnosed as unauthenticated guest. Google sign-in required.")
                    if is_signin_visible:
                        try:
                            await sign_in_btn.click()
                        except Exception:
                            pass
                    else:
                        try:
                            await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
                        except Exception:
                            pass

                    self._set_status(
                        JoinStatus.LOGIN_REQUIRED,
                        "Google Sign-In Required: Guest access without a Google account is disabled for this meeting. Next step: Please sign in to your Google Account in the open browser window to join.",
                        requires_login=True
                    )
                    logged_in = await self._await_google_login(url)
                    if not logged_in:
                        return
                    start_time = time.time()
                    continue

                # Diagnosis 5: Fallback for generic access denial
                self._set_status(
                    JoinStatus.ADMISSION_DENIED,
                    "Google Meet Access Restricted: Google Meet displayed 'You can't join this video call' (domain restriction or host admission required). Next step: Sign in with an authorized Google account or ask the meeting host to allow external participants.",
                    waiting_for_host=False
                )
            # Check if standard login required appeared during lobby load (without denial heading)
            if any(msg in body_text for msg in [
                "You must be signed in",
                "Sign in to join this meeting",
                "Sign in to join this video call",
                "Sign in with a Google Account"
            ]):
                self._set_status(
                    JoinStatus.LOGIN_REQUIRED,
                    "Google account login is required to join this meeting. Please sign in via the browser window with your Google Account.",
                    requires_login=True
                )
                logged_in = await self._await_google_login(url)
                if not logged_in:
                    return
                start_time = time.time()
                continue

            # Check if name field is present
            await _fill_name_if_needed()

            # Search for join button in meeting lobby
            btn_elem, btn_text = await _find_join_button()
            if btn_elem:
                if btn_text == "disabled":
                    self._set_status(JoinStatus.JOINING, "Meeting lobby detected. Initializing devices and waiting for Join button to activate...")
                else:
                    try:
                        logger.info("Found Google Meet join button: '%s'. Clicking...", btn_text)
                        await btn_elem.click()
                        clicked_button_text = btn_text or "Join"
                        is_ask = "ask" in clicked_button_text.lower()
                        self._set_status(
                            JoinStatus.REQUEST_SENT,
                            f"Request sent. Clicked '{clicked_button_text}'. Waiting for admission...",
                            waiting_for_host=is_ask
                        )
                        break
                    except Exception as e:
                        logger.warning("Failed to click join button: %s. Retrying...", e)
            else:
                if any(msg in body_text for msg in ["Getting ready", "You'll be able to join in just a moment", "Ready to join?"]):
                    self._set_status(JoinStatus.JOINING, "Meeting lobby detected. Loading devices and join controls...")

            # Check if already in call (e.g. host or auto-admit)
            in_call_sel = [
                "[aria-label*='Leave call' i]",
                "[aria-label*='End call' i]",
                "button[data-call-ended='false']",
                "[aria-label*='call controls' i]",
            ]
            for sel in in_call_sel:
                try:
                    if await page.locator(sel).first.is_visible(timeout=300):
                        logger.info("Detected in-call controls directly without clicking join.")
                        clicked_button_text = "Already in call"
                        break
                except Exception:
                    pass
            if clicked_button_text:
                break

            await asyncio.sleep(1.0)

        if not clicked_button_text:
            # Diagnostics on failure
            body_after = await page.inner_text("body")
            buttons_found = []
            try:
                for b in await page.locator("button, [role='button']").all():
                    if await b.is_visible():
                        t = (await b.inner_text()).strip()
                        aria = (await b.get_attribute("aria-label")) or ""
                        buttons_found.append(t or aria)
            except Exception:
                pass

            logger.warning(
                "Could not locate 'Ask to join' or 'Join now' button after %ds. Visible buttons: %s. Page title: %s",
                timeout_seconds, buttons_found, await page.title()
            )

            # Check if sign in is shown
            if "Sign in" in body_after or any("Sign in" in b for b in buttons_found):
                self._set_status(
                    JoinStatus.LOGIN_REQUIRED,
                    "Google account login is required to join this meeting. Please sign in via the browser window.",
                    requires_login=True
                )
                logged_in = await self._await_google_login(url)
                if not logged_in:
                    return

            if not clicked_button_text:
                self._set_status(
                    JoinStatus.FAILED,
                    f"Could not locate 'Ask to join' or 'Join now' button. (Visible buttons: {', '.join(buttons_found[:4]) if buttons_found else 'none'}). Ensure the meeting link is active and valid."
                )
                return


        # 5. Monitor state transitions (Waiting room vs In meeting vs Denied)
        await self._monitor_google_meet(clicked_button_text)

    async def _monitor_google_meet(self, button_clicked_text: str):
        page = self._page
        logger.info("Monitoring Google Meet after action: '%s'", button_clicked_text)

        if "ask to join" in button_clicked_text.lower() or "ask" in button_clicked_text.lower():
            self._set_status(
                JoinStatus.WAITING_ADMISSION,
                "Waiting for host. Request submitted, waiting for host to admit into call...",
                waiting_for_host=True
            )
        elif "already" in button_clicked_text.lower():
            self._set_status(
                JoinStatus.JOINED,
                "Joined Google Meet call as participant.",
                in_meeting=True,
                waiting_for_host=False
            )
            self._trigger_audio_pipeline()
            await self._hold_active_session()
            return
        else:
            self._set_status(
                JoinStatus.JOINING,
                "Request sent. Connecting to Google Meet call...",
                waiting_for_host=False
            )

        # Monitor loop: keep checking until host admits, host denies, or meeting is stopped
        while not self._stop_event.is_set():
            try:
                if page.is_closed():
                    self._set_status(JoinStatus.STOPPED, "Browser window was closed.")
                    return

                # 1. Check in-call controls first (Host admitted or direct entry)
                in_call_sel = [
                    "[aria-label*='Leave call' i]",
                    "[aria-label*='End call' i]",
                    "button[data-call-ended='false']",
                    "[data-meeting-title]",
                    "[aria-label*='call controls' i]",
                    "[aria-label*='People' i]",
                    "[aria-label*='Chat with everyone' i]",
                ]
                in_call = False
                for sel in in_call_sel:
                    try:
                        if await page.locator(sel).first.is_visible(timeout=400):
                            in_call = True
                            break
                    except Exception:
                        pass

                if in_call:
                    self._set_status(
                        JoinStatus.JOINED,
                        "Successfully joined Google Meet call as participant.",
                        in_meeting=True,
                        waiting_for_host=False
                    )
                    # Trigger audio capture and transcription pipeline
                    self._trigger_audio_pipeline()
                    # Continue holding connection open until stopped
                    await self._hold_active_session()
                    return

                body_text = await page.inner_text("body")

                # 2. Check if host denied admission
                if any(denied in body_text for denied in [
                    "You can't join this call",
                    "Someone in the meeting removed you",
                    "The host has denied your request",
                    "You've been removed from the meeting",
                    "Your request to join was denied"
                ]):
                    self._set_status(
                        JoinStatus.ADMISSION_DENIED,
                        "Meeting host denied admission to the Google Meet call.",
                        waiting_for_host=False
                    )
                    return

                # 3. Check if meeting has ended
                if any(ended in body_text for ended in [
                    "The meeting has ended",
                    "You left the meeting",
                    "Everyone has left",
                    "This video call has ended"
                ]):
                    self._set_status(
                        JoinStatus.MEETING_ENDED,
                        "Google Meet call has ended.",
                        waiting_for_host=False
                    )
                    return

                # 4. Check if waiting for host
                if any(waiting in body_text.lower() for waiting in [
                    "waiting",
                    "asking to join",
                    "let you in",
                    "someone will let you in",
                    "you'll join the call when"
                ]):
                    self._set_status(
                        JoinStatus.WAITING_ADMISSION,
                        "Waiting for host: Waiting for meeting host to admit the AI Meeting Agent...",
                        waiting_for_host=True
                    )

            except Exception as e:
                logger.debug("Monitoring check exception: %s", e)

            await asyncio.sleep(1.0)


    async def _join_zoom(self, url: str):
        page = self._page

        # Zoom web client URL transform: zoom.us/j/{id} -> zoom.us/wc/{id}/join
        web_url = url
        match = re.search(r"zoom\.us/j/(\d+)", url)
        if match:
            meeting_id = match.group(1)
            # Check for pwd parameter
            pwd_part = ""
            if "pwd=" in url:
                pwd_match = re.search(r"pwd=([^&]+)", url)
                if pwd_match:
                    pwd_part = f"?pwd={pwd_match.group(1)}"
            web_url = f"https://app.zoom.us/wc/{meeting_id}/join{pwd_part}"

        self._set_status(JoinStatus.NAVIGATING, f"Connecting to Zoom Web Client: {web_url}")

        try:
            await page.goto(web_url, wait_until="networkidle", timeout=30000)
        except Exception:
            try:
                await page.goto(web_url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                self._set_status(JoinStatus.FAILED, f"Failed to navigate to Zoom: {str(e)}")
                return

        await asyncio.sleep(2)

        # 1. Check for Sign in required
        body_text = await page.inner_text("body")
        if "Sign In to Join" in body_text or "Please sign in to join" in body_text:
            self._set_status(
                JoinStatus.LOGIN_REQUIRED,
                "Zoom requires user authentication to join this meeting.",
                requires_login=True
            )
            return

        # 2. Check for Passcode
        passcode_input = page.locator("input#inputpasscode, input[name='password']").first
        try:
            if await passcode_input.is_visible(timeout=2000):
                self._set_status(
                    JoinStatus.PASSCODE_REQUIRED,
                    "Meeting requires a passcode to join. Please provide a link containing ?pwd= or passcode."
                )
                return
        except Exception:
            pass

        # 3. Enter Name
        name_input = page.locator("input#inputname, input[name='user_name'], input[placeholder*='Name' i]").first
        try:
            if await name_input.is_visible(timeout=2000):
                await name_input.fill(self.participant_name)
        except Exception:
            pass

        # 4. Click Join
        join_btn = page.locator("button#joinBtn, button:has-text('Join')").first
        try:
            if await join_btn.is_visible(timeout=2000):
                await join_btn.click()
                self._set_status(JoinStatus.JOINING, "Submitted Zoom join request...")
        except Exception as e:
            self._set_status(JoinStatus.FAILED, f"Could not click Zoom join button: {e}")
            return

        # 5. Monitor Zoom state (waiting room vs joined)
        await self._monitor_zoom()

    async def _monitor_zoom(self):
        page = self._page
        for _ in range(60):
            if self._stop_event.is_set():
                break

            try:
                body_text = await page.inner_text("body")
                if "host will let you in soon" in body_text.lower() or "waiting room" in body_text.lower():
                    self._set_status(
                        JoinStatus.WAITING_ADMISSION,
                        "Placed in Zoom waiting room. Waiting for host admission...",
                        waiting_for_host=True
                    )

                # Check if in call
                leave_btn = page.locator("button:has-text('Leave'), button.footer-button__button").first
                if await leave_btn.is_visible(timeout=500):
                    self._set_status(
                        JoinStatus.JOINED,
                        "Successfully joined Zoom meeting as participant.",
                        in_meeting=True
                    )
                    self._trigger_audio_pipeline()
                    await self._hold_active_session()
                    return

                if "meeting has ended" in body_text.lower() or "meeting has been ended" in body_text.lower():
                    self._set_status(JoinStatus.MEETING_ENDED, "Zoom meeting was ended by host.")
                    return

            except Exception:
                pass

            await asyncio.sleep(1)

    async def _join_teams(self, url: str):
        page = self._page
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
            # Check for "Continue on this browser"
            browser_join = page.locator("button:has-text('Continue on this browser'), a:has-text('Continue on this browser')").first
            if await browser_join.is_visible(timeout=3000):
                await browser_join.click()
                self._set_status(JoinStatus.JOINING, "Selected browser join for Microsoft Teams...")
            else:
                self._set_status(
                    JoinStatus.LOGIN_REQUIRED,
                    "Microsoft Teams requires sign-in or manual browser selection for this meeting."
                )
        except Exception as e:
            self._set_status(JoinStatus.FAILED, f"Microsoft Teams join failed: {e}")

    async def _hold_active_session(self):
        """Maintains browser session while meeting is active."""
        page = self._page
        while not self._stop_event.is_set() and self.in_meeting:
            try:
                body_text = await page.inner_text("body")
                if any(k in body_text.lower() for k in ["you left the meeting", "meeting has ended", "call ended"]):
                    self._set_status(JoinStatus.MEETING_ENDED, "Meeting was terminated.")
                    break
            except Exception:
                break
            await asyncio.sleep(2)

    def _trigger_audio_pipeline(self):
        """Starts audio capture and live transcription upon genuine meeting admission."""
        logger.info("Triggering audio capture and transcription pipeline for active meeting...")
        try:
            from app.services import meeting_state
            if not meeting_state.runtime_started:
                meeting_state.start_runtime()
        except Exception as e:
            logger.warning(f"Could not automatically trigger audio runtime: {e}")

    def stop(self) -> Dict[str, Any]:
        """Stops the meeting join session and cleans up resources cleanly."""
        self._set_status(JoinStatus.STOPPED, "Meeting session stopped by user.")
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._cleanup_playwright(), self._loop)

        return {"success": True, "message": "Browser session closed and resources cleaned."}

    async def _cleanup_playwright(self):
        self._stop_event.set()
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self.in_meeting = False
        logger.info("[BrowserMeetingAgent] Playwright browser and contexts cleaned up.")

    def open_auth_window(self, target_url: str = "https://accounts.google.com/", user_id: Optional[str] = None):
        """
        Launches the user-isolated browser profile in a visible window so the user
        can safely sign in with their own Google credentials.
        """
        import subprocess
        profile_folder, user_data_dir = get_user_browser_profile_dir(user_id)
        clean_stale_singleton_locks(user_data_dir)

        chrome_exe = get_chrome_executable()
        if chrome_exe:
            cmd = [chrome_exe, f"--user-data-dir={user_data_dir}", target_url]
            subprocess.Popen(cmd)
            return {
                "success": True,
                "profile_path": user_data_dir,
                "profile_folder": profile_folder,
                "message": f"Google Chrome authentication window opened in profile '{profile_folder}'. Sign in to your Google Account, then close the window or return to the dashboard to join."
            }
        else:
            return {
                "success": False,
                "profile_path": user_data_dir,
                "profile_folder": profile_folder,
                "message": "Google Chrome executable not detected on system. Please install Google Chrome or sign in via standard browser."
            }


# Singleton agent instance
browser_agent = BrowserMeetingAgent()

