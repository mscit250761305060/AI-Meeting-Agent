from pathlib import Path

from agents.gemini_agent import ask_gemini


def generate_project_structure(
    requirements,
    output_folder
):

    prompt = f"""
You are a Senior Full Stack Developer.

Generate a FastAPI project.

Return ONLY valid JSON.

Format:

{{
    "app.py":"...",
    "models.py":"...",
    "database.py":"...",
    "requirements.txt":"..."
}}

Project:

{requirements}
"""

    response = ask_gemini(prompt)

    return response