import re


def extract_requirements_local(transcript):

    text = transcript.lower()

    requirements = {
        "project_title": "",
        "features": [],
        "pages": [],
        "user_flow": []
    }

    # Project detection

    if "employee management system" in text:
        requirements["project_title"] = (
            "Employee Management System"
        )

    elif "snake game" in text:
        requirements["project_title"] = (
            "Snake Game"
        )

    # Page detection

    page_patterns = [
        "dashboard page",
        "employee list page",
        "employee form page",
        "login page",
        "sign up page",
        "registration page",
        "signup page",
        "registration page",
        "home page",
        "profile page"
    ]

    for page in page_patterns:

        if page in text:

            if page not in requirements["pages"]:
                requirements["pages"].append(page)

    # Features

    if "employee" in text:

        requirements["features"] = [
            "Add Employee",
            "Edit Employee",
            "Delete Employee"
        ]

    requirements["user_flow"] = [
        "Manage Employees"
    ]

    return requirements