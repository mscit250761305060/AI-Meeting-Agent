import subprocess
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_demo_project(plan, force_fresh=False):
    """Creates the project directory structure dynamically from the plan."""

    project_name = plan.get("template", "ai_generated_project")
    base_dir = Path(tempfile.gettempdir()) / "ai_meeting_agent_projects"
    output_path = base_dir / project_name

    if output_path.exists() and force_fresh:
        try:
            from runners.project_runner_agent import kill_process_on_port
            kill_process_on_port(8001)
        except Exception as e:
            logger.warning(f"Failed to kill port 8001 before directory clean: {e}")
            
        shutil.rmtree(output_path, ignore_errors=True)
        logger.info(f"Deleted existing project directory for fresh generation: {output_path}")

    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created project directory: {output_path}")
        print(f"New project created: {output_path}")
    else:
        print(f"Existing project found: {output_path}. Reusing.")

    return {
        "status": "success",
        "project_path": str(output_path)
    }