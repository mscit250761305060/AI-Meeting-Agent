from pathlib import Path


def update_existing_features(requirements, project_path):

    page_updates = requirements.get("page_updates", [])

    if not page_updates:

        print("No page updates found.")

        return

    project_path = Path(project_path)

    print("\nUpdating Existing Pages...")

    for update in page_updates:

        page = update["page"]
        instruction = update["instruction"]

        filename = (
            page.lower()
            .replace(" ", "_")
            + ".html"
        )

        page_file = project_path / filename

        if not page_file.exists():

            print(f"Page not found: {filename}")

            continue

        print(
            f"Updating {filename} -> {instruction}"
        )

    print("Existing Page Update Completed.")