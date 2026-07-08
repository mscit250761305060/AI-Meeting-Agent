from agents.gemini_agent import ask_gemini


def fix_error(
    filename,
    code,
    error
):

    prompt = f"""
You are a Senior Python Debugger.

Fix the following code.

Return ONLY corrected code.

Filename:

{filename}

Current Code:

{code}

Error:

{error}
"""

    return ask_gemini(prompt)