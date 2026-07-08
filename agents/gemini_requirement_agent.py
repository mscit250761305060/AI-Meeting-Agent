import json

from agents.gemini_agent import ask_gemini


def extract_requirements_ai(transcript):

    prompt = f"""
You are a Senior Software Business Analyst.

Read the meeting transcript.

Return ONLY valid JSON.

Format:
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

Meeting Transcript:

{transcript}
"""

    response = ask_gemini(prompt)

    # Gemini ઘણી વખત ```json ... ``` માં જવાબ આપે છે
    response = (
        response
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    return json.loads(response)