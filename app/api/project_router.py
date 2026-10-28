import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.models.schemas import TranscriptRequest, ProjectGenerationResponse
from app.services.project_service import ProjectGenerationService
from meeting_engine.whisper_worker import transcribe_audio
from app.models.models import User, SessionRecord, GeneratedProject, SessionRequirement
from app.services.auth_service import get_optional_user
from app.database.database import get_db, SessionLocal
from sqlalchemy.orm import Session

router = APIRouter(tags=["project"])

@router.post("/generate-demo", response_model=ProjectGenerationResponse)
def generate_demo(req: TranscriptRequest, current_user: Optional[User] = Depends(get_optional_user)):
    """
    Directly synthesizes a project from raw text transcript.
    """
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")
    
    user_id = current_user.id if current_user else None
    result = ProjectGenerationService.generate_demo_from_transcript(req.transcript, user_id=user_id)
    return result

@router.post("/upload-audio", response_model=ProjectGenerationResponse)
def upload_audio(file: UploadFile = File(...), current_user: Optional[User] = Depends(get_optional_user)):
    """
    Uploads an audio recording, transcribes it via Faster-Whisper, and generates the demo project.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        transcript = transcribe_audio(tmp_path)
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=400, detail="Could not transcribe audio or audio was silent.")

    user_id = current_user.id if current_user else None
    result = ProjectGenerationService.generate_demo_from_transcript(transcript, user_id=user_id)
    return result

@router.post("/generate-project", response_model=ProjectGenerationResponse)
def generate_project(payload: dict, current_user: Optional[User] = Depends(get_optional_user)):
    """
    Synthesizes a project directly from structured specification payload.
    Supports project_name, purpose, industry, entity_name, entity_plural, fields, pages, features, user_roles.
    """
    user_id = current_user.id if current_user else None
    result = ProjectGenerationService.generate_from_specification(payload, user_id=user_id)
    return result


# =====================================================================
# Project Listing, Details, File Hierarchy, and Secure ZIP Download APIs
# =====================================================================

import io
import os
import re
import zipfile
from fastapi.responses import Response

GENERATED_BASE_DIR = Path("generated_projects").resolve()

EXCLUDED_NAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    ".git", ".gitignore",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".venv", "venv", "env",
    "node_modules",
    ".DS_Store", "Thumbs.db"
}
EXCLUDED_EXTS = {".pyc", ".pyo", ".pyd"}


def _resolve_project(project_id: str, db: Optional[Session] = None, current_user: Optional[User] = None):
    """
    Locates a project by database record ID, session ID, or folder name.
    Strictly prevents path traversal attacks and enforces user ownership isolation.
    """
    # Reject directory traversal sequences
    if ".." in project_id or "/" in project_id or "\\" in project_id:
        raise HTTPException(status_code=400, detail="Invalid project identifier.")

    db_proj = None
    requirements_data = None

    def _query(db_sess):
        nonlocal db_proj, requirements_data
        db_proj = db_sess.query(GeneratedProject).filter(
            (GeneratedProject.id == project_id) |
            (GeneratedProject.session_id == project_id) |
            (GeneratedProject.project_name == project_id)
        ).first()

        if db_proj:
            # Enforce ownership check if session belongs to a user
            if db_proj.session_id:
                session_rec = db_sess.query(SessionRecord).filter(SessionRecord.session_id == db_proj.session_id).first()
                if session_rec and session_rec.user_id:
                    if not current_user or session_rec.user_id != current_user.id:
                        raise HTTPException(status_code=403, detail="Access denied: this project belongs to another user.")

            req = db_sess.query(SessionRequirement).filter(SessionRequirement.session_id == db_proj.session_id).first()
            if req:
                requirements_data = req.data
        else:
            # If not matched directly, check if the identifier or path is owned by another user in DB
            other_match = db_sess.query(GeneratedProject).join(
                SessionRecord, GeneratedProject.session_id == SessionRecord.session_id
            ).filter(
                (GeneratedProject.project_path.like(f"%{project_id}%")) |
                (GeneratedProject.project_name == project_id.replace("_", " ").title())
            ).filter(SessionRecord.user_id.isnot(None)).first()
            if other_match:
                sess = db_sess.query(SessionRecord).filter(SessionRecord.session_id == other_match.session_id).first()
                if sess and sess.user_id and (not current_user or sess.user_id != current_user.id):
                    raise HTTPException(status_code=403, detail="Access denied: this project belongs to another user.")

    try:
        if db is not None:
            _query(db)
        elif SessionLocal:
            with SessionLocal() as db_sess:
                _query(db_sess)
    except HTTPException:
        raise
    except Exception:
        pass

    # Resolve target path
    if db_proj and db_proj.project_path:
        target_path = Path(db_proj.project_path).resolve()
    else:
        target_path = (GENERATED_BASE_DIR / project_id).resolve()

    # Path traversal verification
    try:
        target_path.relative_to(GENERATED_BASE_DIR)
    except ValueError:
        if not (db_proj and Path(db_proj.project_path).resolve() == target_path):
            raise HTTPException(status_code=403, detail="Access denied: path outside generated projects directory.")

    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found on disk.")

    proj_name = db_proj.project_name if db_proj else target_path.name.replace("_", " ").title()
    session_id = db_proj.session_id if db_proj else None
    created_at = str(db_proj.created_at) if (db_proj and db_proj.created_at) else None

    return {
        "db_proj": db_proj,
        "project_id": db_proj.id if db_proj else target_path.name,
        "project_name": proj_name,
        "session_id": session_id,
        "project_path": str(target_path),
        "target_path": target_path,
        "created_at": created_at,
        "requirements": requirements_data,
        "file_tree": db_proj.file_tree if db_proj else None
    }


@router.get("/projects")
def list_projects(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Lists generated projects. Isolated per authenticated user.
    Strictly excludes projects belonging to other users.
    """
    projects_list = []
    seen_paths = set()
    other_users_projects = set()

    # 1. Projects from database
    try:
        # Track other users' projects to prevent leaking during supplementary disk scan
        other_q = db.query(GeneratedProject.project_path, GeneratedProject.project_name).join(
            SessionRecord, GeneratedProject.session_id == SessionRecord.session_id
        ).filter(SessionRecord.user_id.isnot(None))
        if current_user:
            other_q = other_q.filter(SessionRecord.user_id != current_user.id)
        for p_row in other_q.all():
            if p_row[0]:
                other_users_projects.add(str(Path(p_row[0]).resolve()))
            if p_row[1]:
                other_users_projects.add(p_row[1].lower())

        query = db.query(GeneratedProject).outerjoin(SessionRecord, GeneratedProject.session_id == SessionRecord.session_id)
        if current_user:
            query = query.filter((SessionRecord.user_id == current_user.id) | (SessionRecord.user_id.is_(None)))
        else:
            query = query.filter(SessionRecord.user_id.is_(None))

        records = query.order_by(GeneratedProject.created_at.desc()).all()
        for rec in records:
            p_path = Path(rec.project_path).resolve()
            if p_path in seen_paths:
                continue
            seen_paths.add(p_path)
            file_count = 0
            if p_path.exists() and p_path.is_dir():
                for root, dirs, files in os.walk(p_path):
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES and not d.startswith(".")]
                    file_count += sum(1 for f in files if f not in EXCLUDED_NAMES and not any(f.endswith(e) for e in EXCLUDED_EXTS))

            projects_list.append({
                "id": rec.id,
                "project_name": rec.project_name,
                "session_id": rec.session_id,
                "project_path": str(p_path.relative_to(Path.cwd())) if str(p_path).startswith(str(Path.cwd())) else str(p_path),
                "created_at": str(rec.created_at) if rec.created_at else None,
                "file_count": file_count,
                "status": "ready"
            })
    except Exception:
        pass

    # 2. Supplementary check for unassigned folders on disk (never leak another user's project)
    if GENERATED_BASE_DIR.exists():
        for item in GENERATED_BASE_DIR.iterdir():
            if item.is_dir() and item.resolve() not in seen_paths and item.name not in EXCLUDED_NAMES:
                if str(item.resolve()) in other_users_projects or item.name.lower() in other_users_projects:
                    continue
                file_count = sum(1 for root, dirs, files in os.walk(item) for f in files if f not in EXCLUDED_NAMES and not any(f.endswith(e) for e in EXCLUDED_EXTS))
                projects_list.append({
                    "id": item.name,
                    "project_name": item.name.replace("_", " ").title(),
                    "session_id": None,
                    "project_path": str(item.relative_to(Path.cwd())) if str(item).startswith(str(Path.cwd())) else str(item),
                    "created_at": None,
                    "file_count": file_count,
                    "status": "ready"
                })

    return {"success": True, "total": len(projects_list), "projects": projects_list}


def _is_preview_running(port: int = 8001) -> bool:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.15)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


@router.get("/projects/{project_id}")
def get_project_details(
    project_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Returns detailed information, requirements, and generation status for a project.
    """
    info = _resolve_project(project_id, db=db, current_user=current_user)
    target_path = info["target_path"]

    files_list = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES and not d.startswith(".")]
        for f in files:
            if f not in EXCLUDED_NAMES and not any(f.endswith(e) for e in EXCLUDED_EXTS):
                rel = str((Path(root) / f).relative_to(target_path)).replace("\\", "/")
                files_list.append(rel)

    is_running = _is_preview_running(8001)

    return {
        "success": True,
        "id": info["project_id"],
        "project_name": info["project_name"],
        "session_id": info["session_id"],
        "project_path": info["project_path"],
        "created_at": info["created_at"],
        "status": "ready",
        "file_count": len(files_list),
        "files": files_list,
        "requirements": info["requirements"],
        "preview_active": is_running,
        "running_url": "http://127.0.0.1:8001" if is_running else None
    }


@router.post("/projects/{project_id}/run")
def run_project_preview(
    project_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Launches or switches the preview server to the selected project on port 8001.
    """
    info = _resolve_project(project_id, db=db, current_user=current_user)
    target_path = info["target_path"]
    from agents.project_runner_agent import run_project
    res = run_project(target_path)
    return {
        "success": res.get("success", False),
        "running_url": "http://127.0.0.1:8001" if res.get("success") else None,
        "message": res.get("stdout") or (res.get("errors")[0] if res.get("errors") else "Preview launch failed.")
    }


@router.get("/projects/{project_id}/files")
def list_project_files(
    project_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Lists a project's files and folders hierarchy securely, excluding secrets,
    caches, virtualenvs, and sensitive items.
    """
    info = _resolve_project(project_id, db=db, current_user=current_user)
    target_path = info["target_path"]

    entries = []
    for root, dirs, files in os.walk(target_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES and not d.startswith(".")]
        for d in dirs:
            dir_path = Path(root) / d
            rel = str(dir_path.relative_to(target_path)).replace("\\", "/")
            entries.append({
                "name": d,
                "path": rel,
                "type": "directory"
            })
        for f in files:
            if f in EXCLUDED_NAMES or any(f.endswith(e) for e in EXCLUDED_EXTS) or f.startswith(".env"):
                continue
            file_path = Path(root) / f
            rel = str(file_path.relative_to(target_path)).replace("\\", "/")
            entries.append({
                "name": f,
                "path": rel,
                "type": "file",
                "size_bytes": file_path.stat().st_size
            })

    entries.sort(key=lambda x: (x["type"] != "directory", x["path"]))

    return {
        "success": True,
        "project_id": info["project_id"],
        "project_name": info["project_name"],
        "total_items": len(entries),
        "files": entries
    }


@router.get("/projects/{project_id}/download")
def download_project_zip(
    project_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Creates an in-memory ZIP archive of the project and streams it for download.
    Strictly excludes sensitive files (.env, virtualenvs, git, pycache).
    Does NOT modify or delete the original project on disk.
    """
    info = _resolve_project(project_id, db=db, current_user=current_user)
    target_path = info["target_path"]

    try:
        zip_buffer = io.BytesIO()
        file_count = 0
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(target_path):
                # Exclude sensitive/unnecessary directories
                dirs[:] = [d for d in dirs if d not in EXCLUDED_NAMES and not d.startswith(".")]
                for f in files:
                    # Exclude sensitive/unnecessary files
                    if f in EXCLUDED_NAMES or any(f.endswith(e) for e in EXCLUDED_EXTS) or f.startswith(".env"):
                        continue
                    full_file = Path(root) / f
                    arcname = str(full_file.relative_to(target_path)).replace("\\", "/")
                    zf.write(full_file, arcname=arcname)
                    file_count += 1

        if file_count == 0:
            raise HTTPException(status_code=500, detail="Cannot create ZIP: Project directory has no downloadable files.")

        zip_buffer.seek(0)
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', info["project_name"] or project_id)

        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}.zip"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate ZIP archive: {str(e)}")

