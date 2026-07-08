import json

from agents.prompt_builder_agent import (
    build_backend_prompt
)

with open(
    "data/requirements.json",
    "r",
    encoding="utf-8"
) as f:

    requirements = json.load(f)

prompt = build_backend_prompt(
    requirements
)

print(prompt)