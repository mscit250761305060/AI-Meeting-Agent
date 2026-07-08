def build_backend_prompt(requirements):
    project_title = requirements.get("project_title") or requirements.get("project_name") or "AI Generated Project"
    features = requirements.get("features", [])
    pages = requirements.get("pages", [])

    prompt = f"""
You are a Senior Python Backend Engineer.

Generate a production-ready FastAPI application in a single file `app.py`.

Rules:
- Return ONLY valid Python code. No markdown blocks, no formatting wrapper, no explanation.
- Use in-memory storage (like a list or dict). No database setup required.
- Do NOT use UUIDs for list indices; use integer indices for simplicity so the frontend can delete/update items by list index.

Project Name: {project_title}

The backend MUST expose the following REST endpoints to match the frontend JavaScript calls:

1. GET /employees
   Returns a list of all employees. Each employee is a dictionary/object with fields:
   - name (string)
   - email (string)
   - department (string)

2. POST /employees
   Accepts an employee JSON object (with name, email, department fields) and appends it to the list. Returns the created employee.

3. PUT /employees/{{employee_id}}
   Updates the employee at the integer index `employee_id`.

4. DELETE /employees/{{employee_id}}
   Deletes the employee at the integer index `employee_id`.

5. GET /dashboard-stats
   Returns dashboard stats:
   {{
      "total_employees": int (total count),
      "departments": int (count of unique departments),
      "active_users": int (count of unique employees)
   }}

Create the complete `app.py` code. Do not use placeholders. Keep it simple and clean.
"""
    return prompt