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

    Required JSON format:
    {{
     "project_name": "Name of the project",
     "project_title": "Name of the project (same as project_name)",
     "industry": "Industry category (e.g. HR, E-commerce, Finance)",
     "features": ["list of features"],
     "pages": ["list of pages"],
     "frontend": "HTML/CSS/JS",
     "backend": "FastAPI",
     "database": "SQLite",
     "user_roles": ["list of user roles"],
     "page_updates": []
    }}

    Rules:
    - Keep exact page names.
    - If transcript contains page update instructions (e.g. "add search bar to employee list"), put them in page_updates list as {{"page": "employee list", "instruction": "Add Search Bar"}}.
    - Return ONLY valid JSON.

    Transcript:
    {transcript}
    """

    text = ""
    client = get_genai_client()
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = getattr(response, "text", "")
        text = text.replace("```json", "").replace("```", "").strip()

        return json.loads(text)

    except ClientError as e:
        return {"error": str(e)}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in model response", "raw": text}