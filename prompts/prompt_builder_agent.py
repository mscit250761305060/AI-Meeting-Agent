def build_backend_prompt(requirements):
    import json
    project_title = requirements.get("project_title") or requirements.get("project_name") or "AI Generated Project"
    features = requirements.get("features", [])
    pages = requirements.get("pages", [])
    user_roles = requirements.get("user_roles", ["Admin", "User"])

    prompt = f"""
You are a Senior Python Backend Architect and FastAPI expert.

Generate a complete, fully functional, production-ready, multi-file backend using FastAPI, SQLite, and SQLAlchemy for the project '{project_title}'.

Project Requirements:
{json.dumps(requirements, indent=4)}

You MUST output ONLY a valid JSON object with exactly these 5 keys. Each value is the complete Python source code for that file:

{{
    "database.py": "...",
    "models.py": "...",
    "schemas.py": "...",
    "crud.py": "...",
    "app.py": "..."
}}

=== STRICT RULES FOR EACH FILE ===

--- database.py ---
- Use: SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/project_db" (or load from env)
- Create engine with: create_engine(SQLALCHEMY_DATABASE_URL)
- Define SessionLocal and Base
- Include a get_db() dependency function

--- models.py ---
- Import Base with: from database import Base
- Define one SQLAlchemy ORM class per major entity (e.g. User, Room, Booking, Guest, etc.) matching the project: {project_title}
- Each model MUST have: id = Column(Integer, primary_key=True, index=True)
- Use appropriate column types: String, Integer, Float, Boolean, DateTime, Text
- Include __tablename__ for every model
- CRITICAL: Add __table_args__ = {{'extend_existing': True}} to EVERY model class to prevent MetaData collision errors.
- Add ForeignKey relationships where entities are related
- Do NOT use relative imports

--- schemas.py ---
- Import from pydantic: BaseModel
- Create Base and Create schemas for each model, AND a standard response schema named EXACTLY `[ModelName]` (e.g., `class User(UserBase): id: int`) to be used as the default response model.
- Include Login schema: class LoginRequest(BaseModel): username: str; password: str
- Include Register schema: class RegisterRequest(BaseModel): username: str; email: str; password: str; role: str
- Include Token schema: class Token(BaseModel): access_token: str; token_type: str; role: str; user_id: int

--- crud.py ---
- Import models and database with ABSOLUTE imports: import models; from database import SessionLocal
- Implement full CRUD functions for each entity: get_all, get_by_id, create, update, delete
- REQUIRED: implement a seed_data(db) function that inserts 10-15 realistic demo records for EVERY table if empty
  * The seed data must match the project theme '{project_title}'
  * Include one user per role for: {', '.join(user_roles)} with username=role_name.lower() and password="password123"
  * Include realistic data for all other tables (names, dates, statuses, prices, etc.)
- CRITICAL: For the User model, use EXACTLY `password = Column(String)`. DO NOT use `hashed_password`. DO NOT use passlib or password hashing for this simple demo, store the password as plain text.
- CRITICAL: You MUST include the `seed_data(db)` function. Do not skip it.

--- app.py ---
- Import with ABSOLUTE imports: from database import engine, get_db, Base; import models; import schemas; import crud
- Add: from fastapi import FastAPI, Depends, HTTPException, status
- Add: from fastapi.staticfiles import StaticFiles
- Add: from fastapi.responses import FileResponse
- Add: from sqlalchemy.orm import Session
- On startup, call: Base.metadata.create_all(bind=engine) then seed_data(db)
- Implement these REQUIRED routes:
  * POST /api/auth/register — accepts RegisterRequest, creates user in User table, returns Token with access_token="demo-token", role, user_id
  * POST /api/auth/login — accepts LoginRequest, validates username+password against User table, returns Token with access_token="demo-token", role, user_id
  * GET /api/dashboard-stats — returns a JSON dict with key counts for all tables (e.g. total_rooms, total_bookings, etc.)
  * Full CRUD routes for EVERY entity under /api/[entity-name-plural] (GET all, GET by id, POST, PUT, DELETE)
- The root route GET / returns FileResponse("../frontend/index.html")
- The static mount MUST be the VERY LAST LINE: app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
- Do NOT use relative imports anywhere

=== ADDITIONAL RULES ===
1. Output ONLY the JSON object. Do NOT wrap it in markdown code blocks. Do NOT add any text before or after the JSON.
2. ALL Python imports between files MUST be ABSOLUTE. NEVER use relative imports (no `from .database import ...`, no `from . import ...`).
3. Every file must be complete, functional, and production-ready. No placeholders, no TODO comments, no `pass` statements.
4. Make sure all column names in CRUD operations match the exact column names in models.py.
5. Handle all exceptions with proper HTTP status codes and error messages.
"""
    return prompt