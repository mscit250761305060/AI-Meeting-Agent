from pathlib import Path

def generate_pages(requirements, project_path):

    project_path = Path(project_path)

    pages = requirements.get("pages", [])

    for page in pages:

        filename = (
            page.lower()
            .replace(" ", "_")
            + ".html"
        )

        if page.lower() == "dashboard":

            content = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
</head>
<body>

<nav>
    <a href="dashboard.html">Dashboard</a>
    <a href="employee_list.html">Employee List</a>
    <a href="employee_form.html">Employee Form</a>
</nav>

<h1>Dashboard</h1>

<div>
    <h2>Total Employees</h2>
    <h3>25</h3>
</div>

</body>
</html>
"""

        elif page.lower() == "employee list":

            content = """
<!DOCTYPE html>
<html>
<head>
    <title>Employee List</title>
</head>
<body>

<nav>
    <a href="dashboard.html">Dashboard</a>
    <a href="employee_list.html">Employee List</a>
    <a href="employee_form.html">Employee Form</a>
</nav>

<h1>Employee List</h1>

<table border="1">
<tr>
    <th>Name</th>
    <th>Email</th>
    <th>Department</th>
</tr>

<tr>
    <td>Jeel</td>
    <td>jeel@test.com</td>
    <td>IT</td>
</tr>

</table>

</body>
</html>
"""

        elif page.lower() == "employee form":

            content = """
<!DOCTYPE html>
<html>
<head>
    <title>Employee Form</title>
</head>
<body>

<nav>
    <a href="dashboard.html">Dashboard</a>
    <a href="employee_list.html">Employee List</a>
    <a href="employee_form.html">Employee Form</a>
</nav>

<h1>Employee Form</h1>

<form>

<label>Name</label><br>
<input type="text"><br><br>

<label>Email</label><br>
<input type="email"><br><br>

<label>Department</label><br>
<input type="text"><br><br>

<button type="submit">
Submit
</button>

</form>

</body>
</html>
"""

        else:

            content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{page}</title>
</head>
<body>

<h1>{page}</h1>

</body>
</html>
"""

        with open(
            project_path / filename,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(content)

    return {"status": "pages_generated"}