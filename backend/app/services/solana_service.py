import re
from typing import Any, Dict, Optional

import httpx

from .. import config

MEMO_PROGRAM_IDS = {
    # SPL Memo Program v2 and the legacy v1 program are both official.
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
}

MEMO_PREFIXES = ("ORBITREE|1", "PAPERROOTS|1")
BASE58_SIGNATURE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{80,90}$")


def _result(verified: bool, status: str, message: str, **extra: Any) -> Dict[str, Any]:
    payload = {
        "verified": verified,
        "status": status,
        "message": message,
        "network": config.solana_network(),
        "rpc_url": config.solana_rpc_url(),
    }
    payload.update(extra)
    return payload


async def fetch_transaction_from_rpc(signature: str) -> Dict[str, Any]:
    """
    Queries the configured Solana RPC for a confirmed transaction.

    Returns ``{"transaction": <result>, "error": <message>}`` so callers can
    fail closed on transport/RPC errors instead of treating them as "not found".
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(config.solana_rpc_url(), json=payload)
    except httpx.HTTPError as exc:
        return {"transaction": None, "error": f"RPC request failed: {exc}"}

    if response.status_code != 200:
        return {
            "transaction": None,
            "error": f"RPC returned HTTP {response.status_code}",
        }

    try:
        body = response.json()
    except ValueError:
        return {"transaction": None, "error": "RPC returned a non-JSON response"}

    if body.get("error"):
        return {"transaction": None, "error": f"RPC error: {body['error']}"}

    return {"transaction": body.get("result"), "error": None}


def _instruction_memo(instruction: Dict[str, Any]) -> Optional[str]:
    program_id = instruction.get("programId")
    if instruction.get("program") == "spl-memo" and program_id in MEMO_PROGRAM_IDS:
        parsed = instruction.get("parsed")
        if isinstance(parsed, str):
            return parsed
    if program_id in MEMO_PROGRAM_IDS:
        data = instruction.get("parsed") or instruction.get("data")
        if isinstance(data, str):
            return data
    return None


def extract_memo_from_transaction(tx_data: Dict[str, Any]) -> Optional[str]:
    """
    Returns the memo string only when it comes from a real SPL Memo Program
    instruction in the transaction. Log messages are never used as evidence.
    """
    if not tx_data:
        return None

    message = (tx_data.get("transaction") or {}).get("message") or {}
    for instruction in message.get("instructions") or []:
        if isinstance(instruction, dict):
            memo = _instruction_memo(instruction)
            if memo:
                return memo
        # jsonParsed "innerInstructions" are not part of the signed message.
    return None


def parse_memo_envelope(memo_text: str) -> Optional[Dict[str, str]]:
    lines = [line.strip() for line in (memo_text or "").strip().splitlines()]
    if not lines or lines[0] not in MEMO_PREFIXES:
        return None

    fields: Dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def _extract_signers(tx_data: Dict[str, Any]) -> Optional[set]:
    message = (tx_data.get("transaction") or {}).get("message") or {}
    account_keys = message.get("accountKeys") or []
    signers = set()
    saw_signer_flag = False
    for key in account_keys:
        if isinstance(key, dict):
            if key.get("signer") is True:
                saw_signer_flag = True
                if key.get("pubkey"):
                    signers.add(key["pubkey"])
        elif isinstance(key, str):
            # Without parsed signer flags we cannot prove who signed.
            continue
    if not saw_signer_flag:
        return None
    return signers


async def verify_solana_attestation(
    signature: str,
    expected_record_id: str,
    expected_version: int,
    expected_file_hash: str,
    expected_record_hash: str,
    expected_wallet: str,
) -> Dict[str, Any]:
    """
    Verifies a transaction signature against the record it claims to attest.

    Every check fails closed: any missing, unparseable or mismatched detail is
    a rejection. Simulated signatures are never accepted, in any environment.
    """
    if not signature:
        return _result(False, "MISSING_SIGNATURE", "No transaction signature was provided.")

    if signature.startswith(("sim_", "mock_")):
        return _result(
            False,
            "SIMULATED_REJECTED",
            "Simulated signatures are not valid blockchain attestations.",
            signature=signature,
        )

    if not BASE58_SIGNATURE.match(signature):
        return _result(
            False,
            "INVALID_SIGNATURE",
            "The transaction signature is not a valid base58 Solana signature.",
            signature=signature,
        )

    if not expected_wallet:
        return _result(
            False,
            "WALLET_REQUIRED",
            "An attesting wallet address is required to verify the transaction signer.",
            signature=signature,
        )

    if not expected_record_id or not expected_file_hash or not expected_record_hash:
        return _result(
            False,
            "MISSING_EXPECTED_DATA",
            "The record is missing the hashes needed to verify this attestation.",
            signature=signature,
        )

    response = await fetch_transaction_from_rpc(signature)
    tx_data = response["transaction"]
    if response["error"]:
        return _result(
            False,
            "RPC_ERROR",
            f"Could not query the Solana RPC: {response['error']}",
            signature=signature,
        )

    if not tx_data:
        return _result(
            False,
            "NOT_FOUND",
            "Transaction not found on the configured Solana cluster yet. "
            "Wait for confirmation and try again.",
            signature=signature,
        )

    meta = tx_data.get("meta")
    if not isinstance(meta, dict):
        return _result(
            False,
            "MISSING_META",
            "The RPC response has no execution metadata, so success cannot be proven.",
            signature=signature,
        )
    if meta.get("err") is not None:
        return _result(
            False,
            "FAILED_ON_CHAIN",
            f"Transaction executed with an error: {meta.get('err')}",
            signature=signature,
        )

    memo_text = extract_memo_from_transaction(tx_data)
    if not memo_text:
        return _result(
            False,
            "MISSING_MEMO",
            "No SPL Memo Program instruction was found in the transaction.",
            signature=signature,
        )

    fields = parse_memo_envelope(memo_text)
    if fields is None:
        return _result(
            False,
            "INVALID_FORMAT",
            "The memo does not match the ORBITREE|1 envelope.",
            signature=signature,
            memo=memo_text,
        )

    if fields.get("record") != expected_record_id:
        return _result(
            False,
            "RECORD_ID_MISMATCH",
            "The memo was signed for a different record.",
            signature=signature,
            memo=memo_text,
        )

    if fields.get("version") != str(expected_version):
        return _result(
            False,
            "VERSION_MISMATCH",
            "The memo was signed for a different record version.",
            signature=signature,
            memo=memo_text,
        )

    if fields.get("action") != "DOCUMENT_REGISTERED":
        return _result(
            False,
            "ACTION_MISMATCH",
            "The memo action is not DOCUMENT_REGISTERED.",
            signature=signature,
            memo=memo_text,
        )

    if (fields.get("file_hash") or "").lower() != expected_file_hash.lower():
        return _result(
            False,
            "FILE_HASH_MISMATCH",
            "The memo does not contain this clipping's file hash.",
            signature=signature,
            memo=memo_text,
        )

    if (fields.get("record_hash") or "").lower() != expected_record_hash.lower():
        return _result(
            False,
            "RECORD_HASH_MISMATCH",
            "The memo does not contain this record's canonical hash.",
            signature=signature,
            memo=memo_text,
        )

    signers = _extract_signers(tx_data)
    if signers is None:
        return _result(
            False,
            "MISSING_SIGNERS",
            "The transaction does not expose signer information, so ownership "
            "of the attestation cannot be proven.",
            signature=signature,
            memo=memo_text,
        )

    if expected_wallet not in signers:
        return _result(
            False,
            "WALLET_MISMATCH",
            "The transaction was not signed by the wallet claiming this attestation.",
            signature=signature,
            memo=memo_text,
        )

    return _result(
        True,
        "VERIFIED",
        f"Transaction verified on Solana {config.solana_network()}.",
        signature=signature,
        slot=tx_data.get("slot"),
        memo=memo_text,
        signer=expected_wallet,
    )
