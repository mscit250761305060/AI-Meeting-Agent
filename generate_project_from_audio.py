import whisper

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

from agents.ui_generator_agent import (
    generate_ui
)

from agents.page_generator_agent import (
    generate_pages
)




print("Loading Whisper...")

model = whisper.load_model("base")

print("Transcribing Audio...")

result = model.transcribe(
    "audio/test.m4a"
)

transcript = result["text"]

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

generate_ui(
    requirements,
    project["project_path"]
)

generate_pages(
    requirements,
    project["project_path"]
)

print("\nSUCCESS!")
print(project["project_path"])