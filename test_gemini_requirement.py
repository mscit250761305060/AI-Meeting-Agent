from agents.gemini_requirement_agent import (
    extract_requirements_ai
)

transcript = """

Create Employee Management System.

Add Login Page.

Add Dashboard.

Add Employee List Page.

Employee List should have Search Bar.

Employee Form should have Salary Field.

"""

requirements = extract_requirements_ai(
    transcript
)

print(requirements)