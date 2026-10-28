"""
app/services/generator/project_synthesizer.py

Deterministic project code generator for AI Meeting Agent.
Synthesizes FastAPI backend, SQLAlchemy database models, REST APIs, and modern HTML pages
based on a validated ProjectSpecification without requiring any AI provider.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple, List
from app.services.generator.specification import ProjectSpecification, FieldSpec


class ProjectSynthesizer:
    def __init__(self, base_dir: Path = Path("generated_projects")):
        self.base_dir = base_dir
        self.base_dir.mkdir(exist_ok=True)

    def determine_output_dir(self, spec: ProjectSpecification) -> Path:
        """
        Determines a safe directory inside generated_projects/.
        Guarantees that existing projects are preserved and never accidentally overwritten.
        """
        candidate_name = f"{spec.project_slug}_app"
        candidate_path = self.base_dir / candidate_name

        if not candidate_path.exists():
            candidate_path.mkdir(parents=True, exist_ok=True)
            return candidate_path

        # If directory exists, find next available version suffix
        version = 2
        while True:
            versioned_name = f"{spec.project_slug}_app_v{version}"
            versioned_path = self.base_dir / versioned_name
            if not versioned_path.exists():
                versioned_path.mkdir(parents=True, exist_ok=True)
                return versioned_path
            version += 1

    def synthesize(self, spec: ProjectSpecification) -> Tuple[Path, Dict[str, Any]]:
        project_dir = self.determine_output_dir(spec)
        files_created = []

        # 1. database.py
        db_code = self._generate_database_py()
        (project_dir / "database.py").write_text(db_code, encoding="utf-8")
        files_created.append("database.py")

        # 2. models.py
        models_code = self._generate_models_py(spec)
        (project_dir / "models.py").write_text(models_code, encoding="utf-8")
        files_created.append("models.py")

        # 3. schemas.py
        schemas_code = self._generate_schemas_py(spec)
        (project_dir / "schemas.py").write_text(schemas_code, encoding="utf-8")
        files_created.append("schemas.py")

        # 4. app.py
        app_code = self._generate_app_py(spec)
        (project_dir / "app.py").write_text(app_code, encoding="utf-8")
        files_created.append("app.py")

        # 5. Dynamic HTML Pages
        nav_html = self._build_navigation_bar(spec)
        css_styles = self._build_shared_styles()

        # index.html (Portal landing)
        index_html = self._generate_index_html(spec, nav_html, css_styles)
        (project_dir / "index.html").write_text(index_html, encoding="utf-8")
        files_created.append("index.html")

        # Individual Pages
        for page in spec.pages:
            filename = f"{page.slug}.html"
            page_content = self._generate_page_html(page, spec, nav_html, css_styles)
            (project_dir / filename).write_text(page_content, encoding="utf-8")
            files_created.append(filename)

        # 6. project_config.json
        config_data = spec.model_dump()
        (project_dir / "project_config.json").write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        files_created.append("project_config.json")

        # 7. requirements.txt
        reqs_content = "fastapi>=0.100.0\nuvicorn>=0.20.0\nsqlalchemy>=2.0.0\npydantic>=2.0.0\n"
        (project_dir / "requirements.txt").write_text(reqs_content, encoding="utf-8")
        files_created.append("requirements.txt")

        # 8. README.md
        readme_content = self._generate_readme(spec)
        (project_dir / "README.md").write_text(readme_content, encoding="utf-8")
        files_created.append("README.md")

        return project_dir, {
            "project_name": spec.project_name,
            "project_path": str(project_dir),
            "files_created": files_created,
            "entity": spec.entity_name,
            "pages": [p.slug for p in spec.pages],
            "endpoints": [e.path for e in spec.api_endpoints]
        }

    def _generate_database_py(self) -> str:
        return """from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./app_data.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

    def _generate_models_py(self, spec: ProjectSpecification) -> str:
        model_name = spec.entity_name
        table_name = spec.entity_plural.lower()

        column_lines = [
            '    id = Column(Integer, primary_key=True, index=True)',
        ]

        for f in spec.fields:
            col_type = "String(255)"
            if f.type == "integer":
                col_type = "Integer"
            elif f.type == "float":
                col_type = "Float"
            elif f.type == "boolean":
                col_type = "Boolean"
            elif f.type == "text":
                col_type = "Text"

            nullable = "False" if f.required else "True"
            default_part = ""
            if f.default is not None:
                if isinstance(f.default, str):
                    default_part = f', default="{f.default}"'
                else:
                    default_part = f', default={f.default}'

            column_lines.append(f'    {f.name} = Column({col_type}, nullable={nullable}{default_part})')

        column_lines.append('    created_at = Column(DateTime, default=datetime.utcnow)')

        cols_block = "\n".join(column_lines)

        return f"""from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from database import Base


class {model_name}(Base):
    __tablename__ = "{table_name}"

{cols_block}
"""

    def _generate_schemas_py(self, spec: ProjectSpecification) -> str:
        model_name = spec.entity_name

        create_fields = []
        for f in spec.fields:
            py_type = "str"
            if f.type == "integer":
                py_type = "int"
            elif f.type == "float":
                py_type = "float"
            elif f.type == "boolean":
                py_type = "bool"

            if not f.required:
                create_fields.append(f"    {f.name}: Optional[{py_type}] = None")
            elif f.default is not None:
                if isinstance(f.default, str):
                    create_fields.append(f'    {f.name}: {py_type} = "{f.default}"')
                else:
                    create_fields.append(f'    {f.name}: {py_type} = {f.default}')
            else:
                create_fields.append(f"    {f.name}: {py_type}")

        create_block = "\n".join(create_fields)

        return f"""from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class {model_name}Base(BaseModel):
{create_block}


class {model_name}Create({model_name}Base):
    pass


class {model_name}Update(BaseModel):
{chr(10).join(f"    {f.name}: Optional[Any] = None" for f in spec.fields).replace("Any", "str")}


class {model_name}Response({model_name}Base):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
"""

    def _generate_app_py(self, spec: ProjectSpecification) -> str:
        model_name = spec.entity_name
        plural = spec.entity_plural.lower()

        # Build seed data
        seed_items = self._build_seed_data(spec)
        seed_code = f"SEED_DATA = {json.dumps(seed_items, indent=4)}"

        page_routes = []
        for page in spec.pages:
            page_routes.append(f"""@app.get("/{page.slug}")
async def serve_{page.slug}():
    return FileResponse("{page.slug}.html")
""")

        page_routes_block = "\n".join(page_routes)

        return f"""from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from database import engine, Base, get_db
import models
import schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="{spec.project_name}",
    description="{spec.purpose}",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

{seed_code}


@app.on_event("startup")
def seed_database():
    db = next(get_db())
    try:
        count = db.query(models.{model_name}).count()
        if count == 0:
            for item in SEED_DATA:
                db_item = models.{model_name}(**item)
                db.add(db_item)
            db.commit()
    except Exception as e:
        print(f"Seed error: {{e}}")
    finally:
        db.close()


@app.get("/")
async def root():
    return FileResponse("index.html")


{page_routes_block}

# ============================================================
# REST API Endpoints
# ============================================================

@app.get("/api/{plural}", response_model=List[schemas.{model_name}Response])
def get_{plural}(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.{model_name}).offset(skip).limit(limit).all()


@app.get("/api/{plural}/{{item_id}}", response_model=schemas.{model_name}Response)
def get_{model_name.lower()}(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.{model_name}).filter(models.{model_name}.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    return item


@app.post("/api/{plural}", response_model=schemas.{model_name}Response, status_code=status.HTTP_201_CREATED)
def create_{model_name.lower()}(item_in: schemas.{model_name}Create, db: Session = Depends(get_db)):
    db_item = models.{model_name}(**item_in.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.put("/api/{plural}/{{item_id}}", response_model=schemas.{model_name}Response)
def update_{model_name.lower()}(item_id: int, item_in: schemas.{model_name}Create, db: Session = Depends(get_db)):
    db_item = db.query(models.{model_name}).filter(models.{model_name}.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    for key, value in item_in.model_dump().items():
        setattr(db_item, key, value)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.delete("/api/{plural}/{{item_id}}")
def delete_{model_name.lower()}(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(models.{model_name}).filter(models.{model_name}.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    db.delete(db_item)
    db.commit()
    return {{"success": True, "message": "{model_name} deleted successfully."}}


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    items = db.query(models.{model_name}).all()
    total = len(items)
    
    # Categorical breakdown if a category or status field exists
    categories = {{}}
    for item in items:
        val = getattr(item, "status", getattr(item, "category", "Default"))
        categories[str(val)] = categories.get(str(val), 0) + 1

    return {{
        "total": total,
        "entity": "{model_name}",
        "distribution": categories,
        "status": "Operational"
    }}


# Static mount (must be last)
app.mount("/", StaticFiles(directory=".", html=True), name="static")
"""

    def _build_seed_data(self, spec: ProjectSpecification) -> List[Dict[str, Any]]:
        entity = spec.entity_name.lower()
        if "task" in entity:
            return [
                {"title": "Initial Project Discovery", "description": "Gather client specifications from kickoff meeting", "status": "Completed", "priority": "High"},
                {"title": "Database Schema Setup", "description": "Configure SQLite and SQLAlchemy models", "status": "In Progress", "priority": "Critical"},
                {"title": "Frontend Component Review", "description": "Validate responsive layouts and dashboard metrics", "status": "Pending", "priority": "Medium"}
            ]
        elif "product" in entity:
            return [
                {"name": "Pro Wireless Headphones", "category": "Electronics", "price": 149.99, "stock": 45, "description": "Noise-cancelling over-ear headphones"},
                {"name": "Ergonomic Office Chair", "category": "Furniture", "price": 289.50, "stock": 18, "description": "Lumbar support executive chair"},
                {"name": "Mechanical Keyboard RGB", "category": "Electronics", "price": 89.00, "stock": 60, "description": "Tactile switch mechanical keyboard"}
            ]
        elif "patient" in entity:
            return [
                {"name": "Eleanor Vance", "age": 34, "gender": "Female", "contact": "+1-555-0192", "diagnosis": "Annual Wellness Check", "status": "Active"},
                {"name": "Marcus Kane", "age": 52, "gender": "Male", "contact": "+1-555-0841", "diagnosis": "Hypertension Monitoring", "status": "Active"},
                {"name": "Sophia Bennett", "age": 28, "gender": "Female", "contact": "+1-555-0319", "diagnosis": "Post-Op Physical Therapy", "status": "Admitted"}
            ]
        elif "customer" in entity:
            return [
                {"name": "Apex Innovations", "email": "contact@apexinno.io", "phone": "+1-555-4421", "company": "Apex Global", "status": "Won"},
                {"name": "Vanguard Media", "email": "leads@vanguardm.com", "phone": "+1-555-8832", "company": "Vanguard", "status": "Proposal"},
                {"name": "Horizon Retail", "email": "procurement@horizon.com", "phone": "+1-555-9923", "company": "Horizon", "status": "Contacted"}
            ]
        elif "booking" in entity:
            return [
                {"guest_name": "Alexander Hayes", "room_type": "Executive Suite", "check_in": "2026-11-01", "check_out": "2026-11-05", "status": "Confirmed"},
                {"guest_name": "Elena Rostova", "room_type": "Deluxe King", "check_in": "2026-11-02", "check_out": "2026-11-04", "status": "Checked In"}
            ]
        elif "employee" in entity:
            return [
                {"name": "Sarah Connor", "email": "s.connor@company.internal", "department": "Engineering", "role": "Senior Architect", "salary": 125000.0},
                {"name": "David Miller", "email": "d.miller@company.internal", "department": "Product", "role": "Product Lead", "salary": 115000.0},
                {"name": "Amira Patel", "email": "a.patel@company.internal", "department": "Design", "role": "UX Specialist", "salary": 95000.0}
            ]
        else:
            return [
                {"name": "Resource Alpha", "category": "Operational", "status": "Active", "description": "Primary operational resource entity"},
                {"name": "Resource Beta", "category": "System", "status": "Active", "description": "Secondary system entity for tracking"}
            ]

    def _build_shared_styles(self) -> str:
        return """
        :root {
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --card-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #06b6d4;
            --success: #10b981;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; }
        header { background: #111827; border-bottom: 1px solid var(--card-border); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 1.25rem; font-weight: 700; color: #fff; text-decoration: none; display: flex; align-items: center; gap: 0.5rem; }
        .logo span { color: var(--accent); }
        nav { display: flex; gap: 1rem; }
        nav a { color: var(--text-muted); text-decoration: none; font-size: 0.95rem; padding: 0.4rem 0.8rem; border-radius: 6px; transition: all 0.2s; }
        nav a:hover, nav a.active { color: #fff; background: var(--card-border); }
        main { flex: 1; padding: 2rem; max-width: 1200px; margin: 0 auto; width: 100%; }
        .card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
        h1, h2, h3 { color: #fff; margin-bottom: 0.75rem; }
        p { color: var(--text-muted); line-height: 1.6; }
        .btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.6rem 1.2rem; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; text-decoration: none; border: none; transition: background 0.2s; }
        .btn-primary { background: var(--primary); color: #fff; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-danger:hover { opacity: 0.9; }
        .btn-outline { background: transparent; border: 1px solid var(--card-border); color: var(--text-main); }
        .btn-outline:hover { background: var(--card-border); }
        .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { text-align: left; padding: 0.85rem 1rem; border-bottom: 1px solid var(--card-border); }
        th { color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
        td { color: var(--text-main); font-size: 0.95rem; }
        tr:hover td { background: rgba(255,255,255,0.02); }
        .form-group { margin-bottom: 1.25rem; }
        label { display: block; margin-bottom: 0.5rem; font-size: 0.9rem; font-weight: 500; color: var(--text-main); }
        input, select, textarea { width: 100%; padding: 0.7rem 1rem; border-radius: 8px; border: 1px solid var(--card-border); background: #0f172a; color: #fff; font-size: 0.95rem; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: var(--primary); ring: 2px var(--primary); }
        .badge { padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; display: inline-block; }
        .badge-success { background: rgba(16,185,129,0.2); color: #34d399; }
        .badge-warning { background: rgba(245,158,11,0.2); color: #fbbf24; }
        .badge-info { background: rgba(6,182,212,0.2); color: #38bdf8; }
        """

    def _build_navigation_bar(self, spec: ProjectSpecification) -> str:
        links = ['<a href="/">Home</a>']
        for page in spec.pages:
            links.append(f'<a href="/{page.slug}">{page.title}</a>')
        return "\n".join(links)

    def _generate_index_html(self, spec: ProjectSpecification, nav_html: str, css: str) -> str:
        feature_lis = "\n".join(f"<li>{f}</li>" for f in spec.features)
        roles_badges = " ".join(f'<span class="badge badge-info">{r}</span>' for r in spec.user_roles)

        page_cards = []
        for p in spec.pages:
            page_cards.append(f"""
            <div class="card" style="margin-bottom: 0;">
                <h3>{p.title}</h3>
                <p style="margin-bottom: 1rem;">{p.description or 'Interactive application view.'}</p>
                <a href="/{p.slug}" class="btn btn-outline" style="width: 100%;">Open Page &rarr;</a>
            </div>
            """)

        pages_grid = "\n".join(page_cards)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{spec.project_name}</title>
    <style>{css}</style>
</head>
<body>
    <header>
        <a href="/" class="logo">🚀 <span>{spec.project_name}</span></a>
        <nav>{nav_html}</nav>
    </header>
    <main>
        <div class="card" style="background: linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%);">
            <h1 style="font-size: 2.2rem; margin-bottom: 0.5rem;">{spec.project_name}</h1>
            <p style="font-size: 1.1rem; max-width: 800px; margin-bottom: 1.5rem;">{spec.purpose}</p>
            <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                <span class="badge badge-success">Backend: {spec.backend_framework}</span>
                <span class="badge badge-info">Database: {spec.database_type}</span>
                <div style="margin-left: auto;">
                    <strong>Supported Roles:</strong> {roles_badges}
                </div>
            </div>
        </div>

        <div class="grid-3" style="margin-bottom: 2rem;">
            {pages_grid}
        </div>

        <div class="card">
            <h2>Key Features</h2>
            <ul style="padding-left: 1.5rem; color: var(--text-muted); line-height: 2;">
                {feature_lis}
            </ul>
        </div>
    </main>
</body>
</html>
"""

    def _generate_page_html(self, page, spec: ProjectSpecification, nav_html: str, css: str) -> str:
        plural = spec.entity_plural.lower()
        model_name = spec.entity_name

        if page.type == "dashboard":
            return self._build_dashboard_page(page, spec, nav_html, css)
        elif page.type == "list":
            return self._build_list_page(page, spec, nav_html, css)
        elif page.type == "form":
            return self._build_form_page(page, spec, nav_html, css)
        else:
            return self._build_generic_page(page, spec, nav_html, css)

    def _build_dashboard_page(self, page, spec: ProjectSpecification, nav_html: str, css: str) -> str:
        plural = spec.entity_plural.lower()
        model_name = spec.entity_name

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.title} — {spec.project_name}</title>
    <style>{css}</style>
</head>
<body>
    <header>
        <a href="/" class="logo">🚀 <span>{spec.project_name}</span></a>
        <nav>{nav_html}</nav>
    </header>
    <main>
        <h1 style="margin-bottom: 1.5rem;">{page.title}</h1>

        <div class="grid-3">
            <div class="card">
                <p>Total {plural.title()}</p>
                <h2 id="totalCount" style="font-size: 2.5rem; color: var(--accent); margin-top: 0.5rem;">0</h2>
            </div>
            <div class="card">
                <p>System Status</p>
                <h2 style="font-size: 2rem; color: var(--success); margin-top: 0.5rem;">Online</h2>
            </div>
            <div class="card">
                <p>Database Engine</p>
                <h2 style="font-size: 2rem; color: #fff; margin-top: 0.5rem;">SQLite 3</h2>
            </div>
        </div>

        <div class="card">
            <h2>Status & Category Distribution</h2>
            <div id="distributionContainer" style="display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem;">
                <p>Loading analytics...</p>
            </div>
        </div>

        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2>Recent {plural.title()}</h2>
                <a href="/{spec.pages[1].slug if len(spec.pages) > 1 else 'list'}" class="btn btn-outline">View All</a>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name/Title</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="recentItems">
                    <tr><td colspan="3">Loading records...</td></tr>
                </tbody>
            </table>
        </div>
    </main>

    <script>
    async function loadStats() {{
        try {{
            const res = await fetch("/api/stats");
            const data = await res.json();
            document.getElementById("totalCount").innerText = data.total;

            const dist = data.distribution || {{}};
            const distContainer = document.getElementById("distributionContainer");
            distContainer.innerHTML = "";
            for (const [key, count] of Object.entries(dist)) {{
                distContainer.innerHTML += `
                    <div style="background: rgba(255,255,255,0.05); padding: 0.75rem 1.25rem; border-radius: 8px; border: 1px solid var(--card-border);">
                        <strong>${{key}}</strong>: ${{count}}
                    </div>
                `;
            }}
        }} catch(e) {{
            console.error(e);
        }}
    }}

    async function loadRecent() {{
        try {{
            const res = await fetch("/api/{plural}?limit=5");
            const items = await res.json();
            const tbody = document.getElementById("recentItems");
            tbody.innerHTML = "";
            if (items.length === 0) {{
                tbody.innerHTML = "<tr><td colspan='3'>No items recorded yet.</td></tr>";
                return;
            }}
            items.forEach(item => {{
                const name = item.title || item.name || item.guest_name || `Item #${{item.id}}`;
                const status = item.status || "Active";
                tbody.innerHTML += `
                    <tr>
                        <td>#${{item.id}}</td>
                        <td>${{name}}</td>
                        <td><span class="badge badge-success">${{status}}</span></td>
                    </tr>
                `;
            }});
        }} catch(e) {{
            console.error(e);
        }}
    }}

    loadStats();
    loadRecent();
    </script>
</body>
</html>
"""

    def _build_list_page(self, page, spec: ProjectSpecification, nav_html: str, css: str) -> str:
        plural = spec.entity_plural.lower()
        model_name = spec.entity_name

        table_headers = ["<th>ID</th>"]
        for f in spec.fields[:4]:
            table_headers.append(f"<th>{f.label}</th>")
        table_headers.append("<th>Actions</th>")

        headers_html = "\n".join(table_headers)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.title} — {spec.project_name}</title>
    <style>{css}</style>
</head>
<body>
    <header>
        <a href="/" class="logo">🚀 <span>{spec.project_name}</span></a>
        <nav>{nav_html}</nav>
    </header>
    <main>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <h1>{page.title}</h1>
            <a href="/{spec.pages[2].slug if len(spec.pages) > 2 else 'form'}" class="btn btn-primary">+ Add New {model_name}</a>
        </div>

        <div class="card">
            <div class="form-group" style="margin-bottom: 1rem;">
                <input type="text" id="searchInput" placeholder="Search {plural} by name or keywords..." onkeyup="filterTable()">
            </div>

            <table>
                <thead>
                    <tr>
                        {headers_html}
                    </tr>
                </thead>
                <tbody id="itemsTable">
                    <tr><td colspan="{len(spec.fields[:4]) + 2}">Loading records...</td></tr>
                </tbody>
            </table>
        </div>
    </main>

    <script>
    let allItems = [];

    async function fetchItems() {{
        try {{
            const res = await fetch("/api/{plural}");
            allItems = await res.json();
            renderTable(allItems);
        }} catch(e) {{
            console.error(e);
        }}
    }}

    function renderTable(items) {{
        const tbody = document.getElementById("itemsTable");
        tbody.innerHTML = "";
        if (items.length === 0) {{
            tbody.innerHTML = "<tr><td colspan='10'>No records found.</td></tr>";
            return;
        }}
        items.forEach(item => {{
            let cols = `<td>#${{item.id}}</td>`;
            const fieldKeys = {json.dumps([f.name for f in spec.fields[:4]])};
            fieldKeys.forEach(k => {{
                cols += `<td>${{item[k] !== undefined && item[k] !== null ? item[k] : '-'}}</td>`;
            }});
            cols += `
                <td>
                    <button class="btn btn-danger" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;" onclick="deleteItem(${{item.id}})">Delete</button>
                </td>
            `;
            tbody.innerHTML += `<tr>${{cols}}</tr>`;
        }});
    }}

    function filterTable() {{
        const q = document.getElementById("searchInput").value.toLowerCase();
        const filtered = allItems.filter(item => JSON.stringify(item).toLowerCase().includes(q));
        renderTable(filtered);
    }}

    async function deleteItem(id) {{
        if (!confirm(`Are you sure you want to delete ${{id}}?`)) return;
        try {{
            const res = await fetch(`/api/{plural}/${{id}}`, {{ method: "DELETE" }});
            if (res.ok) {{
                fetchItems();
            }} else {{
                alert("Failed to delete item.");
            }}
        }} catch(e) {{
            alert("Delete error: " + e);
        }}
    }}

    fetchItems();
    </script>
</body>
</html>
"""

    def _build_form_page(self, page, spec: ProjectSpecification, nav_html: str, css: str) -> str:
        plural = spec.entity_plural.lower()
        model_name = spec.entity_name

        form_fields = []
        for f in spec.fields:
            req_str = "required" if f.required else ""
            if f.options:
                opts = "".join(f'<option value="{opt}">{opt}</option>' for opt in f.options)
                field_html = f"""
                <div class="form-group">
                    <label>{f.label}{" *" if f.required else ""}</label>
                    <select id="{f.name}" name="{f.name}" {req_str}>
                        {opts}
                    </select>
                </div>
                """
            elif f.type == "text":
                field_html = f"""
                <div class="form-group">
                    <label>{f.label}{" *" if f.required else ""}</label>
                    <textarea id="{f.name}" name="{f.name}" rows="3" placeholder="Enter {f.label}" {req_str}></textarea>
                </div>
                """
            elif f.type in ("integer", "float"):
                step_str = 'step="0.01"' if f.type == "float" else 'step="1"'
                field_html = f"""
                <div class="form-group">
                    <label>{f.label}{" *" if f.required else ""}</label>
                    <input type="number" id="{f.name}" name="{f.name}" {step_str} placeholder="Enter {f.label}" {req_str}>
                </div>
                """
            else:
                field_html = f"""
                <div class="form-group">
                    <label>{f.label}{" *" if f.required else ""}</label>
                    <input type="text" id="{f.name}" name="{f.name}" placeholder="Enter {f.label}" {req_str}>
                </div>
                """
            form_fields.append(field_html)

        fields_block = "\n".join(form_fields)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.title} — {spec.project_name}</title>
    <style>{css}</style>
</head>
<body>
    <header>
        <a href="/" class="logo">🚀 <span>{spec.project_name}</span></a>
        <nav>{nav_html}</nav>
    </header>
    <main>
        <div class="card" style="max-width: 650px; margin: 0 auto;">
            <h1>{page.title}</h1>
            <p style="margin-bottom: 1.5rem;">Fill out the form details below to add a new record to the database.</p>

            <form id="recordForm" onsubmit="submitForm(event)">
                {fields_block}
                <div style="display: flex; gap: 1rem; margin-top: 1.5rem;">
                    <button type="submit" class="btn btn-primary" style="flex: 1;">Save {model_name}</button>
                    <a href="/" class="btn btn-outline">Cancel</a>
                </div>
            </form>
        </div>
    </main>

    <script>
    async function submitForm(e) {{
        e.preventDefault();
        const payload = {{}};
        const fieldSpecs = {json.dumps([{"name": f.name, "type": f.type} for f in spec.fields])};

        fieldSpecs.forEach(f => {{
            const el = document.getElementById(f.name);
            if (!el) return;
            let val = el.value;
            if (f.type === "integer") val = parseInt(val, 10) || 0;
            else if (f.type === "float") val = parseFloat(val) || 0.0;
            else if (f.type === "boolean") val = val === "true" || val === true;
            payload[f.name] = val;
        }});

        try {{
            const res = await fetch("/api/{plural}", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify(payload)
            }});

            if (res.ok) {{
                alert("{model_name} added successfully!");
                document.getElementById("recordForm").reset();
                window.location.href = "/{spec.pages[1].slug if len(spec.pages) > 1 else ''}";
            }} else {{
                const err = await res.json();
                alert("Submission failed: " + JSON.stringify(err));
            }}
        }} catch(err) {{
            alert("Network error: " + err);
        }}
    }}
    </script>
</body>
</html>
"""

    def _build_generic_page(self, page, spec: ProjectSpecification, nav_html: str, css: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page.title} — {spec.project_name}</title>
    <style>{css}</style>
</head>
<body>
    <header>
        <a href="/" class="logo">🚀 <span>{spec.project_name}</span></a>
        <nav>{nav_html}</nav>
    </header>
    <main>
        <div class="card">
            <h1>{page.title}</h1>
            <p>{page.description or 'Custom application interface.'}</p>
            <div style="margin-top: 1.5rem;">
                <a href="/" class="btn btn-outline">&larr; Return to Dashboard</a>
            </div>
        </div>
    </main>
</body>
</html>
"""

    def _generate_readme(self, spec: ProjectSpecification) -> str:
        fields_table = "\n".join(f"| `{f.name}` | {f.type} | {'Yes' if f.required else 'No'} | {f.label} |" for f in spec.fields)
        endpoints_table = "\n".join(f"| `{e.method}` | `{e.path}` | {e.description} |" for e in spec.api_endpoints)

        return f"""# {spec.project_name}

{spec.purpose}

## Overview
- **Industry:** {spec.industry}
- **Primary Entity:** `{spec.entity_name}` (`{spec.entity_plural}`)
- **Backend:** {spec.backend_framework}
- **Database:** {spec.database_type} (SQLAlchemy ORM)

## Data Model: `{spec.entity_name}`
| Field | Type | Required | Description |
|---|---|---|---|
{fields_table}

## API Endpoints
| Method | Path | Description |
|---|---|---|
{endpoints_table}

## Running the Application Locally
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Uvicorn preview server
uvicorn app:app --host 127.0.0.1 --port 8001
```
"""
