from pathlib import Path
import json
import re
from types import SimpleNamespace
from utilities.llm_utils import generate_content_with_retry
from utilities.json_response_cleaner_agent import clean_json_response
from config import get_model

def extract_files_from_dict(d, current_path=""):
    files = {}
    if isinstance(d, dict):
        if "code" in d and isinstance(d["code"], str):
            name = current_path if current_path.endswith(".py") else current_path + ".py"
            files[name] = d["code"]
            return files
        for k, v in d.items():
            new_path = f"{current_path}/{k}" if current_path else k
            if isinstance(v, str):
                name = new_path if new_path.endswith(".py") else new_path + ".py"
                files[name] = v
            else:
                files.update(extract_files_from_dict(v, new_path))
    return files

def generate_backend(requirements, output_folder):
    blueprint = requirements.get("blueprint")
    if not blueprint:
        raise ValueError("Blueprint missing from requirements. Please run Architect Agent first.")
        
    project_path = Path(output_folder)
    backend_path = project_path / "backend"
    backend_path.mkdir(exist_ok=True)
    
    # Create Layered Folders
    for folder in ["api", "services", "repositories", "core"]:
        (backend_path / folder).mkdir(exist_ok=True)
        (backend_path / folder / "__init__.py").write_text("", encoding="utf-8")
        
    def write_safe(filename: str, code: str):
        if filename.startswith("backend/"):
            filename = filename[len("backend/"):]
        elif filename.startswith("/"):
            filename = filename[1:]
        file_path = backend_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")
        print(f"Generated {filename}")
    
    # 1. Generate Core Files (database, models, schemas, config)
    core_prompt = f"""
    You are an elite Python Backend Architect. Generate database.py, models.py, schemas.py, and core/config.py for a FastAPI app based on this Database Schema:
    {json.dumps(blueprint.get("database_schema", []), indent=4)}
    
    API Endpoints that will be built:
    {json.dumps(blueprint.get("api_endpoints", []), indent=4)}
    
    Output a STRICT JSON object:
    {{
        "database.py": "code...",
        "models.py": "code...",
        "schemas.py": "code...",
        "core/config.py": "code...",
        "core/exceptions.py": "code..."
    }}
    
    Rules:
    - database.py MUST include the SQLAlchemy get_db() dependency function!
    - models.py must import Base from database. Add __table_args__ = {{'extend_existing': True}} to all models. Use SQLAlchemy 2.0 style mapped_column.
    - STRICTLY adhere to the provided Database Schema. Do NOT add ANY extra constraints (e.g., UniqueConstraint) unless explicitly specified in the blueprint. 
    - Do NOT change default values. If a default is specified in the schema, use exactly that value.
    - schemas.py must use Pydantic V2 (BaseModel, ConfigDict). Generate ALL necessary request/response schemas with rigorous validation (e.g. EmailStr).
    - core/config.py must use pydantic_settings (BaseSettings) to load environment variables (.env). Provide default fallbacks for SECRET_KEY, DB_URL, etc. The default DATABASE_URL MUST be 'mysql+pymysql://root:root@localhost:3306/project_db'.
    - core/exceptions.py should define centralized custom API exceptions (e.g., NotFoundException, UnauthorizedException).
    - Use absolute imports (e.g., 'from core.config import settings', 'from database import Base'). DO NOT prefix with 'backend.'.
    - ALWAYS implement secure JWT Authentication (using PyJWT and passlib).
    - Implement Role-Based Access Control (RBAC) middleware for sensitive routes.
    - Setup placeholder logic for Redis Caching on heavy READ operations.
    - Setup placeholder for Background Tasks / Celery for async operations (e.g. sending emails).
    
    Return a STRICT JSON object mapping relative file paths to their raw python code content.
    """
    core_files = {}
    prompt_appended = ""
    for attempt in range(3):
        core_res = generate_content_with_retry(
            model_name=get_model("backend"),
            contents=core_prompt + prompt_appended,
            config=SimpleNamespace(response_mime_type="application/json", temperature=0.2)
        )
        core_files = extract_files_from_dict(json.loads(clean_json_response(core_res.text)))
        
        from agents.reviewer_agent import review_code
        review = review_code(core_files, blueprint, "Core Files (database, models, schemas, config)", requirements)
        if review.get("approved"):
            print("Core files approved by Reviewer!")
            break
        else:
            print(f"Reviewer rejected core files. Retrying... Feedback: {review.get('feedback')}")
            prompt_appended += f"\n\nPREVIOUS ATTEMPT REJECTED. FIX THESE ISSUES:\n{review.get('feedback')}\n"
    
    for filename, code in core_files.items():
        write_safe(filename, code)
        
    schemas_content = ""
    try:
        schemas_content = (backend_path / "schemas.py").read_text(encoding="utf-8")
    except Exception:
        pass
        
    # 2. Generate Repositories
    repos = blueprint.get("backend_repositories", [])
    if not repos:
        repos = [{"name": "BaseRepository", "description": "Generic CRUD ops"}]
        
    repo_prompt = f"""
    Generate the database repository layer.
    Repositories required: {json.dumps(repos)}
    
    Output a STRICT JSON object:
    {{
        "repositories/repo_name.py": "code..."
    }}
    
    Rules:
    - NEVER use relative imports. Always use absolute imports.
    - IMPORTANT: Models are defined in a single file 'models.py', NOT a package. You MUST import them like: 'from models import User, Book'. Do NOT use 'from models.book import Book'.
    - IMPORTANT: 'database.py' is a single file. Import like: 'from database import get_db'.
    """
    repo_res = generate_content_with_retry(
        model_name=get_model("backend"),
        contents=repo_prompt,
        config=SimpleNamespace(response_mime_type="application/json", temperature=0.2)
    )
    repo_files = extract_files_from_dict(json.loads(clean_json_response(repo_res.text)))
    for filename, code in repo_files.items():
        write_safe(filename, code)

    # 3. Generate Services
    services = blueprint.get("backend_services", [])
    if not services:
        services = [{"name": "BaseService", "description": "Generic business logic"}]
        
    available_repos = list(repo_files.keys())
    endpoints = blueprint.get("api_endpoints", [])
    service_prompt = f"""
    Generate the FULL business logic service layer.
    Services required: {json.dumps(services)}
    API Endpoints that will use these services: {json.dumps(endpoints)}
    AVAILABLE REPOSITORIES (ONLY import from these. DO NOT invent new repository files!): {available_repos}
    
    Output a STRICT JSON object:
    {{
        "services/service_name.py": "code..."
    }}
    
    Rules:
    - NEVER use relative imports. Always use absolute imports.
    - IMPORTANT: Repositories are located in the 'repositories' package. Ensure the import matches the exact filename you expect (e.g., 'from repositories.user_repository import UserRepository'). If a matching repository is not in AVAILABLE REPOSITORIES, use a generic one or inline the database calls.
    """
    svc_files = {}
    svc_prompt_appended = ""
    for attempt in range(3):
        svc_res = generate_content_with_retry(
            model_name=get_model("backend"),
            contents=service_prompt + svc_prompt_appended,
            config=SimpleNamespace(response_mime_type="application/json", temperature=0.2)
        )
        svc_files = extract_files_from_dict(json.loads(clean_json_response(svc_res.text)))
        
        from agents.reviewer_agent import review_code
        review = review_code(svc_files, blueprint, "Backend Services", requirements)
        if review.get("approved"):
            print("Services approved by Reviewer!")
            break
        else:
            print(f"Reviewer rejected services. Retrying... Feedback: {review.get('feedback')}")
            svc_prompt_appended += f"\n\nPREVIOUS ATTEMPT REJECTED. FIX THESE ISSUES:\n{review.get('feedback')}\n"

    for filename, code in svc_files.items():
        write_safe(filename, code)
        
    # 4. Generate API Routers Iteratively based on Endpoints
    api_path = backend_path / "api"
    endpoints = blueprint.get("api_endpoints", [])
    routers = {}
    for ep in endpoints:
        route = ep["route"]
        parts = [p for p in route.split("/") if p]
        if len(parts) >= 2 and parts[0] == "api":
            resource = parts[1].replace("-", "_")
            if resource not in routers:
                routers[resource] = []
            routers[resource].append(ep)
            
    actual_router_modules = {}
    available_services = list(svc_files.keys())
    for resource, eps in routers.items():
        router_prompt = f"""
        Generate a FastAPI APIRouter file for '{resource}'.
        Endpoints: {json.dumps(eps)}
        AVAILABLE SCHEMAS: {schemas_content}
        AVAILABLE SERVICES (ONLY import from these. DO NOT invent new service files!): {available_services}
        
        Rules:
        - import APIRouter, Depends, HTTPException from fastapi
        - Use the provided services layer to execute business logic instead of putting it in the router. If a matching service is not in AVAILABLE SERVICES, you must inline the logic in the router or use generic CRUD logic.
        - NEVER use relative imports. Always use absolute imports (e.g. 'from services.auth_service import AuthService').
        - CRITICAL: The router will be mounted at `/api/{resource}` in app.py. Therefore, you MUST write your route paths relative to this prefix! For example, if the endpoint is `/api/{resource}/status`, write `@router.get("/status")`. If the endpoint is exactly `/api/{resource}`, write `@router.get("")` or `@router.get("/")`. Do NOT include `/api/{resource}` in your @router decorator!
        - CRITICAL: You MUST implement EVERY SINGLE endpoint listed in the 'Endpoints' array. Do NOT skip any endpoint. Implement them fully.
        - CRITICAL: Do NOT invent endpoints that are not in the 'Endpoints' array.
        - Ensure your APIRouter instance is named exactly `router`.
        
        Output JSON (CRITICAL: MUST BE EXACTLY A DICT OF FILE PATHS MAPPED TO SOURCE CODE STRINGS. NO OTHER KEYS, NO LISTS):
        {{
            "api/v1/endpoints/{resource}.py": "code string here"
        }}
        """
        router_files = {}
        r_prompt_appended = ""
        for attempt in range(3):
            router_res = generate_content_with_retry(
                model_name=get_model("backend"),
                contents=router_prompt + r_prompt_appended,
                config=SimpleNamespace(response_mime_type="application/json", temperature=0.2)
            )
            router_files = json.loads(clean_json_response(router_res.text))
            
            from agents.reviewer_agent import review_code
            review = review_code(router_files, blueprint, f"API Router for {resource}", requirements)
            if review.get("approved"):
                print(f"Router {resource} approved by Reviewer!")
                break
            else:
                print(f"Reviewer rejected router {resource}. Retrying... Feedback: {review.get('feedback')}")
                r_prompt_appended += f"\n\nPREVIOUS ATTEMPT REJECTED. FIX THESE ISSUES:\n{review.get('feedback')}\n"
                
        for filename, code in router_files.items():
            if not isinstance(code, str):
                code = json.dumps(code, indent=2)
            write_safe(filename, code)
            if filename.endswith(".py") and "__init__" not in filename:
                clean_name = filename[8:] if filename.startswith("backend/") else filename
                clean_name = clean_name[1:] if clean_name.startswith("/") else clean_name
                module_path = clean_name.replace(".py", "").replace("/", ".")
                # Append instead of overwriting
                if resource not in actual_router_modules:
                    actual_router_modules[resource] = []
                # Don't add if it's the main router itself to avoid circular imports
                if not module_path.endswith("router"):
                    actual_router_modules[resource].append(module_path)
            
    # 4.5. Generate Universal Generic CRUD Router
    generic_crud_content = """from fastapi import APIRouter, Request, HTTPException
import uuid

router = APIRouter()
memory_db = {}

@router.api_route("/{resource}", methods=["GET", "POST", "PUT", "DELETE"])
async def generic_crud_root(resource: str, request: Request):
    return await handle_generic_request(resource, request)

@router.api_route("/{resource}/{item_id}", methods=["GET", "POST", "PUT", "DELETE"])
async def generic_crud_item(resource: str, item_id: str, request: Request):
    return await handle_generic_request(resource, request, item_id)

async def handle_generic_request(resource: str, request: Request, item_id: str = None):
    if resource not in memory_db:
        memory_db[resource] = []
    method = request.method
    if method == "GET":
        if item_id:
            for item in memory_db[resource]:
                if str(item.get("id")) == item_id:
                    return item
            raise HTTPException(status_code=404, detail="Item not found")
        return memory_db[resource]
    if method == "POST":
        try: body = await request.json()
        except: body = {}
        body["id"] = str(uuid.uuid4())
        body["status"] = body.get("status", "Pending")
        memory_db[resource].append(body)
        return body
    if method == "PUT":
        try: body = await request.json()
        except: body = {}
        for idx, item in enumerate(memory_db[resource]):
            if str(item.get("id")) == item_id:
                memory_db[resource][idx].update(body)
                return memory_db[resource][idx]
        raise HTTPException(status_code=404, detail="Item not found")
    if method == "DELETE":
        for idx, item in enumerate(memory_db[resource]):
            if str(item.get("id")) == item_id:
                return memory_db[resource].pop(idx)
        raise HTTPException(status_code=404, detail="Item not found")
    return {"detail": "Method not allowed"}
"""
    write_safe("backend/api/v1/endpoints/generic_crud.py", generic_crud_content)
            
    # 5. Generate app.py
    router_imports = []
    include_routers = []
    # If the AI generated a unified router.py for the resource, use that.
    # Otherwise, we would include each endpoint module individually.
    for resource, modules in actual_router_modules.items():
        if not modules: continue
        module_path = modules[0]
        router_imports.append(f"from {module_path} import router as {resource}_router")
        include_routers.append(f"app.include_router({resource}_router, prefix=\"/api/{resource}\")")
        
    router_imports.append("from api.v1.endpoints.generic_crud import router as generic_router")
    include_routers.append("app.include_router(generic_router, prefix=\"/api\", tags=['generic'])")
        
    app_py_content = f"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models
import time
import logging
{chr(10).join(router_imports)}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Generated API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"{{request.method}} {{request.url.path}} completed in {{process_time:.4f}}s")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {{exc}}")
    return JSONResponse(status_code=500, content={{"detail": "Internal Server Error"}})

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized.")

{chr(10).join(include_routers)}

@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")

app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
"""
    (backend_path / "app.py").write_text(app_py_content, encoding="utf-8")
    print("Generated app.py")
    
    return {"status": "backend_generated"}