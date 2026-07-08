from agents.local_requirement_agent import (
    extract_requirements_local
)

text = """
employee management system

dashboard page

employee list page

employee form page

login page

please add search bar in employee list page

please add salary field in employee form page
"""

print(
    extract_requirements_local(text)
)