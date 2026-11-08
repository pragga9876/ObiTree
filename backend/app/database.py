from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import database_url

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


DATABASE_URL = _normalize_database_url(database_url())
IS_POSTGRES = DATABASE_URL.startswith("postgresql")


def _engine_options(url: str) -> dict:
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        return options
    parsed = make_url(url)
    if "sslmode" not in parsed.query and parsed.host not in {
        None,
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        options["connect_args"] = {"sslmode": "require"}
    return options


engine = create_engine(DATABASE_URL, **_engine_options(DATABASE_URL))

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


def ensure_schema():
    """
    Add storage columns introduced after the first deployment. `create_all`
    never alters existing tables, so both SQLite and PostgreSQL need this
    idempotent migration before the API starts serving requests.
    """
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("documents")}
    statements = {
        "storage_backend": "ALTER TABLE documents ADD COLUMN storage_backend VARCHAR DEFAULT 'local'",
        "storage_path": "ALTER TABLE documents ADD COLUMN storage_path VARCHAR",
        "image_url": "ALTER TABLE documents ADD COLUMN image_url VARCHAR",
    }
    with engine.begin() as connection:
        for column, ddl in statements.items():
            if column not in existing:
                connection.execute(text(ddl))
