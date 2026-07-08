from pathlib import Path

MEMORY_FILE = Path(
    "data/meeting_context.txt"
)


def append_context(text):

    MEMORY_FILE.parent.mkdir(
        exist_ok=True
    )

    old = ""

    if MEMORY_FILE.exists():

        old = MEMORY_FILE.read_text(
            encoding="utf-8"
        )

    MEMORY_FILE.write_text(

        old + "\n" + text,

        encoding="utf-8"

    )


def get_context():

    if not MEMORY_FILE.exists():

        return ""

    return MEMORY_FILE.read_text(

        encoding="utf-8"

    )


def clear_context():

    MEMORY_FILE.write_text(

        "",

        encoding="utf-8"

    )