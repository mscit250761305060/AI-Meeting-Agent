from agents.project_regenerator_agent import (
    start_project_regenerator
)

from agents.project_runner_agent import (
    run_project
)

from agents.error_fix_agent import (
    fix_project_errors
)

from agents.error_file_writer_agent import (
    overwrite_project_files
)


def run_autonomous_engine(
    project_path,
    max_iterations=3
):
    from app.services.ws_manager import manager
    
    iteration = 0
    result = {"success": False, "errors": []}

    while iteration < max_iterations:
        print(f"\nIteration {iteration + 1}")
        manager.broadcast_sync({"action": "log", "message": f"Autonomous Execution: Iteration {iteration + 1}"})

        result = run_project(project_path)
        print(result)

        if not result.get("success") or result.get("errors"):
            errors = result.get("errors", [])
            if not errors:
                errors = ["Server failed to start without specific logs."]
                
            print("Server errors detected...")
            manager.broadcast_sync({"action": "log", "message": f"Detected errors in server execution."})
            
            try:
                response = fix_project_errors("\n".join(errors))
                if response:
                    overwrite_project_files(response, project_path)
            except Exception as e:
                print(f"Error fix skipped (AI unavailable): {e}")
        else:
            print("Project Running Successfully 🎉")
            manager.broadcast_sync({"action": "log", "message": "Project Running Successfully 🎉"})
            return result

        iteration += 1

    print("\nAutonomous Execution Finished")
    manager.broadcast_sync({"action": "log", "message": "Autonomous Execution Finished (Max Iterations reached)."})
    
    # Do a final run test to return the state
    return run_project(project_path)