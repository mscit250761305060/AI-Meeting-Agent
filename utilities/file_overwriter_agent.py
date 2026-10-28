from pathlib import Path


def overwrite_file(

    file_path,

    content

):

    path = Path(file_path)

    path.write_text(

        content,

        encoding="utf-8"

    )

    print(

        "Updated:",

        path.name

    )