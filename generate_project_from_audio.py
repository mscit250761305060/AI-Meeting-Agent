from faster_whisper import WhisperModel

from agents.requirement_agent import (
    extract_requirements
)

from agents.project_planner_agent import (
    plan_project
)

from agents.code_generator_agent import (
    generate_demo_project
)

from agents.file_generator_agent import (
    generate_project_files
)

from agents.crud_generator_agent import (
    generate_crud_app
)

from agents.frontend_generator_agent import (
    generate_frontend
)

from agents.page_generator_agent import (
    generate_pages
)

print("Loading Whisper...")

model = WhisperModel("base", device="cpu", compute_type="int8")

print("Transcribing Audio...")

segments, info = model.transcribe(
    "audio/test.m4a",
    beam_size=1
)

transcript = " ".join(s.text for s in segments)

print("\nTRANSCRIPT:")
print(transcript)

print("\nExtracting Requirements...")

requirements = extract_requirements(
    transcript
)

print(requirements)

print("\nPlanning Project...")

plan = plan_project(
    requirements
)

print(plan)

print("\nGenerating Project...")

project = generate_demo_project(
    plan
)

generate_project_files(
    requirements,
    project["project_path"]
)

generate_crud_app(
    requirements,
    project["project_path"]
)

generate_frontend(
    requirements,
    project["project_path"]
)

generate_pages(
    requirements,
    project["project_path"]
)

print("\nRunning project server...")
from agents.project_runner_agent import run_project
runner_result = run_project(project["project_path"])

features_list = requirements.get("features", [])
pages_list = requirements.get("pages", [])
proj_name = requirements.get("project_name") or requirements.get("project_title") or "AI Generated Project"
running_url = "http://127.0.0.1:8001"

print("\nProject Generated Successfully\n")
print(f"Project Name: {proj_name}")
print(f"Features Created: {', '.join(features_list)}")
print(f"Pages Created: {', '.join(pages_list)}")
print(f"Backend Status: {'Running' if runner_result.get('success') else 'Failed'}")
print(f"Frontend Status: {'Running' if runner_result.get('success') else 'Failed'}")
print(f"Running URL: {running_url}")