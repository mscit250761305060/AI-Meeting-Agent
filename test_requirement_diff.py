from agents.requirement_diff_agent import (
    get_requirement_diff
)

old_requirements = {

    "pages": [
        "dashboard page",
        "employee list page",
        "login page"
    ],

    "features": [
        "Add Employee",
        "Edit Employee"
    ]
}

new_requirements = {

    "pages": [
        "dashboard page",
        "employee list page",
        "login page",
        "reports page",
        "settings page"
    ],

    "features": [
        "Add Employee",
        "Edit Employee",
        "Delete Employee"
    ]
}

diff = get_requirement_diff(
    old_requirements,
    new_requirements
)

print(diff)