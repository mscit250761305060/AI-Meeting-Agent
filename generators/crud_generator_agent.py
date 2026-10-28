from pathlib import Path
import re
from textwrap import dedent


def to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def pluralize(name: str) -> str:
    if name.endswith("y") and len(name) > 1 and name[-2] not in "aeiou":
        return name[:-1] + "ies"
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    return name + "s"


def extract_model_names(models_source: str) -> list[str]:
    return re.findall(r"^class\s+(\w+)\(Base\):", models_source, flags=re.MULTILINE)


def build_common_module() -> str:
    return dedent(
        """
        from sqlalchemy.inspection import inspect


        def serialize_model(obj):
            if obj is None:
                return None
            mapper = inspect(obj).mapper
            return {column.key: getattr(obj, column.key) for column in mapper.columns}
        """
    ).lstrip()


def build_resource_router(model_name: str) -> str:
    resource_name = pluralize(to_snake(model_name))
    return dedent(
        f"""
        from fastapi import APIRouter, Depends, HTTPException, Request, status
        from sqlalchemy.orm import Session
        from sqlalchemy.exc import IntegrityError

        import crud
        import models
        from database import get_db
        from .common import serialize_model


        router = APIRouter(prefix="/api/{resource_name}", tags=["{resource_name}"])
        MODEL = models.{model_name}


        @router.get("")
        def list_items(db: Session = Depends(get_db)):
            return [serialize_model(item) for item in crud.get_all(db, MODEL)]


        @router.get("/{{item_id}}")
        def read_item(item_id: int, db: Session = Depends(get_db)):
            item = crud.get_by_id(db, MODEL, item_id)
            if not item:
                raise HTTPException(status_code=404, detail="{model_name} not found")
            return serialize_model(item)


        @router.post("", status_code=status.HTTP_201_CREATED)
        async def create_item(request: Request, db: Session = Depends(get_db)):
            payload = await request.json()
            try:
                item = crud.create(db, MODEL, payload)
                return serialize_model(item)
            except IntegrityError as e:
                db.rollback()
                raise HTTPException(status_code=400, detail="Database integrity error: likely a duplicate or missing required field.")


        @router.put("/{{item_id}}")
        async def update_item(item_id: int, request: Request, db: Session = Depends(get_db)):
            payload = await request.json()
            try:
                item = crud.update(db, MODEL, item_id, payload)
                if not item:
                    raise HTTPException(status_code=404, detail="{model_name} not found")
                return serialize_model(item)
            except IntegrityError as e:
                db.rollback()
                raise HTTPException(status_code=400, detail="Database integrity error.")


        @router.delete("/{{item_id}}")
        def delete_item(item_id: int, db: Session = Depends(get_db)):
            item = crud.get_by_id(db, MODEL, item_id)
            if not item:
                raise HTTPException(status_code=404, detail="{model_name} not found")
            crud.delete(db, MODEL, item_id)
            return {{"success": True}}
        """
    ).lstrip()


def build_auth_router() -> str:
    return dedent(
        """
        from fastapi import APIRouter, Depends, HTTPException
        from sqlalchemy.orm import Session
        from passlib.context import CryptContext
        import jwt
        from datetime import datetime, timedelta

        import models
        import schemas
        from database import get_db

        SECRET_KEY = "supersecretkey"
        ALGORITHM = "HS256"

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        def verify_password(plain_password, hashed_password):
            return pwd_context.verify(plain_password, hashed_password)

        def get_password_hash(password):
            return pwd_context.hash(password)

        def create_access_token(data: dict, expires_delta: timedelta | None = None):
            to_encode = data.copy()
            expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
            to_encode.update({"exp": expire})
            return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

        router = APIRouter(prefix="/api/auth", tags=["auth"])


        @router.post("/register", response_model=schemas.Token)
        def register(request: schemas.RegisterRequest, db: Session = Depends(get_db)):
            existing = db.query(models.User).filter(models.User.email == request.email).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")
            
            new_user = models.User(
                email=request.email,
                hashed_password=get_password_hash(request.password),
                role=getattr(request, "role", "user")
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            token = create_access_token(data={"sub": str(new_user.id), "role": new_user.role})
            return {
                "access_token": token,
                "token_type": "bearer",
                "role": new_user.role,
                "user_id": new_user.id,
            }


        @router.post("/login", response_model=schemas.Token)
        def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
            user = db.query(models.User).filter(models.User.email == getattr(request, "email", getattr(request, "username", ""))).first()
            if not user or not verify_password(request.password, user.hashed_password):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            token = create_access_token(data={"sub": str(user.id), "role": user.role})
            return {
                "access_token": token,
                "token_type": "bearer",
                "role": user.role,
                "user_id": user.id,
            }
"""
    ).lstrip()


def build_dashboard_router(model_names: list[str]) -> str:
    counts = "\n".join(
        [
            f'        "total_{pluralize(to_snake(model_name))}": db.query(models.{model_name}).count(),'
            for model_name in model_names
        ]
    )
    return dedent(
        f"""
        from fastapi import APIRouter, Depends
        from sqlalchemy.orm import Session

        import models
        from database import get_db


        router = APIRouter(tags=["dashboard"])


        @router.get("/api/dashboard-stats")
        def get_dashboard_stats(db: Session = Depends(get_db)):
            return {{
{counts}
            }}
        """
    ).lstrip()


def build_app_module(model_names: list[str]) -> str:
    router_imports = ["from api.auth import router as auth_router", "from api.dashboard import router as dashboard_router"]
    include_lines = ["app.include_router(auth_router)", "app.include_router(dashboard_router)"]

    for model_name in model_names:
        module_name = pluralize(to_snake(model_name))
        router_imports.append(f"from api.{module_name} import router as {module_name}_router")
        include_lines.append(f"app.include_router({module_name}_router)")

    lines = [
        "from fastapi import FastAPI",
        "from fastapi.responses import FileResponse",
        "from fastapi.staticfiles import StaticFiles",
        "",
        "from database import Base, engine, get_db",
        "import crud",
        "import models",
    ]
    lines.extend(router_imports)
    lines.extend([
        "",
        "app = FastAPI()",
        "",
        "",
        "@app.on_event(\"startup\")",
        "def startup():",
        "    Base.metadata.create_all(bind=engine)",
        "    db = next(get_db())",
        "    crud.seed_data(db)",
        "",
    ])
    lines.extend(include_lines)
    lines.extend([
        "",
        "",
        "@app.get(\"/\")",
        "async def root():",
        "    return FileResponse(\"../frontend/index.html\")",
        "",
        "",
        "app.mount(\"/\", StaticFiles(directory=\"../frontend\", html=True), name=\"static\")",
    ])
    return "\n".join(lines) + "\n"


def generate_crud_app(requirements, project_path):
    project_path = Path(project_path)
    backend_path = project_path / "backend"
    backend_path.mkdir(parents=True, exist_ok=True)

    models_path = backend_path / "models.py"
    if not models_path.exists():
        raise FileNotFoundError(f"models.py not found at {models_path}")

    model_names = extract_model_names(models_path.read_text(encoding="utf-8"))
    if not model_names:
        raise ValueError("No SQLAlchemy model classes were found in backend/models.py")

    api_path = backend_path / "api"
    api_path.mkdir(exist_ok=True)
    (api_path / "__init__.py").write_text("", encoding="utf-8")
    (api_path / "common.py").write_text(build_common_module(), encoding="utf-8")
    (api_path / "auth.py").write_text(build_auth_router(), encoding="utf-8")
    (api_path / "dashboard.py").write_text(build_dashboard_router(model_names), encoding="utf-8")

    for model_name in model_names:
        resource_name = pluralize(to_snake(model_name))
        (api_path / f"{resource_name}.py").write_text(build_resource_router(model_name), encoding="utf-8")
        print(f"Generated CRUD route file: backend/api/{resource_name}.py")

    (backend_path / "app.py").write_text(build_app_module(model_names), encoding="utf-8")
    print("Generated CRUD route file: backend/api/auth.py")
    print("Generated CRUD route file: backend/api/dashboard.py")
    print("Generated CRUD application entrypoint: backend/app.py")

    return {
        "status": "crud_ready",
        "models": model_names,
        "routes": [pluralize(to_snake(model_name)) for model_name in model_names],
    }