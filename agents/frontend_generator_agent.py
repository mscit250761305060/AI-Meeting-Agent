from pathlib import Path


def generate_frontend(requirements, project_path):

    project_path = Path(project_path)

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{requirements.get("project_title")}</title>
</head>
<body>

    <h1>{requirements.get("project_title")}</h1>

    <h2>Features</h2>

    <ul>
        {
            ''.join(
                [f"<li>{feature}</li>"
                 for feature in requirements.get("features", [])]
            )
        }
    </ul>

    <h2>Pages</h2>

    <ul>

    <li>
    <a href="dashboard_page.html">
    Dashboard
    </a>
    </li>

    <li>
    <a href="employee_list_page.html">
    Employee List
    </a>
    </li>

    <li>
    <a href="employee_form_page.html">
    Employee Form
    </a>
    </li>

    <li>
    <a href="login_page.html">
    Login
    </a>
    </li>

    </ul>

    <h2>Add Item</h2>

    <input id="name" placeholder="Enter Name">

    <button onclick="addItem()">
        Add
    </button>

    <script>

    async function addItem() {{

        const name =
            document.getElementById("name").value;

        await fetch(
            "/items",
            {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/json"
                }},
                body: JSON.stringify({{
                    name: name
                }})
            }}
        );

        alert("Added");
    }}

    </script>

</body>
</html>
"""

    with open(
        project_path / "index.html",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html)

    return {
        "status": "frontend_generated"
    }