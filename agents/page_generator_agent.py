from pathlib import Path

def generate_pages(requirements, project_path):

    project_path = Path(project_path)

    pages = requirements.get("pages", [])

    for page in pages:

        page_name = page.lower().strip()

        filename = (
            page_name
            .replace(" ", "_")
            + ".html"
        )

        print("Creating:", filename)

    navigation = ""

    for nav_page in pages:

        nav_file = (
            nav_page.lower()
            .strip()
            .replace(" ", "_")
            + ".html"
        )

        nav_link = nav_file

        navigation += (
            f'<a href="{nav_link}">'
            f'{nav_page}</a> | '
        )

    for page in pages:

        page_name = page.lower().strip()

        filename = (
            page_name
            .replace(" ", "_")
            + ".html"
        )

        # LOGIN PAGE

        if "login" in page_name:

            content = f"""

            <!DOCTYPE html>

            <html>
            <head>
            <title>Login</title>
            </head>
            <body>
            <div>
                {navigation}
            </div>

            <hr>

            <h1>Login Page</h1>

            <form>

            <label>Email</label><br> <input type="email"><br><br>

            <label>Password</label><br> <input type="password"><br><br>

            <button type="submit">
            Login
            </button>

            </form>

            </body>
            </html>
            """


        # DASHBOARD

        elif "dashboard" in page_name:

            content = f"""

            <!DOCTYPE html>
            <html>

            <head>
                <title>Dashboard</title>
            </head>

            <body>

            <nav>
                {navigation}
            </nav>

            <hr>

            <h1>Dashboard</h1>

            <div>
                <h3>Total Employees</h3>
                <p id="totalEmployees">0</p>
            </div>

            <div>
                <h3>Departments</h3>
                <p id="departments">0</p>
            </div>

            <div>
                <h3>Active Users</h3>
                <p id="activeUsers">0</p>
            </div>

            <script>

            async function loadDashboard() {{

                const response = await fetch("/dashboard-stats");

                const stats = await response.json();

                document.getElementById("totalEmployees").innerText =
                    stats.total_employees;

                document.getElementById("departments").innerText =
                    stats.departments;

                document.getElementById("activeUsers").innerText =
                    stats.active_users;
            }}

            loadDashboard();

            </script>

            </body>
            </html>

            """


        # EMPLOYEE LIST

        elif (
            "employee list" in page_name
            or "employees" in page_name
        ):

            content = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <title>Employee List</title>
            </head>
            <body>

            <div>
                {navigation}
            </div>

            <hr>

            <h1>Employee List</h1>

            <table border="1">

            <thead>
            <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Department</th>
            <th>Action</th>
            </tr>
            </thead>

            <tbody id="employeeTable">

            </tbody>

            </table>

            <script>

            async function loadEmployees() {{

                const response = await fetch("/employees");

                const employees = await response.json();

                const table =
                    document.getElementById("employeeTable");

                table.innerHTML = "";

                employees.forEach((employee, index) => {{

                    table.innerHTML += `
                    <tr>
                        <td>${{employee.name}}</td>
                        <td>${{employee.email}}</td>
                        <td>${{employee.department}}</td>

                        <td>
                            <button onclick="deleteEmployee(${{index}})">
                                Delete
                            </button>
                        </td>
                    </tr>
                    `;

                }});

            }}

            loadEmployees();

            async function deleteEmployee(id) {{

                await fetch("/employees/" + id, {{

                    method: "DELETE"

                }});

                loadEmployees();

            }}

            </script>

            </body>
            </html>
            """


        # EMPLOYEE FORM

        elif "employee form" in page_name:

            content = f"""

            <!DOCTYPE html>
            <html>
            <head>
            <title>Employee Form</title>
            </head>
            <body>

            <div>
                {navigation}
            </div>

            <hr>

            <h1>Employee Form</h1>

            <form>

            <label>Name</label><br>
            <input id="name" type="text"><br><br>

            <label>Email</label><br>
            <input id="email" type="email"><br><br>

            <label>Department</label><br>
            <input id="department" type="text"><br><br>

            <button type="button" onclick="saveEmployee()">
            Save Employee
            </button>

            </form>

            <script>

                async function saveEmployee() {{

                    const name = document.getElementById("name").value;
                    const email = document.getElementById("email").value;
                    const department = document.getElementById("department").value;

                    await fetch("/employees", {{
                        method: "POST",
                        headers: {{
                            "Content-Type": "application/json"
                        }},
                        body: JSON.stringify({{name, email, department }})
                    }});

                    alert("Employee Saved");
                }}

            </script>

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

            <div>
                {navigation}
            </div>

            <hr>

            <h1>{page}</h1>

            </body>
            </html>
            """


        page_file = project_path / filename

        # Do not overwrite existing pages
        if page_file.exists():

            print(f"Skipping existing page: {filename}")

        else:

            with open(
                page_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(content)

            print(f"Generated new page: {filename}")

    return {
        "status": "pages_generated"
    }

