import json
import time
import threading
import inspect
from pathlib import Path

from agents.project_planner_agent import plan_project
from agents.code_generator_agent import generate_demo_project
from agents.file_generator_agent import generate_project_files
from agents.crud_generator_agent import generate_crud_app
from agents.page_generator_agent import generate_pages
from agents.requirement_diff_agent import get_requirement_diff
from agents.frontend_generator_agent import generate_frontend
from agents.new_page_generator_agent import generate_new_pages
from agents.page_update_agent import update_existing_pages
from agents.feature_update_agent import update_existing_features
from agents.project_runner_agent import run_project
from agents.error_fix_agent import fix_project_errors
from agents.error_file_writer_agent import overwrite_project_files
from agents.smart_update_agent import get_requirement_changes
from agents.regeneration_router_agent import decide_generators
from agents.file_selector_agent import find_related_files
from agents.file_editor_agent import edit_existing_file
from agents.file_overwriter_agent import overwrite_file

_running_lock = threading.Lock()
_is_running = False


def start_project_regenerator():
    global _is_running
    with _running_lock:
        if _is_running:
            return
        _is_running = True

    # Detect if called from test or main script running in main thread
    caller_frame = inspect.stack()[1]
    caller_filename = caller_frame.filename
    is_test_or_main = "test_" in caller_filename or "project_regenerator_agent" in caller_filename

    if is_test_or_main and threading.current_thread() == threading.main_thread():
        _run_regenerator_loop()
    else:
        t = threading.Thread(target=_run_regenerator_loop, daemon=True)
        t.start()


def _run_regenerator_loop():
    requirements_file = Path("data/requirements.json")
    last_content = ""
    last_requirements = {}

    # Initialize last_requirements from last_requirements.json on startup if it exists
    last_req_file = Path("data/last_requirements.json")
    if last_req_file.exists():
        try:
            last_requirements = json.loads(last_req_file.read_text(encoding="utf-8"))
        except Exception:
            last_requirements = {}

    while True:
        try:
            if requirements_file.exists():
                content = requirements_file.read_text(encoding="utf-8")
                if content.strip() and content != last_content:
                    requirements = json.loads(content)

                    if "error" in requirements:
                        last_content = content
                        continue

                    print("Requirement Changed")
                    print("Running Project Regenerator...")

                    print("Comparing Requirements...")
                    # Load previous requirements from file before get_requirement_changes side-effects it
                    if last_req_file.exists():
                        try:
                            last_requirements = json.loads(last_req_file.read_text(encoding="utf-8"))
                        except Exception:
                            last_requirements = {}
                    else:
                        last_requirements = {}

                    changes = get_requirement_changes(requirements)
                    if not changes:
                        last_content = content
                        continue

                    diff = get_requirement_diff(
                        last_requirements,
                        requirements
                    )

                    plan = plan_project(requirements)
                    project = generate_demo_project(plan)

                    print("Generating Changed Files...")

                    # Selective generation
                    if "pages" in changes and diff.get("new_pages"):
                        generate_new_pages(
                            diff,
                            requirements,
                            project["project_path"]
                        )

                    if "page_updates" in changes:
                        update_existing_pages(
                            requirements,
                            project["project_path"]
                        )
                        update_existing_features(
                            requirements,
                            project["project_path"]
                        )
                        for update in requirements.get("page_updates", []):
                            page = update.get("page")
                            instruction = update.get("instruction")
                            files = find_related_files(
                                project["project_path"],
                                page
                            )
                            if files:
                                updated = edit_existing_file(
                                    files[0],
                                    instruction
                                )
                                if updated:
                                    overwrite_file(
                                        files[0],
                                        updated
                                    )

                    if "features" in changes:
                        from agents.ai_backend_generator_agent import generate_backend
                        generate_backend(
                            requirements,
                            project["project_path"]
                        )

                    if "project_title" in changes or "features" in changes:
                        generate_project_files(
                            requirements,
                            project["project_path"]
                        )

                    if "pages" in changes or "project_title" in changes:
                        generate_frontend(
                            requirements,
                            project["project_path"]
                        )

                    print("Updating Project...")
                    print("Project Updated Successfully")

                    # Run Project / Start Preview Server
                    result = run_project(project["project_path"])
                    if result.get("errors"):
                        # Attempt to fix errors
                        response = fix_project_errors("\n".join(result["errors"]))
                        if response:
                            overwrite_project_files(
                                response,
                                project["project_path"]
                            )
                            result = run_project(project["project_path"])

                    last_content = content
                    last_requirements = requirements

            time.sleep(2)
        except Exception as e:
            print(f"Regenerator Error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    start_project_regenerator()
    # Keep main thread alive if run as script
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass