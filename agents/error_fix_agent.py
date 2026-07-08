from agents.gemini_agent import ask_gemini


def fix_project_errors(errors):

    if not errors:
        print("No errors found.")
        return None

    prompt = f"""
You are an expert Python developer.

The generated project has these errors:

{errors}

Return ONLY the corrected files as JSON.

Example:

{{
    "app.py":"...",
    "models.py":"..."
}}

Do not explain anything.
Only return JSON.
"""

    print("Sending Errors to Gemini...")

    response = ask_gemini(prompt)

    return response