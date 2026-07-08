import ast
import os
from pathlib import Path

def get_local_imports(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except Exception as e:
        return []
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    
    # Filter only local modules (agents, server, etc.)
    local_modules = []
    for imp in imports:
        if imp.startswith("agents.") or imp.startswith("server.") or imp.startswith("app."):
            local_modules.append(imp.replace(".", "/") + ".py")
    return local_modules

def trace_dependencies(entry_points, base_dir):
    visited = set()
    queue = list(entry_points)
    
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
            
        visited.add(current)
        full_path = os.path.join(base_dir, current)
        if not os.path.exists(full_path):
            # Try without .py if it's a package
            if os.path.exists(full_path.replace(".py", "")):
                pass
            continue
            
        deps = get_local_imports(full_path)
        for dep in deps:
            if dep not in visited:
                queue.append(dep)
                
    return visited

if __name__ == "__main__":
    base = "c:/Users/Admin/ai-meeting-agent"
    used_files = trace_dependencies(["app/main.py"], base)
    print("ACTIVE FILES:\n" + "\n".join(sorted(used_files)))
