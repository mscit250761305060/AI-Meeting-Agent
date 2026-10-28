import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api import meeting_router, project_router, ws_router, auth_router
from app.database.database import engine, Base, get_db
from app.services.auth_service import get_optional_user

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run safe schema migrations
    if engine is not None:
        try:
            from app.database.database import migrate_db_schema
            migrate_db_schema()
        except Exception as e:
            logger.warning(f"Could not auto-migrate database tables: {e}")
    yield
    # Shutdown: Clean shutdown lifecycle
    logger.info("Shutting down AI Meeting Agent backend. Cleaning up background processes...")
    try:
        from app.services import meeting_state
        meeting_state.end_meeting()
    except Exception:
        pass
    try:
        from agents.project_runner_agent import kill_process_on_port
        kill_process_on_port(8001)
    except Exception:
        pass

app = FastAPI(
    title="AI Meeting Agent Main App",
    description="Real-time meeting capture, requirements analysis, and live project synthesis backend.",
    version="2.0.0",
    lifespan=lifespan
)

# Mount static assets if static folder exists
static_dir = Path("app/static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Modular Routers
app.include_router(auth_router)
app.include_router(meeting_router)
app.include_router(project_router)
app.include_router(ws_router)

# Health endpoint (used by start.py process check)
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "backend_server": "AI Meeting Agent Backend",
        "version": "2.0.0"
    }
# Dashboard UI Route (Requires Authentication, redirects logged-out users to /login)
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_ui(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    template_path = Path("app/templates/dashboard.html")
    if template_path.exists():
        html_content = template_path.read_text(encoding="utf-8")
    else:
        html_content = "<h1>Dashboard template not found in app/templates/dashboard.html</h1>"
    return HTMLResponse(content=html_content)

# Login Page Route (Redirects already logged-in users to / unless explicitly registering)
@app.get("/login", response_class=HTMLResponse)
def get_login(request: Request, db: Session = Depends(get_db)):
    if request.query_params.get("registered") not in ("1", "true"):
        user = get_optional_user(request, db)
        if user:
            return RedirectResponse(url="/", status_code=303)

    template_path = Path("app/templates/login.html")
    if template_path.exists():
        html_content = template_path.read_text(encoding="utf-8")
    else:
        html_content = "<h1>Login template not found in app/templates/login.html</h1>"
    return HTMLResponse(content=html_content)

# Register Page Route (Redirects already logged-in users to /)
@app.get("/register", response_class=HTMLResponse)
def get_register(request: Request, db: Session = Depends(get_db)):
    user = get_optional_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=303)

    template_path = Path("app/templates/register.html")
    if template_path.exists():
        html_content = template_path.read_text(encoding="utf-8")
    else:
        html_content = "<h1>Register template not found in app/templates/register.html</h1>"
    return HTMLResponse(content=html_content)

# Public Landing Page Route
@app.get("/landing", response_class=HTMLResponse)
def get_landing():
    template_path = Path("app/templates/landing.html")
    if template_path.exists():
        html_content = template_path.read_text(encoding="utf-8")
    else:
        html_content = "<h1>Landing template not found in app/templates/landing.html</h1>"
    return HTMLResponse(content=html_content)

# Global Logout Route
@app.get("/logout")
def app_logout(response: Response):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="access_token", path="/")
    return resp