def decide_generators(changes):

    generators = []

    if "pages" in changes:

        generators.append(
            "page_generator"
        )

    if "features" in changes:

        generators.append(
            "crud_generator"
        )

    if "page_updates" in changes:

        generators.append(
            "page_updater"
        )

    return generators