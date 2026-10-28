"""
api_validator_agent.py

After the preview server starts on port 8001, this agent:
1. Reads backend/app.py to discover all registered API routes
2. Waits for the server to be ready
3. Hits every GET endpoint and the login POST endpoint
4. Returns a structured validation report with failures
5. Failure details are fed back to the autonomous engine for targeted error fixing
"""

import re
import time
import requests
from pathlib import Path


BASE_URL = "http://127.0.0.2:8001"
LOGIN_CREDENTIALS = {"username": "admin", "password": "password123"}
REQUEST_TIMEOUT = 5


def _wait_for_server(max_wait: int = 15) -> bool:
    """Poll the server root until it responds or timeout."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/", timeout=2)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False

def _retry_request(req_func, *args, retries=3, **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            return req_func(*args, **kwargs)
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise last_err


def _extract_routes(app_py_source: str) -> dict:
    """
    Parse @app.get("/path"), @app.post("/path"), etc. from app.py source.
    Returns {method: [list of paths]}.
    """
    routes = {"GET": [], "POST": [], "PUT": [], "DELETE": []}
    pattern = re.compile(
        r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    for match in pattern.finditer(app_py_source):
        method = match.group(1).upper()
        path = match.group(2)
        # Skip static mount routes and paths with required path params only
        if "{" not in path and path != "/":
            routes.get(method, []).append(path)
    return routes


def validate_apis(project_path: str) -> dict:
    """
    Validate all API endpoints in the generated backend.
    Returns:
        {
            "success": bool,
            "passed": [list of passing endpoints],
            "failed": [list of {endpoint, method, status_code, error}],
            "error_summary": str  (suitable for error_fix_agent)
        }
    """
    project_path = Path(project_path)
    app_py = project_path / "backend" / "app.py"

    if not app_py.exists():
        return {
            "success": False,
            "passed": [],
            "failed": [],
            "error_summary": "backend/app.py not found — cannot validate APIs."
        }

    source = app_py.read_text(encoding="utf-8")
    routes = _extract_routes(source)

    print("API Validator: Waiting for server to be ready...")
    if not _wait_for_server():
        return {
            "success": False,
            "passed": [],
            "failed": [],
            "error_summary": "Server did not start on http://127.0.0.1:8001 within 15 seconds."
        }

    print("API Validator: Server is ready. Starting endpoint validation...")

    passed = []
    failed = []

    # First try to get an auth token
    token = None
    try:
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=LOGIN_CREDENTIALS,
            timeout=REQUEST_TIMEOUT
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            passed.append("POST /api/auth/login")
            print("API Validator: ✅ POST /api/auth/login — 200")
        else:
            failed.append({
                "endpoint": "/api/auth/login",
                "method": "POST",
                "status_code": login_resp.status_code,
                "error": login_resp.text[:300]
            })
            print(f"API Validator: ❌ POST /api/auth/login — {login_resp.status_code}")
    except Exception as e:
        failed.append({
            "endpoint": "/api/auth/login",
            "method": "POST",
            "status_code": 0,
            "error": str(e)
        })
        print(f"API Validator: ❌ POST /api/auth/login — {e}")

    # Build auth headers if we have a token
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Validate all GET endpoints
    for path in routes.get("GET", []):
        try:
            r = _retry_request(
                requests.get,
                f"{BASE_URL}{path}",
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )
            if r.status_code < 400:
                try:
                    data = r.json()
                    passed.append(f"GET {path}")
                    print(f"API Validator: ✅ GET {path} — {r.status_code} (Valid JSON)")
                except Exception:
                    failed.append({
                        "endpoint": path,
                        "method": "GET",
                        "status_code": r.status_code,
                        "error": "Response was not valid JSON"
                    })
                    print(f"API Validator: ❌ GET {path} — {r.status_code} (Invalid JSON)")
            else:
                failed.append({
                    "endpoint": path,
                    "method": "GET",
                    "status_code": r.status_code,
                    "error": r.text[:300]
                })
                print(f"API Validator: ❌ GET {path} — {r.status_code}")
        except Exception as e:
            failed.append({
                "endpoint": path,
                "method": "GET",
                "status_code": 0,
                "error": str(e)
            })
            print(f"API Validator: ❌ GET {path} — {e}")

    success = len(failed) == 0

    # Build error summary string for error_fix_agent
    error_summary = ""
    if failed:
        lines = ["The following API endpoints are returning errors after server startup:\n"]
        for f in failed:
            lines.append(f"  [{f['method']}] {f['endpoint']} → HTTP {f['status_code']}: {f['error']}")
        error_summary = "\n".join(lines)

    print(f"\nAPI Validator: {len(passed)} passed, {len(failed)} failed.")
    return {
        "success": success,
        "passed": passed,
        "failed": failed,
        "error_summary": error_summary
    }
