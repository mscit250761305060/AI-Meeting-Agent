import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app as fastapi_app

import os
from pathlib import Path

# Dedicated file-backed test database ensures multi-threaded threadpool consistency
TEST_DB_FILE = Path("test_runner.db")
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE.resolve()}"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# Ensure all models are registered on Base and tables created on test engine
import app.models.models  # noqa: F401
Base.metadata.create_all(bind=test_engine)
from app.database.database import migrate_db_schema
migrate_db_schema(target_engine=test_engine)


@pytest.fixture(autouse=True)
def db_session_fixture():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield
    fastapi_app.dependency_overrides.clear()
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            try:
                conn.execute(table.delete())
            except Exception:
                pass
