import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import config, models
from .database import Base, IS_POSTGRES, engine, ensure_schema
from .routers import documents
from .services import storage_service

LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.log"))
log_handlers = [logging.StreamHandler()]
try:
    log_handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
except OSError:
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("obitree")
logger.info("Starting ObiTree backend server...")


def _retire_legacy_simulated_attestations():
    """
    Older builds accepted ``sim_``/``mock_`` signatures. Those were never
    on-chain, so they must stop counting as verified attestations.
    """
    try:
        with engine.begin() as connection:
            retired = connection.execute(
                text(
                    "UPDATE contributions SET verification_status = 'FAILED' "
                    "WHERE verification_status = 'VERIFIED' "
                    "AND (tx_signature LIKE 'sim[_]%' OR tx_signature LIKE 'mock[_]%')"
                )
            )
            connection.execute(
                text(
                    "UPDATE canonical_records SET status = 'READY_FOR_ATTESTATION' "
                    "WHERE status = 'ATTESTED' AND NOT EXISTS ("
                    "SELECT 1 FROM contributions c "
                    "WHERE c.document_id = canonical_records.record_id "
                    "AND c.version_id = canonical_records.version "
                    "AND c.verification_status = 'VERIFIED')"
                )
            )
            if retired.rowcount:
                logger.warning(
                    "Retired %s simulated attestation(s) from the ledger", retired.rowcount
                )
    except Exception as exc:  # pragma: no cover - depends on external database
        logger.error("Could not retire legacy simulated attestations: %s", exc)


def _log_deployment_config():
    """Surface missing production configuration without printing secrets."""
    if not config.is_production():
        return
    if not config.get_env("DATABASE_URL"):
        logger.warning(
            "DATABASE_URL is not set; falling back to SQLite on an ephemeral disk."
        )
    if not config.supabase_storage_enabled():
        logger.warning(
            "Supabase Storage is not configured; uploads will use ephemeral local disk."
        )
    if not config.get_env("CORS_ORIGINS"):
        logger.warning(
            "CORS_ORIGINS is not set; only local development origins are allowed."
        )
    logger.info("CORS allowlist: %s", ", ".join(config.cors_origins()) or "(none)")
    if config.cors_origin_regex():
        logger.info("CORS origin regex: %s", config.cors_origin_regex())


def _log_storage_status():
    """Check Supabase Storage once at boot so bad keys/buckets show in logs."""
    if not config.supabase_storage_enabled():
        return
    role = storage_service.key_role()
    if role in {"anon", "publishable"}:
        logger.error(
            "Supabase key is a %s key, not a secret/service key; uploads will be "
            "rejected by row-level security.",
            role,
        )
    try:
        info = storage_service.check_bucket()
    except Exception as exc:  # pragma: no cover - depends on external service
        logger.warning("Supabase Storage bucket check failed: %s", exc)
        return
    logger.info(
        "Supabase bucket '%s' ready (public=%s, size_limit=%s, allowed_mime_types=%s)",
        info["id"],
        info["public"],
        info["file_size_limit"],
        info["allowed_mime_types"] or "any",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    _retire_legacy_simulated_attestations()
    _log_deployment_config()
    _log_storage_status()
    logger.info(
        "Database ready (%s); storage=%s",
        "postgresql" if IS_POSTGRES else "sqlite",
        "supabase" if config.supabase_storage_enabled() else "local",
    )
    yield


app = FastAPI(
    title="ObiTree API",
    description="Family chronicles reconstructed from obituaries and sealed on Solana.",
    version="2.1.0",
    lifespan=lifespan,
)

# The Vercel deployment and local Vite servers are allowlisted through env vars.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_origin_regex=config.cors_origin_regex() or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve local development uploads. Production images live in Supabase Storage.
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(documents.router)


@app.get("/health")
@app.get("/api/health")
def health():
    database_status = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on external database
        logger.error("Health check database failure: %s", exc)
        database_status = "unavailable"

    payload = {
        "status": "ok" if database_status == "ok" else "degraded",
        "service": "obitree-backend",
        "database": "postgresql" if IS_POSTGRES else "sqlite",
        "database_status": database_status,
        "storage": "supabase" if config.supabase_storage_enabled() else "local",
        "network": config.solana_network(),
        "rpc": config.solana_rpc_url(),
    }
    if database_status != "ok":
        return JSONResponse(status_code=503, content=payload)
    return payload
