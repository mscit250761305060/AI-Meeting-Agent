try:
    import google.genai as genai
except ImportError as e:
    raise ImportError(
        "Failed to import google.genai. Activate the project virtual environment "
        "and install google-genai in the workspace venv."
    ) from e

from dotenv import load_dotenv
import os
import json
from google.genai.errors import ClientError

load_dotenv()


def get_genai_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to .env or your environment before calling generate_demo."
        )
    return genai.Client(api_key=api_key)


def extract_requirements(transcript: str):
    prompt = f"""
    You are a senior software business analyst.

    Analyze the meeting transcript and extract all software requirements.

    Return ONLY valid JSON.

    Example:

    {{
    "project_title": "Employee Management System",
    "features": [
        "Add Employee",
        "Edit Employee",
        "Delete Employee"
    ],
    "pages": [
        "Dashboard",
        "Employee List",
        "Employee Form"
    ],
    "user_flow": [
        "Admin Login",
        "Manage Employees",
        "View Employee List"
    ]
    }}

    Transcript:

    {transcript}
    """

    text = ""
    client = get_genai_client()
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        text = getattr(response, "text", "")
        text = text.replace("```json", "").replace("```", "").strip()

        return json.loads(text)

    except ClientError as e:
        return {"error": str(e)}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in model response", "raw": text}