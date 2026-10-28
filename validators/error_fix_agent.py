from utilities.llm_utils import generate_content_with_retry
from utilities.json_response_cleaner_agent import clean_json_response
import json
from config import get_model


import os
from pathlib import Path

def fix_project_errors(errors, requirements=None, project_path=None):

    if not errors:
        print("No errors found.")
        return None

    project_context = ""
    if requirements:
        import json as _json
        project_context = f"\nProject Name: {requirements.get('project_name', 'AI Generated Project')}\nProject Features: {', '.join(requirements.get('features', []))}\n"

    # --- Read Code Context ---
    code_context = ""
    if project_path:
        base_dir = Path(project_path)
        files_to_read = []
        # --- Dynamic Backend Files ---
        backend_dir = base_dir / "backend"
        if backend_dir.exists():
            for py_file in backend_dir.rglob("*.py"):
                if "venv" not in py_file.parts and ".pytest_cache" not in py_file.parts and "__pycache__" not in py_file.parts:
                    files_to_read.append(py_file)
        
        frontend_src_dir = base_dir / "frontend" / "src"
        if frontend_src_dir.exists():
            files_to_read.append(frontend_src_dir / "App.tsx")
            files_to_read.append(frontend_src_dir / "api.ts")
            files_to_read.append(frontend_src_dir / "main.tsx")
            
            for tsx_file in frontend_src_dir.rglob("*.tsx"):
                if tsx_file not in files_to_read:
                    files_to_read.append(tsx_file)

        for filepath in files_to_read:
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8")
                    rel_path = filepath.relative_to(base_dir).as_posix()
                    code_context += f"--- {rel_path} ---\n```\n{content}\n```\n\n"
                except Exception:
                    pass

    prompt = f"""
You are an Elite Full-Stack Debugging Expert.

The generated project has these runtime errors (E2E or API Validation):

{errors}
{project_context}

Here is the CURRENT SOURCE CODE for the project:
{code_context}

Project Structure Notes:
- Backend files are in `backend/` and frontend files are in `frontend/src/`.
- The frontend is a React + Vite + Tailwind CSS application using TSX.
- If the error is an API mismatch (e.g. 500 or UI says "Cannot read properties"), analyze BOTH the FastAPI schemas and the Frontend React (TSX) logic to see where the mismatch is.
- Make sure that the frontend exactly uses the keys returned by the backend schema.
- ALL Python imports MUST be ABSOLUTE relative to the backend directory (e.g. `from core.database import Base`, `import models`). NEVER prefix imports with 'backend.'.
- The SQLite database URL must be `sqlite:///./project.db`.
- Use `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")`.

Return ONLY the corrected files as a JSON object where keys are filenames (e.g., "backend/app.py" or "frontend/src/pages/LoginPage.tsx") and values are the complete corrected file content.

Example:
{{
    "backend/app.py": "... corrected app.py content ...",
    "frontend/src/pages/LoginPage.tsx": "... corrected LoginPage.tsx content ..."
}}

Only return JSON. No explanations. No markdown. Only return the files that actually need fixing!
"""

    print("Sending Errors to Gemini...")

    from types import SimpleNamespace
    response = generate_content_with_retry(
        model_name=get_model("error_fix"),
        contents=prompt,
        config=SimpleNamespace(
            response_mime_type="application/json",
            temperature=0.1
        ),
        max_retries=3,
        base_delay=2.0
    )

    return response.text