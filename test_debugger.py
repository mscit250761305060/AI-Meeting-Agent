from pathlib import Path

from agents.ai_debugger_agent import (
    fix_error
)

code = Path(
    "generated_projects/employee_management_demo/app.py"
).read_text()

fixed = fix_error(

    "app.py",

    code,

    "NameError: employee is not defined"

)

print(fixed)