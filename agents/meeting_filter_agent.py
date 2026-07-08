PROJECT_KEYWORDS = [

    "create",
    "add",
    "remove",
    "delete",
    "update",
    "page",
    "dashboard",
    "login",
    "register",
    "employee",
    "user",
    "project",
    "system",
    "api",
    "database",
    "crud",
    "feature"

]


def is_project_requirement(text):

    if not text:
        return False

    text = text.strip().lower()

    if len(text) < 10:
        return False

    if text.count(".") > 5:
        return False

    if "..." in text:
        return False

    # for phrase in IGNORE_PHRASES:

    #     if phrase in text:
    #         return False

    # return True

    for keyword in PROJECT_KEYWORDS:

        if keyword in text:

            return True

    return False