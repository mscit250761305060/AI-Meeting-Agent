from pathlib import Path


TRANSCRIPT_FILE = Path(
    "data/live_transcript.txt"
)


def append_transcript(text):

    with open(

        TRANSCRIPT_FILE,

        "a",

        encoding="utf-8"

    ) as file:

        file.write(text)

        file.write("\n")

    print(

        "Transcript Updated"

    )