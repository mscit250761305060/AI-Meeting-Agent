from pathlib import Path


MEMORY_FILE = Path(
    "data/meeting_memory.txt"
)


def add_to_memory(text):

    if not text.strip():
        return

    previous = ""

    if MEMORY_FILE.exists():

        previous = MEMORY_FILE.read_text(
            encoding="utf-8"
        )

    previous += "\n" + text.strip()

    MEMORY_FILE.write_text(

        previous,

        encoding="utf-8"

    )


def get_memory():

    if MEMORY_FILE.exists():

        return MEMORY_FILE.read_text(
            encoding="utf-8"
        )

    return ""


def clear_memory():

    MEMORY_FILE.write_text(
        "",
        encoding="utf-8"
    )