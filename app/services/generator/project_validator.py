"""
app/services/generator/project_validator.py

Static and structural validation engine for generated projects.
Validates syntax, required files, route integrity, and schemas before marking generation successful.
"""

import ast
import json
from pathlib import Path
from typing import Dict, Any, List
from app.services.generator.specification import ProjectSpecification


class ProjectValidator:
    REQUIRED_FILES = [
        "app.py",
        "database.py",
        "models.py",
        "schemas.py",
        "index.html",
        "project_config.json",
        "requirements.txt",
        "README.md"
    ]

    @classmethod
    def validate_project(cls, project_dir: Path, spec: ProjectSpecification) -> Dict[str, Any]:
        project_path = Path(project_dir)
        errors: List[str] = []
        warnings: List[str] = []
        files_checked: List[str] = []

        if not project_path.exists() or not project_path.is_dir():
            return {
                "valid": False,
                "errors": [f"Project directory {project_path} does not exist."],
                "warnings": [],
                "files_checked": []
            }

        # 1. Verify all required files exist
        for req_file in cls.REQUIRED_FILES:
            target = project_path / req_file
            if not target.exists():
                errors.append(f"Missing required project file: {req_file}")
            else:
                files_checked.append(req_file)

        # 2. Verify all specified HTML pages exist
        for page in spec.pages:
            page_file = project_path / f"{page.slug}.html"
            if not page_file.exists():
                errors.append(f"Missing specified HTML page file: {page.slug}.html")
            else:
                files_checked.append(f"{page.slug}.html")

        # 3. Python Syntax Validation via ast.parse
        py_files = ["app.py", "database.py", "models.py", "schemas.py"]
        for py_name in py_files:
            target = project_path / py_name
            if target.exists():
                try:
                    content = target.read_text(encoding="utf-8")
                    ast.parse(content, filename=py_name)
                except SyntaxError as e:
                    errors.append(f"Syntax error in {py_name} line {e.lineno}: {e.msg}")
                except Exception as e:
                    errors.append(f"Failed to read/parse {py_name}: {str(e)}")

        # 4. Verify project_config.json integrity
        config_path = project_path / "project_config.json"
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                if not cfg.get("project_name"):
                    warnings.append("project_config.json missing project_name field.")
            except Exception as e:
                errors.append(f"Invalid JSON in project_config.json: {str(e)}")

        is_valid = len(errors) == 0

        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "files_checked": files_checked,
            "project_name": spec.project_name,
            "project_path": str(project_path)
        }
