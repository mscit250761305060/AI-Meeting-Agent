from pathlib import Path

from agents.gemini_agent import ask_gemini

from agents.response_cleaner_agent import (
    clean_llm_response
)

from agents.prompt_builder_agent import (
    build_backend_prompt
)


def generate_backend(
    requirements,
    output_folder
):

    prompt = build_backend_prompt(
        requirements
    )

    response = ask_gemini(
        prompt
    )

    code = clean_llm_response(
        response
    )

    # Ensure StaticFiles and FileResponse are imported and mounted at the end
    import re

    if "StaticFiles" not in code:
        lines = code.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if "import " in line:
                insert_idx = i
                break
        lines.insert(insert_idx, "from fastapi.staticfiles import StaticFiles")
        code = "\n".join(lines)

    if "FileResponse" not in code:
        lines = code.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if "import " in line:
                insert_idx = i
                break
        lines.insert(insert_idx, "from fastapi.responses import FileResponse")
        code = "\n".join(lines)

    # Replace root endpoint (/) to return FileResponse("index.html")
    # This matches @app.get("/") with any parameters, followed by the function definition and return statement
    # without crossing boundaries into other endpoints or functions
    root_pattern = r'@app\.get\(\s*["\']/["\'](?:(?!@app).)*?def\s+\w+\(\s*\)\s*:(?:(?!def).)*?return\s+[^#\n]+'
    root_replacement = '@app.get("/")\nasync def root():\n    return FileResponse("index.html")\n'
    code = re.sub(root_pattern, root_replacement, code, flags=re.DOTALL)

    if 'app.mount("/",' not in code and "app.mount('/'," not in code:
        code += '\n\n# Mount static files (must be kept last)\napp.mount("/", StaticFiles(directory=".", html=True), name="static")\n'

    output = Path(
        output_folder
    ) / "app.py"

    output.write_text(
        code,
        encoding="utf-8"
    )

    print(
        "AI Backend Generated"
    )