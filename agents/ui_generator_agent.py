from pathlib import Path


def generate_ui(requirements, project_path):

    project_path = Path(project_path)

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{requirements.get("project_title")}</title>

    <style>

    body {{
        font-family: Arial;
        margin: 40px;
    }}

    .card {{
        border: 1px solid #ddd;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }}

    </style>

</head>

<body>

    <h1>{requirements.get("project_title")}</h1>

    <div class="card">

        <h2>Features</h2>

        <ul>
            {
                "".join(
                    [
                        f"<li>{feature}</li>"
                        for feature in requirements.get("features", [])
                    ]
                )
            }
        </ul>

    </div>

</body>
</html>
"""

    with open(
        project_path / "index.html",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html_content)

    return {
        "status": "ui_generated"
    }