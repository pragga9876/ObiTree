import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env_fresh():
    """
    Dynamically re-reads backend/.env so edits to GEMINI_API_KEY take effect
    immediately without requiring a server reboot.
    """
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()


# Initial load
load_env_fresh()


def get_gemini_api_key() -> str:
    load_env_fresh()
    return os.environ.get("GEMINI_API_KEY", "").strip()


GEMINI_API_KEY = get_gemini_api_key()
SOLANA_NETWORK = os.environ.get("SOLANA_NETWORK", "devnet")
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
