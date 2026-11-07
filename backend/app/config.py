import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

if ENV_PATH.exists():
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SOLANA_NETWORK = os.environ.get("SOLANA_NETWORK", "devnet")
SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
