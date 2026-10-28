import subprocess
import sys
import time
import re
from pathlib import Path

server_process = None
vite_process = None

def find_free_port(start_port=8001):
    import socket
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    return 8001

def kill_process_on_port(port):
    import re
    for _ in range(3):
        try:
            output = subprocess.check_output("netstat -ano", shell=True, text=True)
            pids = set()
            pattern = re.compile(rf"\s+TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)", re.IGNORECASE)
            for line in output.splitlines():
                match = pattern.search(line)
                if match:
                    pids.add(int(match.group(1)))
            if not pids: break
            for pid in pids:
                try: subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception: pass
            time.sleep(0.5)
        except Exception: break


def run_project(project_path):
    global server_process, vite_process
    
    project_path = Path(project_path)
    backend_path = project_path / "backend"
    frontend_path = project_path / "frontend"
    run_path = backend_path if backend_path.exists() else project_path

    # Clean up previous instances
    if server_process is not None:
        try: server_process.kill()
        except: pass
    if vite_process is not None:
        try: vite_process.kill()
        except: pass

    port = find_free_port(8001)
    
    kill_process_on_port(port) # FastAPI
    kill_process_on_port(3000) # Vite

    print(f"Starting Backend Server on port {port}...")
    backend_log = project_path / "backend_server.log"
    
    # 1. Start FastAPI
    try:
        log_file = open(backend_log, "w", encoding="utf-8")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--port", str(port), "--host", "127.0.0.1"],
            cwd=run_path,
            stdout=log_file,
            stderr=log_file,
            text=True
        )
    except Exception as e:
        return {"success": False, "errors": [f"Failed to start backend: {e}"], "url": ""}

    time.sleep(2)
    
    # Check if backend crashed immediately
    if server_process.poll() is not None:
        try:
            with open(backend_log, "r", encoding="utf-8") as f:
                logs = f.read()
        except:
            logs = "Server crashed but no logs were found."
        return {"success": False, "errors": [f"Backend server crashed on startup. Logs:\n{logs}"], "url": ""}

    # 2. Setup Frontend
    print("Installing Frontend Dependencies (this takes 30-45s)...")
    try:
        # Run npm install synchronously
        subprocess.run(["npm", "install"], cwd=frontend_path, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Warning: npm install failed or not found. Assuming dependencies are cached or vite will fail. Error: {e}")

    # 3. Start Vite
    vite_port = find_free_port(3000)
    kill_process_on_port(vite_port) # Vite

    print(f"Starting Vite React Server on port {vite_port}...")
    frontend_log = project_path / "vite_server.log"
    try:
        f_log_file = open(frontend_log, "w", encoding="utf-8")
        vite_process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(vite_port)],
            cwd=frontend_path,
            shell=True,
            stdout=f_log_file,
            stderr=f_log_file,
            text=True
        )
    except Exception as e:
        return {"success": False, "errors": [f"Failed to start Vite: {e}"], "url": ""}

    time.sleep(2)

    return {
        "success": True,
        "stdout": f"Servers started successfully (Backend: {port}, Frontend: {vite_port})",
        "warnings": [],
        "errors": [],
        "url": f"http://127.0.0.1:{vite_port}"
    }

if __name__ == "__main__":
    if len(sys.argv) > 1: run_project(sys.argv[1])
    else: print("Usage: python project_runner_agent.py <project_path>")