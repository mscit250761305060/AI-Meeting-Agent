import re


def clean_json_response(response):

    response = response.strip()

    # Remove ```json
    response = re.sub(
        r"^```json",
        "",
        response,
        flags=re.IGNORECASE
    )

    # Remove ```
    response = re.sub(
        r"```$",
        "",
        response
    )

    return response.strip()