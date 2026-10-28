import subprocess
import time
import sys
import os


def get_python_executable():
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable

def kill_port(port):
    try:
        # Find PIDs listening on the specified port
        output = subprocess.check_output(
            f"netstat -ano | findstr :{port}",
            shell=True,
            text=True
        )
        killed = False
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts[3]:
                pid = parts[-1]
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    killed = True
                except Exception:
                    pass
        if killed:
            print(f"[*] Cleared existing processes on port {port}")
            time.sleep(1)
    except Exception:
        pass

def is_server_running(port):
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                # Port is active. Try querying health endpoint
                import urllib.request
                import json
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
                        if response.status == 200:
                            data = json.loads(response.read().decode())
                            if "backend_server" in data:
                                return True
                except Exception:
                    pass
    except Exception:
        pass
    return False

if __name__ == "__main__":
    print("====================================")
    print("Starting AI Meeting Agent")
    print("====================================")
    
    if is_server_running(8000):
        print("[*] AI Meeting Agent is already running on http://127.0.0.1:8000")
        sys.exit(0)
        
    kill_port(8000)
    
    print("[*] Launching Uvicorn Server on http://127.0.0.1:8000\n")
    
    try:
        subprocess.run([
            get_python_executable(), 
            "-m", 
            "uvicorn", 
            "app.main:app", 
            "--host", 
            "127.0.0.1", 
            "--port", 
            "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
