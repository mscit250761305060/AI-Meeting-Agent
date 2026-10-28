from generators.page_generator_agent import generate_pages


def generate_new_pages(diff, requirements, project_path):

    if not diff["new_pages"]:

        print("No new pages found.")

        return

    temp_requirements = requirements.copy()

    temp_requirements["pages"] = diff["new_pages"]

    print("\nGenerating ONLY new pages...")

    generate_pages(
        temp_requirements,
        project_path
    )