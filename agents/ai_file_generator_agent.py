from pathlib import Path

from agents.gemini_agent import ask_gemini
from agents.response_cleaner_agent import clean_llm_response


def generate_file(
    requirements,
    filename,
    instruction,
    output_folder
):

    prompt = f"""
You are a Senior Full Stack Developer.

Return ONLY code.

No markdown.
No explanation.

Project:

{requirements}

Generate:

{filename}

Instruction:

{instruction}
"""

    response = ask_gemini(prompt)

    code = clean_llm_response(response)

    path = Path(output_folder) / filename

    path.write_text(
        code,
        encoding="utf-8"
    )

    print(f"Generated: {filename}")