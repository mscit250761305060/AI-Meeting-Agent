from agents.local_requirement_agent import (
    extract_requirements_local
)

text = """
employee management system
dashboard page
employee list page
employee form page
login page
"""

print(
    extract_requirements_local(text)
)