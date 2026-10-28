import logging
from pathlib import Path
from utilities.llm_utils import generate_content_with_retry
from types import SimpleNamespace
from config import get_model

logger = logging.getLogger(__name__)

def run_code_review(project_path: str):
    """
    Code Reviewer Agent. Scans the generated code and provides feedback/fixes.
    For demonstration, we scan the main backend app.py
    """
    backend_app = Path(project_path) / "backend" / "app.py"
    if not backend_app.exists(): return
    
    code = backend_app.read_text(encoding="utf-8")
    
    prompt = f"""
    You are an elite Security & Code Reviewer Agent.
    Review the following FastAPI code for Security, SOLID principles, and Clean Architecture.
    
    Code:
    {code}
    
    If the code is good, return the exact same code.
    If the code has vulnerabilities (e.g., missing CORS, bad error handling), rewrite it to be production-ready.
    
    Output ONLY the raw Python code wrapped in ```python ... ```
    """
    
    try:
        response = generate_content_with_retry(
            model_name=get_model("backend"),
            contents=prompt,
            config=SimpleNamespace(temperature=0.1)
        )
        new_code = response.text.strip()
        if new_code.startswith("```python"): new_code = new_code[9:].strip()
        if new_code.startswith("```"): new_code = new_code[3:].strip()
        if new_code.endswith("```"): new_code = new_code[:-3].strip()
        
        backend_app.write_text(new_code, encoding="utf-8")
        logger.info("Code Reviewer Agent fixed backend/app.py.")
    except Exception as e:
        logger.error(f"Code review failed: {e}")
