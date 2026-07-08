from agents.regeneration_router_agent import (
    decide_generators
)

changes = {

    "pages":[

        "reports page"

    ],

    "features":[

        "Delete Employee"

    ]

}
print(

    decide_generators(
        changes
    )

)