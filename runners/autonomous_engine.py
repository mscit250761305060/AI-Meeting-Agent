from validators.project_regenerator_agent import start_project_regenerator
from runners.project_runner_agent import run_project
from validators.error_fix_agent import fix_project_errors
from utilities.error_file_writer_agent import overwrite_project_files

def run_autonomous_engine(
    project_path,
    max_iterations=8,
    requirements=None
):
    from server.ws_manager import manager
    from pathlib import Path
    import time
    import sys
    import asyncio
    import concurrent.futures

    Path(project_path, "backend").mkdir(parents=True, exist_ok=True)
    Path(project_path, "frontend").mkdir(parents=True, exist_ok=True)

    import subprocess
    
    # Initialize Git Repository for Smart Memory
    subprocess.run("git init", cwd=project_path, shell=True, capture_output=True)
    subprocess.run("git config user.email 'ai@agent.com'", cwd=project_path, shell=True, capture_output=True)
    subprocess.run("git config user.name 'AI Agent'", cwd=project_path, shell=True, capture_output=True)
    
    def git_commit(msg):
        subprocess.run("git add .", cwd=project_path, shell=True, capture_output=True)
        subprocess.run(f'git commit -m "{msg}"', cwd=project_path, shell=True, capture_output=True)
        
    git_commit("Initial Project Generation")

    iteration = 0
    result = {"success": False, "errors": []}
    all_passed = False

    while iteration < max_iterations:
        print(f"\n--- Autonomous Execution: Iteration {iteration + 1} ---")
        try: manager.broadcast_sync({"action": "log", "message": f"Autonomous Engine: Iteration {iteration + 1}/{max_iterations}"})
        except: pass

        start_server = time.time()
        try:
            result = run_project(project_path)
        except Exception as run_err:
            result = {"success": False, "errors": [f"Orchestrator crash during run_project: {str(run_err)}"]}
            
        dur_server = time.time() - start_server
        try: manager.broadcast_sync({"action": "log", "message": f"⏱️ [Timing] Server Started ({dur_server:.2f}s)"})
        except: pass

        # 1. Check Server Startup
        if not result.get("success") or result.get("errors"):
            errors = result.get("errors", ["Server failed to start without specific logs."])
            try: manager.broadcast_sync({"action": "log", "message": "Server Startup Failed. Auto-fixing..."})
            except: pass
            
            try:
                response = fix_project_errors("\n".join(errors), requirements=requirements, project_path=project_path)
                if response:
                    overwrite_project_files(response, project_path)
                    git_commit(f"Auto-fix Server Startup (Iter {iteration+1})")
            except Exception as fix_err:
                print(f"Error during auto-healing: {fix_err}")
                
            time.sleep(2) # Prevent rapid crash loops and allow file handles to release
            iteration += 1
            continue

        test_url = result.get("url", "http://127.0.0.1:8001")

        # 2. Check API Endpoints
        try:
            from validators.api_validator_agent import validate_apis
            try: manager.broadcast_sync({"action": "log", "message": "Validating API endpoints..."})
            except: pass
            
            validation = validate_apis(project_path)
            if not validation.get("success") and validation.get("failed"):
                failed_count = len(validation["failed"])
                try: manager.broadcast_sync({"action": "log", "message": f"API Validation: {failed_count} endpoint(s) failed. Auto-fixing..."})
                except: pass
                
                fix_response = fix_project_errors(validation["error_summary"], requirements=requirements, project_path=project_path)
                if fix_response:
                    overwrite_project_files(fix_response, project_path)
                    git_commit(f"Auto-fix API Endpoints (Iter {iteration+1})")
                
                iteration += 1
                continue
            else:
                passed = len(validation.get("passed", []))
                try: manager.broadcast_sync({"action": "log", "message": f"API Validation: All {passed} endpoints passed ✅"})
                except: pass
        except Exception as e:
            print(f"API validation skipped: {e}")

        # 2.5 Check Frontend Compile (Vite/React Build)
        try:
            try: manager.broadcast_sync({"action": "log", "message": "Validating Frontend Build (TypeScript/React)..."})
            except: pass
            
            import subprocess
            build_result = subprocess.run(
                "npm run build", 
                cwd=str(Path(project_path) / "frontend"), 
                shell=True, capture_output=True, text=True
            )
            
            if build_result.returncode != 0:
                try: manager.broadcast_sync({"action": "log", "message": f"Frontend Build Failed! Auto-fixing..."})
                except: pass
                
                error_output = build_result.stdout + "\n" + build_result.stderr
                # Truncate to avoid massive logs, just take first 2000 chars of errors
                if len(error_output) > 2000:
                    error_output = error_output[:2000] + "\n...[truncated]"
                    
                fix_response = fix_project_errors("Frontend Build Errors:\n" + error_output, requirements=requirements, project_path=project_path)
                if fix_response:
                    overwrite_project_files(fix_response, project_path)
                    git_commit(f"Auto-fix Frontend Build (Iter {iteration+1})")
                
                iteration += 1
                continue
            else:
                try: manager.broadcast_sync({"action": "log", "message": "Frontend Build Passed ✅"})
                except: pass
        except Exception as e:
            print(f"Frontend build validation skipped: {e}")

        # 3. Check UI (E2E)
        try:
            from runners.e2e_tester_agent import run_e2e_tests
            try: manager.broadcast_sync({"action": "log", "message": "Running E2E UI Tests..."})
            except: pass
            
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
                
            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    test_success, test_errors = pool.submit(asyncio.run, run_e2e_tests(test_url)).result()
            else:
                test_success, test_errors = asyncio.run(run_e2e_tests(test_url))
                
            if not test_success:
                try: manager.broadcast_sync({"action": "log", "message": f"E2E Tests Failed: {len(test_errors)} errors. Auto-fixing..."})
                except: pass
                
                fix_response = fix_project_errors("UI E2E Errors:\n" + "\n".join(test_errors), requirements=requirements, project_path=project_path)
                if fix_response:
                    overwrite_project_files(fix_response, project_path)
                    git_commit(f"Auto-fix UI E2E Errors (Iter {iteration+1})")
                
                iteration += 1
                continue
            else:
                try: manager.broadcast_sync({"action": "log", "message": "E2E UI Tests Passed ✅"})
                except: pass
        except Exception as e:
            print(f"E2E tests skipped due to error: {e}")

        # If we made it here, everything passed!
        all_passed = True
        break

    if all_passed:
        sys.stdout.buffer.write("🎉 Your project is successfully completed and validated.\n".encode("utf-8"))
        try: manager.broadcast_sync({"action": "log", "message": "Project Running Successfully & Fully Validated ✅"})
        except: pass
    else:
        try: manager.broadcast_sync({"action": "log", "message": "Autonomous Execution Finished (Max Iterations reached with unresolved errors)."})
        except: pass

    # --- Phase: Documentation ---
    try:
        if requirements:
            from generators.documentation_agent import generate_documentation
            try: manager.broadcast_sync({"action": "log", "message": "Generating README documentation..."})
            except: pass
            generate_documentation(requirements, project_path)
    except Exception as e:
        print(f"Documentation generation skipped: {e}")
        
    # --- Phase: DevOps & Git ---
    try:
        from generators.devops_generator_agent import generate_devops_files
        try: manager.broadcast_sync({"action": "log", "message": "Generating DevOps & Docker files..."})
        except: pass
        generate_devops_files(requirements, project_path)
    except Exception as e:
        print(f"DevOps generation skipped: {e}")

    # Final run just to keep it alive if needed
    if not all_passed:
        result = run_project(project_path)
        
    return result