"""
In-process smoke test for the ObiTree backend.

Runs against a throwaway SQLite database with local upload storage, so it does
not touch the development database or Supabase. It verifies the upload path,
image serving, fail-closed attestation rejection and the strict memo parser.

Usage (from the repository root):
    backend/venv/Scripts/python.exe backend/scripts/smoke_test.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

SMOKE_DB = Path(tempfile.gettempdir()) / "obitree-smoke.db"
if SMOKE_DB.exists():
    SMOKE_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app import main  # noqa: E402
from app.routers import documents  # noqa: E402
from app.services import llm_service, solana_service  # noqa: E402

# Keep the smoke test offline: force the deterministic extractor.
llm_service.get_gemini_api_key = lambda: ""

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}{f' — {detail}' if detail else ''}")
    if not condition:
        FAILURES.append(label)


def fake_transaction(memo_text, signer="SmokeWallet1111111111111111111111111111111"):
    return {
        "slot": 42,
        "meta": {"err": None},
        "transaction": {
            "message": {
                "accountKeys": [
                    {"pubkey": signer, "signer": True},
                    {"pubkey": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr", "signer": False},
                ],
                "instructions": [
                    {
                        "program": "spl-memo",
                        "programId": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
                        "parsed": memo_text,
                    }
                ],
            }
        },
    }


def run_verification_checks(record_id, version, file_hash, record_hash):
    wallet = "SmokeWallet1111111111111111111111111111111"
    memo = documents.generate_memo_text(
        record_id=record_id,
        version=version,
        file_hash=file_hash,
        record_hash=record_hash,
        previous_hash="-",
    )
    tx = fake_transaction(memo, signer=wallet)

    async def fake_fetch(_signature):
        return {"transaction": tx, "error": None}

    original_fetch = solana_service.fetch_transaction_from_rpc
    solana_service.fetch_transaction_from_rpc = fake_fetch

    async def verify(**overrides):
        params = {
            "signature": "5" * 88,
            "expected_record_id": record_id,
            "expected_version": version,
            "expected_file_hash": file_hash,
            "expected_record_hash": record_hash,
            "expected_wallet": wallet,
        }
        params.update(overrides)
        return await solana_service.verify_solana_attestation(**params)

    try:
        result = asyncio.run(verify())
        check("valid memo verifies", result["verified"] and result["status"] == "VERIFIED")

        result = asyncio.run(verify(expected_wallet="OtherWallet111111111111111111111111111111"))
        check("wrong signer rejected", result["status"] == "WALLET_MISMATCH")

        result = asyncio.run(verify(expected_record_id="doc_other"))
        check("wrong record id rejected", result["status"] == "RECORD_ID_MISMATCH")

        result = asyncio.run(verify(expected_version=version + 1))
        check("wrong version rejected", result["status"] == "VERSION_MISMATCH")

        result = asyncio.run(verify(expected_record_hash="0" * 64))
        check("wrong record hash rejected", result["status"] == "RECORD_HASH_MISMATCH")

        result = asyncio.run(verify(expected_file_hash="0" * 64))
        check("wrong file hash rejected", result["status"] == "FILE_HASH_MISMATCH")

        result = asyncio.run(verify(signature="sim_deadbeef"))
        check("simulated signature rejected", result["status"] == "SIMULATED_REJECTED")

        meta_backup = tx.pop("meta")
        result = asyncio.run(verify())
        check("missing execution metadata rejected", result["status"] == "MISSING_META")
        tx["meta"] = meta_backup

        no_signers = fake_transaction(memo)
        no_signers["transaction"]["message"]["accountKeys"] = [
            {"pubkey": "SomeAccount11111111111111111111111111111111"}
        ]
        tx_backup = tx["transaction"]["message"]["accountKeys"]
        tx["transaction"]["message"]["accountKeys"] = no_signers["transaction"]["message"][
            "accountKeys"
        ]
        result = asyncio.run(verify())
        check("missing signer data rejected", result["status"] == "MISSING_SIGNERS")
        tx["transaction"]["message"]["accountKeys"] = tx_backup
    finally:
        solana_service.fetch_transaction_from_rpc = original_fetch


def run():
    image_path = Path(tempfile.gettempdir()) / "obitree-smoke.png"
    Image.new("RGB", (32, 32), "white").save(image_path)

    with TestClient(main.app) as client:
        health = client.get("/api/health")
        check("health responds", health.status_code == 200, health.text)
        payload = health.json()
        check("health reports sqlite", payload.get("database") == "sqlite")
        check("health reports local storage", payload.get("storage") == "local")

        with open(image_path, "rb") as handle:
            response = client.post(
                "/api/documents",
                files={"file": ("smoke-obituary.png", handle, "image/png")},
            )
        check("upload without wallet succeeds", response.status_code == 200, response.text[:300])
        upload = response.json()
        record_id = upload["document_id"]
        project_id = upload["project"]["id"]
        check("upload returns hashes", bool(upload.get("file_hash")) and bool(upload.get("record_hash")))
        check("upload returns memo", upload.get("memo_payload", "").startswith("ORBITREE|1"))
        check("upload returns image url", bool(upload.get("image_url")))

        image_response = client.get(upload["image_url"])
        check("uploaded image is served", image_response.status_code == 200)

        project = client.get(f"/api/projects/{project_id}").json()
        check("project lists the clipping", len(project["documents"]) == 1)
        check("family graph has a root", bool(project["graph"].get("root_id")))

        simulated = client.post(
            "/api/attestations",
            json={
                "document_id": record_id,
                "version": 1,
                "transaction_signature": "sim_fake_signature",
                "wallet": "SmokeWallet1111111111111111111111111111111",
                "network": "devnet",
            },
        )
        check("simulated attestation is rejected", simulated.status_code == 400, simulated.text[:300])
        check(
            "rejection reports SIMULATED_REJECTED",
            simulated.json().get("detail", {}).get("status") == "SIMULATED_REJECTED",
        )

        fake = client.post(
            "/api/attestations",
            json={
                "document_id": record_id,
                "version": 1,
                "transaction_signature": "2" * 88,
                "wallet": "SmokeWallet1111111111111111111111111111111",
                "network": "devnet",
            },
        )
        check(
            "unknown signature is rejected",
            fake.status_code in {400, 502},
            fake.text[:300],
        )

        after = client.get(f"/api/projects/{project_id}").json()
        check("failed attempts are not counted", after["stats"]["attestations"] == 0)
        check("failed attempts do not seal the record", after["stats"]["sealed_documents"] == 0)

        run_verification_checks(
            record_id,
            1,
            upload["file_hash"],
            upload["record_hash"],
        )

    check("database file was written", SMOKE_DB.exists() and SMOKE_DB.stat().st_size > 0)

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
