def get_requirement_diff(old_requirements, new_requirements):

    old_pages = set(
        old_requirements.get("pages", [])
    )

    new_pages = set(
        new_requirements.get("pages", [])
    )

    old_features = set(
        old_requirements.get("features", [])
    )

    new_features = set(
        new_requirements.get("features", [])
    )

    return {

        "new_pages":
            list(new_pages - old_pages),

        "removed_pages":
            list(old_pages - new_pages),

        "new_features":
            list(new_features - old_features),

        "removed_features":
            list(old_features - new_features)

    }