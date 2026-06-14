def plan_project(requirements):

    title = requirements.get("project_title", "").lower()

    if "employee" in title:
        return {
            "project_type": "crud_app",
            "template": "employee_management"
        }

    if "dashboard" in title:
        return {
            "project_type": "dashboard",
            "template": "admin_dashboard"
        }

    return {
        "project_type": "landing_page",
        "template": "basic_landing"
    }