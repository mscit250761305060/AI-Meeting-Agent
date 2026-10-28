import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from utilities.llm_utils import generate_content_with_retry
from utilities.json_response_cleaner_agent import clean_json_response
from config import get_model

def generate_devops_files(requirements, project_path):
    project_path = Path(project_path)
    
    project_name = requirements.get("project_name", "ai-generated-project").lower().replace(" ", "-")
    
    prompt = f"""
    You are an elite DevOps Engineer. We have built a FastAPI + React/Vite web application called '{project_name}'.
    
    I need you to generate the following production-ready DevOps files:
    1. A `Dockerfile` (based on python:3.11-slim) that installs backend requirements, exposes port 8000, and runs uvicorn. 
    2. A `docker-compose.yml` that builds the Dockerfile AND includes a `db` service using the `mysql:8.0` image (with MYSQL_ROOT_PASSWORD, MYSQL_DATABASE, etc.).
    3. A `requirements.txt` containing at least: fastapi, uvicorn, sqlalchemy, pydantic, passlib, bcrypt==3.2.2, python-jose, PyJWT, pymysql.
    4. A `.env` file with a strong random JWT_SECRET_KEY and DATABASE_URL (mysql+pymysql://root:root@db:3306/demo).
    5. A `.gitignore` file for Python/FastAPI and React/Node.js projects. **CRITICAL: You MUST include `node_modules/` and `frontend/node_modules/` in the gitignore.**
    6. A `.github/workflows/deploy.yml` file that defines a CI/CD pipeline. It should checkout code, setup python, run `pytest`, build the frontend with node, and build the docker container.
    
    Return a STRICT JSON object where keys are the exact filenames and values are the raw text contents.
    {{
        "Dockerfile": "code...",
        "docker-compose.yml": "code...",
        "backend/requirements.txt": "code...",
        ".env": "code...",
        ".gitignore": "code...",
        ".github/workflows/deploy.yml": "code..."
    }}
    """
    
    response = generate_content_with_retry(
        model_name=get_model("backend"), # reuse backend model config
        contents=prompt,
        config=SimpleNamespace(response_mime_type="application/json", temperature=0.1)
    )
    
    try:
        files = json.loads(clean_json_response(response.text))
        for filename, content in files.items():
            file_path = project_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            print(f"Generated DevOps file: {filename}")
            
    except Exception as e:
        print(f"Error generating DevOps files: {e}")
        return False
        
    # --- GIT INITIALIZATION ---
    try:
        print("Initializing Git Repository...")
        # git init
        subprocess.run(["git", "init"], cwd=str(project_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # git config (in case global isn't set, to prevent commit errors)
        subprocess.run(["git", "config", "user.name", "AI Meeting Agent"], cwd=str(project_path), check=False)
        subprocess.run(["git", "config", "user.email", "agent@ai.local"], cwd=str(project_path), check=False)
        # git add .
        subprocess.run(["git", "add", "."], cwd=str(project_path), check=True)
        # git commit
        subprocess.run(["git", "commit", "-m", "🎉 Initial Production-Ready Commit by AI Meeting Agent"], cwd=str(project_path), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Git Initialization Complete.")
    except Exception as e:
        print(f"Git initialization skipped/failed: {e}")
        
    return True
