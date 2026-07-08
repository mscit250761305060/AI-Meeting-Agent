from pathlib import Path

from agents.gemini_agent import ask_gemini

from agents.response_cleaner_agent import (
    clean_llm_response
)


def generate_ai_page(
    page_name,
    output_folder
):

    prompt = f"""
You are a Senior Frontend Developer.

Generate ONLY HTML.

No explanation.

No markdown.

Create:

{page_name}
"""

    response = ask_gemini(
        prompt
    )

    html = clean_llm_response(
        response
    )

    filename = (
        page_name.lower()
        .replace(" ", "_")
        + ".html"
    )

    output_path = Path(
        output_folder
    ) / filename

    output_path.write_text(
        html,
        encoding="utf-8"
    )

    print(
        f"Generated AI Page: {filename}"
    )