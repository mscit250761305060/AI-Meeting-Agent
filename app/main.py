from fastapi import FastAPI
from pydantic import BaseModel

from agents.requirement_agent import extract_requirements

from agents.file_generator_agent import generate_project_files
from agents.crud_generator_agent import generate_crud_app

from agents.project_planner_agent import plan_project
from agents.code_generator_agent import generate_demo_project

from agents.frontend_generator_agent import generate_frontend
from agents.ui_generator_agent import generate_ui

from agents.page_generator_agent import generate_pages

app = FastAPI()


class MeetingRequest(BaseModel):
    transcript: str


@app.get("/")
def home():
    return {
        "message": "AI Meeting Agent Running"
    }


@app.post("/generate-demo")
def generate_demo(data: MeetingRequest):

    requirements = extract_requirements(
        data.transcript
    )

    plan = plan_project(
        requirements
    )

    result = generate_demo_project(
    plan
)

    generate_project_files(
        requirements,
        result["project_path"]
    )

    generate_crud_app(
        requirements,
        result["project_path"]
    )

    generate_frontend(
        requirements,
        result["project_path"]
    )

    generate_ui(
        requirements,
        result["project_path"]
    )

    generate_pages(
        requirements,
        result["project_path"]
    )

    return {
    "requirements": requirements,
    "plan": plan,
    "result": result,
    "message": "Demo Project Generated Successfully"
    }