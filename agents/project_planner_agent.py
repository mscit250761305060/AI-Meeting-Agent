def plan_project(requirements):

    title = requirements.get(
        "project_title",
        ""
    ).lower()

    return {
        "project_type": "crud_app",
        "template": "employee_management"
    }