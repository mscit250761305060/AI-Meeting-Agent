import re


ADD_KEYWORDS = [
    "add",
    "include",
    "need",
    "create",
    "implement"
]

REMOVE_KEYWORDS = [
    "remove",
    "delete",
    "discard"
]

UPDATE_KEYWORDS = [
    "change",
    "modify",
    "update",
    "replace"
]


def detect_action(text: str):

    lower = text.lower()

    for word in REMOVE_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return "REMOVE"

    for word in UPDATE_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return "UPDATE"

    for word in ADD_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", lower):
            return "ADD"

    return "UNKNOWN"