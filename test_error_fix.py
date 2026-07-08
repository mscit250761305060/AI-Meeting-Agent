from agents.error_fix_agent import fix_project_errors

errors = """
ModuleNotFoundError:
No module named fastapi
"""

result = fix_project_errors(errors)

print(result)