import re

import psutil


SUPPORTED_APPS = {

    "zoom.exe": "Zoom",

    "ms-teams.exe": "Microsoft Teams",

    "teams.exe": "Microsoft Teams",

    "chrome.exe": "Google Meet",

    "msedge.exe": "Google Meet",

}


def classify_meeting_url(url):
    if not url:
        return None

    cleaned = url.strip().lower()

    if "meet.google.com" in cleaned:
        return "google"

    if "zoom.us" in cleaned or "/j/" in cleaned or "zoommtg" in cleaned:
        return "zoom"

    if "teams.microsoft.com" in cleaned or "microsoftteams" in cleaned:
        return "teams"

    return None


def detect_meeting_app():

    running = []

    for process in psutil.process_iter(["name"]):

        try:

            name = process.info["name"]

            if not name:

                continue

            if name.lower() in SUPPORTED_APPS:

                running.append(

                    SUPPORTED_APPS[name.lower()]

                )

        except Exception:

            pass

    return list(set(running))