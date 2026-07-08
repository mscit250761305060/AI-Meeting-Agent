from agents.file_editor_agent import (
    edit_existing_file
)

result = edit_existing_file(

    "generated_projects/employee_management_demo/login_page.html",

    "Add Remember Me checkbox"

)

print(result[:1000])