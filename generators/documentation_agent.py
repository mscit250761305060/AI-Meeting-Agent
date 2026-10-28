"""
documentation_agent.py

Generates a comprehensive README.md for every generated project including:
- Project overview
- Folder structure
- Setup instructions
- API endpoint table
- Demo login credentials
- Feature list
"""

import logging
from pathlib import Path
from utilities.llm_utils import generate_content_with_retry
from config import get_model

logger = logging.getLogger(__name__)


def generate_documentation(requirements: dict, project_path: str) -> dict:
    """Generates README.md in the project root with full project documentation."""
    project_path = Path(project_path)
    project_name = requirements.get("project_name") or requirements.get("project_title", "AI Generated Project")
    features = requirements.get("features", [])
    pages = requirements.get("pages", [])
    user_roles = requirements.get("user_roles", ["Admin", "User"])
    industry = requirements.get("industry", "General")

    prompt = f"""
Generate a comprehensive, professional README.md for the project '{project_name}'.

Project Details:
- Industry: {industry}
- Features: {', '.join(features)}
- Pages: {', '.join(pages)}
- User Roles: {', '.join(user_roles)}
- Backend: FastAPI + SQLite + SQLAlchemy
- Frontend: HTML + CSS + JavaScript (dark mode, glassmorphic UI)

The README must include ALL of the following sections in this exact order:

1. # {project_name}
   Brief 2-3 sentence description of what this project does.

2. ## Project Structure
   Show the folder structure:
   ```
   project_root/
   ├── backend/
   │   ├── app.py         # FastAPI main application
   │   ├── database.py    # SQLAlchemy engine & session
   │   ├── models.py      # Database table models
   │   ├── schemas.py     # Pydantic validation schemas
   │   ├── crud.py        # Database helpers & seed data
   │   └── project.db     # SQLite database (auto-created)
   ├── frontend/
   │   ├── index.html     # Entry point
   │   └── [page files].html/.css/.js
   ├── project_config.json
   └── README.md
   ```

3. ## Quick Start
   ```bash
   # Install dependencies
   pip install fastapi uvicorn sqlalchemy pydantic

   # Run the backend server
   cd backend
   uvicorn app:app --port 8001 --reload

   # Open in browser
   # http://127.0.0.1:8001
   ```

4. ## Demo Credentials
   Table with username, password, role for each user role. Default password is "password123" for all.

5. ## API Endpoints
   A markdown table with columns: Method | Endpoint | Description | Auth Required
   Include ALL standard endpoints: /api/auth/login, /api/dashboard-stats, and CRUD for each major entity.

6. ## Features
   A bulleted list of all {len(features)} features.

7. ## Pages
   A bulleted list of all {len(pages)} pages with a one-line description of each.

8. ## Tech Stack
   | Component | Technology |
   |---|---|
   | Backend | FastAPI |
   | Database | SQLite via SQLAlchemy |
   | Frontend | HTML5 + CSS3 + Vanilla JavaScript |
   | UI Design | Dark Mode, Glassmorphism |

Return ONLY the raw markdown text of the README. No JSON, no code blocks wrapping the entire output.
"""

    try:
        response = generate_content_with_retry(
            model_name=get_model("documentation"),
            contents=prompt,
            max_retries=3,
            base_delay=2.0
        )
        readme_content = response.text

        # Write to project root
        readme_path = project_path / "README.md"
        readme_path.write_text(readme_content, encoding="utf-8")
        print(f"Documentation: README.md generated ({len(readme_content)} chars)")
        return {"README.md": readme_content}

    except Exception as e:
        logger.error(f"Failed to generate documentation: {e}")
        # Write a minimal fallback README
        fallback = f"""# {project_name}

Auto-generated full-stack web application.

## Quick Start
```bash
cd backend
uvicorn app:app --port 8001
```
Open http://127.0.0.1:8001

## Features
{chr(10).join(f'- {f}' for f in features)}

## Pages
{chr(10).join(f'- {p}' for p in pages)}
"""
        (project_path / "README.md").write_text(fallback, encoding="utf-8")
        return {"README.md": fallback}
