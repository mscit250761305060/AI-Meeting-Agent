import requests


DEBUG_URL = "http://localhost:9222/json"


def detect_google_meet():

    try:

        tabs = requests.get(
            DEBUG_URL,
            timeout=2
        ).json()

        for tab in tabs:

            url = tab.get(
                "url",
                ""
            ).lower()

            title = tab.get(
                "title",
                ""
            )

            if "meet.google.com" in url:

                return {

                    "meeting": True,

                    "url": url,

                    "title": title

                }

        return {

            "meeting": False

        }

    except Exception:

        return {

            "meeting": False

        }