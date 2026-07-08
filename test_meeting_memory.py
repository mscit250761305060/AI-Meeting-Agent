from agents.meeting_memory_agent import (

    add_to_memory,

    get_memory,

    clear_memory

)

clear_memory()

add_to_memory(
    "Create Employee Management System"
)

add_to_memory(
    "Add Dashboard"
)

add_to_memory(
    "Add Search Bar"
)

print(

    get_memory()

)