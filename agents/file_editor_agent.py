from pathlib import Path

from agents.gemini_agent import ask_gemini


def edit_existing_file(

    file_path,

    instruction

):

    path = Path(file_path)

    if not path.exists():

        return None

    old_code = path.read_text(

        encoding="utf-8"

    )

    prompt = f"""
You are an expert software engineer.

Update ONLY this file.

Do NOT explain.

Do NOT return markdown.

Return ONLY the complete updated file.

Instruction:

{instruction}

Current File:

{old_code}
"""

    updated = ask_gemini(prompt)

    return updated