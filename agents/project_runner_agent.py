import subprocess
import sys
import time
import re
from pathlib import Path

# Global reference to the running server process
server_process = None


def kill_process_on_port(port):
    try:
        # Find PIDs listening on the specified port
        output = subprocess.check_output(
            f"netstat -ano | findstr :{port}",
            shell=True,
            text=True
        )
        pids = set()
        for line in output.splitlines():
            # netstat lines look like: TCP  127.0.0.1:8000  0.0.0.0:0  LISTENING  PID
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts[3]:
                pid = parts[-1]
                pids.add(int(pid))

        # Kill each process
        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        time.sleep(0.5)
    except Exception:
        pass


def ensure_static_mount(project_path):
    app_path = Path(project_path) / "app.py"
    if not app_path.exists():
        return
    
    try:
        code = app_path.read_text(encoding="utf-8")
        modified = False
        
        if "StaticFiles" not in code:
            lines = code.splitlines()
            insert_idx = 0
            for i, line in enumerate(lines):
                if "import " in line:
                    insert_idx = i
                    break
            lines.insert(insert_idx, "from fastapi.staticfiles import StaticFiles")
            code = "\n".join(lines)
            modified = True
            
        if "FileResponse" not in code:
            lines = code.splitlines()
            insert_idx = 0
            for i, line in enumerate(lines):
                if "import " in line:
                    insert_idx = i
                    break
            lines.insert(insert_idx, "from fastapi.responses import FileResponse")
            code = "\n".join(lines)
            modified = True

        # Replace root endpoint (/) to return FileResponse("index.html")
        root_pattern = r'@app\.get\(\s*["\']/["\'](?:(?!@app).)*?def\s+\w+\(\s*\)\s*:(?:(?!def).)*?return\s+[^#\n]+'
        if re.search(root_pattern, code, re.DOTALL):
            root_replacement = '@app.get("/")\nasync def root():\n    return FileResponse("index.html")\n'
            code = re.sub(root_pattern, root_replacement, code, flags=re.DOTALL)
            modified = True

        if 'app.mount("/",' not in code and "app.mount('/'," not in code:
            code += '\n\n# Mount static files (must be kept last)\napp.mount("/", StaticFiles(directory=".", html=True), name="static")\n'
            modified = True
            
        if modified:
            app_path.write_text(code, encoding="utf-8")
    except Exception as e:
        print(f"Error ensuring static mount: {e}")


def run_project(project_path):
    global server_process

    # 1. Terminate tracked background process
    if server_process is not None:
        try:
            server_process.terminate()
            server_process.wait(timeout=2)
        except Exception:
            try:
                server_process.kill()
            except Exception:
                pass
        server_process = None

    # 2. Hard clean port 8001 to handle untracked processes from previous runs
    kill_process_on_port(8001)

    # 3. Ensure static mount and FileResponse root redirect are present in app.py
    ensure_static_mount(project_path)

    print("Starting Preview Server...")

    project_path = Path(project_path)
    log_file_path = project_path / "preview_server.log"

    # Truncate log file
    try:
        log_file_path.write_text("", encoding="utf-8")
    except Exception:
        pass

    try:
        # Open log file for appending uvicorn outputs
        log_file = open(log_file_path, "a", encoding="utf-8")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--port",
                "8001",
                "--host",
                "127.0.0.1"
            ],
            cwd=project_path,
            stdout=log_file,
            stderr=log_file,
            text=True
        )
        log_file.close()
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "warnings": [],
            "errors": [f"Failed to launch preview server: {e}"]
        }

    # Wait a moment to see if uvicorn starts successfully or crashes immediately
    time.sleep(1.5)

    poll = process.poll()
    if poll is not None:
        # Process has terminated (crashed)
        errors = []
        try:
            log_content = log_file_path.read_text(encoding="utf-8")
            errors = [log_content.strip() or f"Process exited with code {poll}"]
        except Exception as e:
            errors = [f"Process exited with code {poll}. Failed to read logs: {e}"]

        return {
            "success": False,
            "stdout": "",
            "warnings": [],
            "errors": errors
        }

    # Process is successfully running in background
    server_process = process

    print("Preview Ready")
    print("Preview URL:")
    print("http://127.0.0.1:8001")

    return {
        "success": True,
        "stdout": "Server started successfully on http://127.0.0.1:8001",
        "warnings": [],
        "errors": []
    }