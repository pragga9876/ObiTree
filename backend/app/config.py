import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

DEFAULT_SOLANA_RPC_URL = "https://api.devnet.solana.com"
DEV_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"


def load_env_fresh():
    """
    Re-read backend/.env so local edits take effect without a server reboot.
    The file is excluded from the production image; Render/Vercel environment
    variables are the source of truth in deployment.
    """
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


load_env_fresh()


def get_env(name: str, default: str = "") -> str:
    load_env_fresh()
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def is_production() -> bool:
    return get_env("APP_ENV", "development").lower() in {"production", "prod"}


def get_gemini_api_key() -> str:
    return get_env("GEMINI_API_KEY")


GEMINI_API_KEY = get_gemini_api_key()


def database_url() -> str:
    """PostgreSQL (Supabase) in production, local SQLite in development."""
    return get_env("DATABASE_URL") or f"sqlite:///{BACKEND_DIR / 'obitree.db'}"


def solana_network() -> str:
    return get_env("SOLANA_NETWORK", "devnet")


def solana_rpc_url() -> str:
    return get_env("SOLANA_RPC_URL", DEFAULT_SOLANA_RPC_URL)


def supabase_url() -> str:
    return get_env("SUPABASE_URL").rstrip("/")


def supabase_service_role_key() -> str:
    return get_env("SUPABASE_SERVICE_ROLE_KEY")


def supabase_storage_bucket() -> str:
    return get_env("SUPABASE_STORAGE_BUCKET", "obituary-images")


def supabase_storage_enabled() -> bool:
    return bool(supabase_url() and supabase_service_role_key())


def supabase_storage_public() -> bool:
    return get_env("SUPABASE_STORAGE_PUBLIC", "true").lower() not in {
        "0",
        "false",
        "no",
    }


def supabase_signed_url_ttl() -> int:
    try:
        return max(60, int(get_env("SUPABASE_SIGNED_URL_TTL", "604800")))
    except ValueError:
        return 604800


def cors_origins() -> list[str]:
    raw = get_env("CORS_ORIGINS", DEV_CORS_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def cors_origin_regex() -> str:
    return get_env("CORS_ORIGIN_REGEX")
