import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from app.services.ws_manager import manager
from app.services.generator.specification import ProjectSpecification
from app.services.generator.requirement_parser import parse_requirements
from app.services.generator.project_synthesizer import ProjectSynthesizer
from app.services.generator.project_validator import ProjectValidator
from agents.project_runner_agent import run_project

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TRANSCRIPT_FILE = DATA_DIR / "live_transcript.txt"
REQUIREMENTS_FILE = DATA_DIR / "requirements.json"

LAST_PROJECT_PATH: Optional[str] = None


class ProjectGenerationService:
    @staticmethod
    def get_last_project_path() -> Optional[str]:
        global LAST_PROJECT_PATH
        return LAST_PROJECT_PATH

    @staticmethod
    def set_last_project_path(path: str):
        global LAST_PROJECT_PATH
        LAST_PROJECT_PATH = path

    @classmethod
    def generate_demo_from_transcript(cls, transcript: str, session_id: Optional[str] = None, user_id: Optional[str] = None) -> dict:
        """
        Provider-independent generation from meeting transcript text.
        Converts transcript into validated specification, synthesizes full project structure,
        validates files and syntax, and launches preview server.
        """
        global LAST_PROJECT_PATH
        manager.broadcast_sync({"action": "log", "message": "Analyzing meeting transcript (rule-based parser)..."})

        # 1. Save raw transcript
        TRANSCRIPT_FILE.write_text(transcript, encoding="utf-8")

        # 2. Parse into ProjectSpecification without AI dependencies
        try:
            spec = parse_requirements(transcript)
        except Exception as e:
            logger.exception("Requirement parsing error: %s", e)
            return {"success": False, "message": f"Requirement extraction failed: {str(e)}"}

        return cls._execute_synthesis_pipeline(spec, session_id=session_id, user_id=user_id)

    @classmethod
    def generate_from_specification(cls, input_spec: Union[dict, ProjectSpecification], session_id: Optional[str] = None, user_id: Optional[str] = None) -> dict:
        """
        Generates project directly from structured requirement payload.
        """
        try:
            if isinstance(input_spec, dict):
                spec = parse_requirements(input_spec)
            elif isinstance(input_spec, ProjectSpecification):
                spec = input_spec
            else:
                return {"success": False, "message": "Invalid specification input format."}
        except Exception as e:
            return {"success": False, "message": f"Failed to validate specification: {str(e)}"}

        return cls._execute_synthesis_pipeline(spec, session_id=session_id, user_id=user_id)

    @classmethod
    def _execute_synthesis_pipeline(cls, spec: ProjectSpecification, session_id: Optional[str] = None, user_id: Optional[str] = None) -> dict:
        global LAST_PROJECT_PATH
        import uuid
        from app.services import meeting_state

        active_session_id = session_id or meeting_state.current_session_id or f"session_{uuid.uuid4().hex[:12]}"
        effective_user_id = user_id or meeting_state.current_user_id

        # Save structured requirements to data/requirements.json
        req_dict = spec.model_dump()
        REQUIREMENTS_FILE.write_text(json.dumps(req_dict, indent=4), encoding="utf-8")

        manager.broadcast_sync({
            "action": "log",
            "message": f"Synthesizing '{spec.project_name}' ({spec.entity_name} model, {len(spec.pages)} pages)..."
        })

        # 3. Synthesize dynamic project files
        synthesizer = ProjectSynthesizer()
        project_dir, synth_info = synthesizer.synthesize(spec)
        LAST_PROJECT_PATH = str(project_dir)

        for filename in synth_info["files_created"]:
            manager.broadcast_sync({
                "action": "create_file",
                "path": filename,
                "content": f"Generated {filename} for {spec.project_name}"
            })

        manager.broadcast_sync({"action": "log", "message": "Validating generated project structure and Python syntax..."})

        # 4. Validate generated project before marking success
        val_result = ProjectValidator.validate_project(project_dir, spec)
        if not val_result["valid"]:
            error_msg = "; ".join(val_result["errors"])
            manager.broadcast_sync({"action": "log", "message": f"❌ Project validation failed: {error_msg}"})
            return {
                "success": False,
                "message": f"Project validation failed: {error_msg}",
                "errors": val_result["errors"],
                "project_path": str(project_dir)
            }

        # 5. Launch preview server on port 8001
        manager.broadcast_sync({"action": "log", "message": f"Launching preview server for {spec.project_name} on port 8001..."})
        runner_result = run_project(project_dir)

        features_list = spec.features
        pages_list = [p.title for p in spec.pages]
        proj_name = spec.project_name
        running_url = "http://127.0.0.1:8001"

        # 6. Database record persistence for GeneratedProject and SessionRequirement
        project_id = str(uuid.uuid4())
        try:
            from app.database.database import SessionLocal
            from app.models.models import GeneratedProject, SessionRequirement, SessionRecord
            if SessionLocal:
                with SessionLocal() as db:
                    if active_session_id:
                        # Ensure session record exists and has ownership set
                        sess = db.query(SessionRecord).filter(SessionRecord.session_id == active_session_id).first()
                        if not sess:
                            sess = SessionRecord(session_id=active_session_id, user_id=effective_user_id, status="active")
                            db.add(sess)
                            db.flush()
                        elif effective_user_id and not sess.user_id:
                            sess.user_id = effective_user_id

                        # Upsert SessionRequirement
                        req_rec = db.query(SessionRequirement).filter(SessionRequirement.session_id == active_session_id).first()
                        if not req_rec:
                            req_rec = SessionRequirement(session_id=active_session_id, data=req_dict)
                            db.add(req_rec)
                        else:
                            req_rec.data = req_dict

                        # Upsert GeneratedProject
                        existing_proj = db.query(GeneratedProject).filter(GeneratedProject.session_id == active_session_id).first()
                        if not existing_proj:
                            proj_rec = GeneratedProject(
                                id=project_id,
                                session_id=active_session_id,
                                project_name=proj_name,
                                project_path=str(project_dir),
                                file_tree=synth_info.get("files_created", [])
                            )
                            db.add(proj_rec)
                        else:
                            existing_proj.project_name = proj_name
                            existing_proj.project_path = str(project_dir)
                            existing_proj.file_tree = synth_info.get("files_created", [])
                            project_id = existing_proj.id
                        db.commit()
                        meeting_state.current_project_id = project_id
        except Exception as e:
            logger.warning(f"Could not persist project generation to database: {e}")

        formatted_msg = f"""Project Generated Successfully

Project Name: {proj_name}
Entity: {spec.entity_name} ({spec.entity_plural})
Features Created: {", ".join(features_list)}
Pages Created: {", ".join(pages_list)}
Backend Status: {"Running" if runner_result.get("success") else "Failed"}
Running URL: {running_url}
Files Checked: {len(val_result["files_checked"])} files verified
Directory: {project_dir.name}"""

        if spec.unsupported_requirements:
            formatted_msg += f"\nUnsupported Requirements Note: {'; '.join(spec.unsupported_requirements)}"

        manager.broadcast_sync({
            "action": "project_ready",
            "url": running_url,
            "project_name": proj_name,
            "project_id": project_id
        })
        manager.broadcast_sync({"action": "log", "message": f"✅ {proj_name} ready at {running_url}"})

        return {
            "success": runner_result.get("success", False),
            "message": formatted_msg,
            "running_url": running_url,
            "requirements": req_dict,
            "details": {
                "project_id": project_id,
                "session_id": active_session_id,
                "project_name": proj_name,
                "project_path": str(project_dir),
                "entity": spec.entity_name,
                "features": features_list,
                "pages": pages_list,
                "backend_status": "Running" if runner_result.get("success") else "Failed",
                "running_url": running_url,
                "unsupported": spec.unsupported_requirements,
                "validation": val_result
            }
        }
