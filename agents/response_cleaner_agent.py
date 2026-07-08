import re


def clean_llm_response(response):

    response = response.strip()

    # Remove markdown blocks

    response = re.sub(
        r"```html",
        "",
        response,
        flags=re.IGNORECASE
    )

    response = re.sub(
        r"```",
        "",
        response
    )

    return response.strip()