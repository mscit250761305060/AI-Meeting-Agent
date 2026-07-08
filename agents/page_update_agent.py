from pathlib import Path


def update_existing_pages(requirements, project_path):

    updates = requirements.get("page_updates", [])

    if not updates:

        print("No page updates found.")

        return

    project_path = Path(project_path)

    print("\nUpdating Existing Pages...")

    for update in updates:

        page = update["page"]

        instruction = update["instruction"]

        filename = page.replace(" ", "_") + ".html"

        filepath = project_path / filename

        if not filepath.exists():

            print(f"{filename} not found.")

            continue

        html = filepath.read_text(
            encoding="utf-8"
        )

        print(f"Updating {filename} -> {instruction}")

        # ----------------------------
        # Search Bar
        # ----------------------------

        if (
            instruction == "Add Search Bar"
            and 'id="searchBox"' not in html
        ):

            search_html = """

<hr>

<h3>Search Employee</h3>

<input
id="searchBox"
type="text"
placeholder="Search Employee">

"""

            html = html.replace(
                "<table",
                search_html + "\n<table",
                1
            )

        # ----------------------------
        # Salary Field
        # ----------------------------

        if (
            instruction == "Add Salary Field"
            and 'id="salary"' not in html
        ):

            salary_html = """

<label>Salary</label><br>
<input
id="salary"
type="number"><br><br>

"""

            html = html.replace(
                '<button type="button"',
                salary_html + '\n<button type="button"',
                1
            )

        filepath.write_text(
            html,
            encoding="utf-8"
        )

    print("Existing Page Update Completed.")