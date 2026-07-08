import re


def extract_requirements_local(transcript):

    text = transcript.lower()

    requirements = {
        "project_title": "",
        "features": [],
        "pages": [],
        "user_flow": [],
        "page_updates": []
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

    valid_pages = [
        "dashboard page",
        "employee list page",
        "employee form page",
        "login page",
        "reports page",
        "settings page",
        "analytics page",
        "profile page",
        "about page",
        "contact page"
    ]

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        # Ignore update instructions
        if (
            "please" in line
            or "add" in line
            or "search" in line
            or "salary" in line
            or "export" in line
        ):
            continue

        if line in valid_pages:

            if line not in requirements["pages"]:
                requirements["pages"].append(line)

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

    # Page Updates

    if (
        "search" in text
        and "employee list" in text
    ):

        requirements["page_updates"].append({

            "page": "employee list page",

            "instruction": "Add Search Bar"

        })

    if (
        "salary" in text
        and "employee form" in text
    ):

        requirements["page_updates"].append({

            "page": "employee form page",

            "instruction": "Add Salary Field"

        })

    if (
        "export" in text
        and "employee list" in text
    ):

        requirements["page_updates"].append({

            "page": "employee list page",

            "instruction": "Add Export Button"

        })

    return requirements