from pathlib import Path


def find_related_files(
    project_path,
    requirement
):

    project = Path(project_path)

    matches = []

    keywords = requirement.lower().split()

    for file in project.rglob("*"):

        if not file.is_file():
            continue

        score = 0

        name = file.name.lower()

        # Exact filename bonus
        if requirement.lower().replace(" ", "_") in name:
            score += 10

        # Keyword matching
        for word in keywords:

            if word in name:
                score += 1

        # Ignore temporary AI pages
        if "please_add" in name:
            score -= 5

        if score > 0:

            matches.append(

                (

                    score,

                    str(file)

                )

            )

    matches.sort(

        reverse=True

    )

    return [

        path

        for _, path in matches

    ]