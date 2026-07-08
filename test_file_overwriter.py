from agents.file_editor_agent import (
    edit_existing_file
)

from agents.file_overwriter_agent import (
    overwrite_file
)

FILE = (
    "generated_projects/employee_management_demo/login_page.html"
)

updated = edit_existing_file(

    FILE,

    "Add Remember Me checkbox"

)

overwrite_file(

    FILE,

    updated

)

print(

    "Done"
)