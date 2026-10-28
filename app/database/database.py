from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = os.getenv("AGENT_DATABASE_URL", "sqlite:///./ai_meeting_agent.db")

connect_args = {}
if "sqlite" in SQLALCHEMY_DATABASE_URL.lower():
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.error(f"Failed to initialize database engine for {SQLALCHEMY_DATABASE_URL}: {e}")
    engine = None
    SessionLocal = None

Base = declarative_base()

def get_db():
    if not SessionLocal:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_db_schema(target_engine=None):
    """
    Safely migrates database schema preserving all existing tables and data.
    Adds missing columns to tables without destroying or resetting anything.
    """
    if target_engine is None:
        target_engine = engine

    if target_engine is None:
        logger.warning("Database engine is not initialized. Skipping schema migration.")
        return

    try:
        # 1. Ensure all models are registered on Base
        import app.models.models  # noqa: F401
        Base.metadata.create_all(bind=target_engine)

        # 2. Inspect existing columns and add missing ones
        with target_engine.begin() as conn:
            is_sqlite = "sqlite" in str(target_engine.url).lower()

            if is_sqlite:
                # Inspect users table columns
                user_cols_res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
                existing_user_cols = {col[1] for col in user_cols_res}

                new_user_cols = [
                    ("email", "VARCHAR(255)"),
                    ("full_name", "VARCHAR(255)"),
                    ("google_connected", "BOOLEAN DEFAULT 0"),
                    ("google_sub", "VARCHAR(255)"),
                    ("google_email", "VARCHAR(255)"),
                    ("google_access_token", "TEXT"),
                    ("google_refresh_token", "TEXT"),
                    ("google_token_expiry", "DATETIME"),
                ]

                for col_name, col_type in new_user_cols:
                    if col_name not in existing_user_cols:
                        logger.info(f"Adding missing column users.{col_name}...")
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))

                # Inspect sessions table
                session_cols_res = conn.execute(text("PRAGMA table_info(sessions)")).fetchall()
                existing_session_cols = {col[1] for col in session_cols_res}
                if "user_id" not in existing_session_cols:
                    logger.info("Adding missing column sessions.user_id...")
                    conn.execute(text("ALTER TABLE sessions ADD COLUMN user_id VARCHAR(36)"))

                # Inspect summaries table
                summary_cols_res = conn.execute(text("PRAGMA table_info(summaries)")).fetchall()
                existing_summary_cols = {col[1] for col in summary_cols_res}
                if "key_points" not in existing_summary_cols:
                    logger.info("Adding missing column summaries.key_points...")
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN key_points JSON"))
            else:
                # PostgreSQL / MySQL safe column additions
                postgres_user_cols = [
                    ("email", "VARCHAR(255)"),
                    ("full_name", "VARCHAR(255)"),
                    ("google_connected", "BOOLEAN DEFAULT FALSE"),
                    ("google_sub", "VARCHAR(255)"),
                    ("google_email", "VARCHAR(255)"),
                    ("google_access_token", "TEXT"),
                    ("google_refresh_token", "TEXT"),
                    ("google_token_expiry", "TIMESTAMP WITH TIME ZONE"),
                ]
                for col_name, col_type in postgres_user_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    except Exception:
                        pass
                try:
                    conn.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)"))
                except Exception:
                    pass
                try:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN IF NOT EXISTS key_points JSONB"))
                except Exception:
                    pass
        logger.info("Database schema safe migration completed successfully.")
    except Exception as e:
        logger.exception(f"Error during database safe schema migration: {e}")
