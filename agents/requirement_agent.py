import json
import logging
from app.services.ai.ollama_service import ollama_service, OllamaServiceException
from config import get_model

logger = logging.getLogger(__name__)


def extract_requirements(transcript: str) -> dict:
    prompt = f"""You are a senior software business analyst.

Analyze the meeting transcript and extract all software requirements into structured JSON.

Return ONLY valid JSON matching this schema:
{{
 "project_name": "Name of the project",
 "project_title": "Name of the project (same as project_name)",
 "industry": "Industry category (e.g. HR, E-commerce, Healthcare, Finance)",
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
- If transcript contains page update instructions, put them in page_updates list as {{"page": "page name", "instruction": "instructions"}}.
- Return ONLY valid JSON.

Transcript:
{transcript}
"""
    model_name = get_model("requirement")
    try:
        raw_text = ollama_service.generate(
            prompt=prompt,
            model=model_name,
            json_mode=True
        )
        # Clean any accidental markdown wrap
        cleaned = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in model response", "raw": raw_text}
    except OllamaServiceException as e:
        return {"error": f"Ollama extraction failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error during extraction: {str(e)}"}