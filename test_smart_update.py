from agents.smart_update_agent import (
    get_requirement_changes
)

requirements = {

    "project_title": "Employee Management System",

    "pages": [

        "dashboard page",

        "reports page",

        "analytics page"

    ],

    "features": [

        "Add Employee"

    ]

}

print(

    get_requirement_changes(
        requirements
    )

)