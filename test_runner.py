from agents.project_runner_agent import run_project

result = run_project(
    "generated_projects/employee_management_demo"
)

print(result)

print("\nWarnings Count:", len(result["warnings"]))
print("Errors Count:", len(result["errors"]))