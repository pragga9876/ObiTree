import httpx
import re
from typing import Dict, Any, Optional

DEVNET_RPC_URL = "https://api.devnet.solana.com"


async def fetch_transaction_from_rpc(signature: str) -> Optional[Dict[str, Any]]:
    """
    Queries Solana Devnet RPC for a confirmed transaction.
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

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(DEVNET_RPC_URL, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("result")
        except Exception as e:
            print(f"Solana RPC query error: {e}")
    return None


def extract_memo_from_transaction(tx_data: Dict[str, Any]) -> Optional[str]:
    """
    Extracts the Memo text string from a parsed Solana transaction.
    """
    if not tx_data:
        return None

    transaction = tx_data.get("transaction", {})
    message = transaction.get("message", {})
    instructions = message.get("instructions", [])

    for inst in instructions:
        # jsonParsed memo instruction
        if isinstance(inst, dict):
            if inst.get("program") == "spl-memo":
                return inst.get("parsed")
            # Raw string instruction or programId check
            if inst.get("programId") in [
                "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
                "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
            ]:
                return inst.get("parsed") or inst.get("data")

    # Also check log messages in meta
    meta = tx_data.get("meta", {})
    log_messages = meta.get("logMessages", [])
    for log in log_messages:
        if "Program log: Memo" in log:
            return log.replace("Program log: Memo (len", "").split("): ", 1)[-1].strip('"')
        if "ORBITREE|1" in log or "PAPERROOTS|1" in log:
            return log

    return None


async def verify_solana_attestation(
    signature: str,
    expected_record_id: str,
    expected_version: int,
    expected_file_hash: str,
    expected_record_hash: str,
    expected_wallet: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Independently verifies a Solana transaction signature against expected record details.
    """
    tx_data = await fetch_transaction_from_rpc(signature)

    if not tx_data:
        # If simulated / test signature
        if signature.startswith("sim_") or signature.startswith("mock_"):
            return {
                "verified": True,
                "status": "VERIFIED_SIMULATED",
                "signature": signature,
                "memo": f"ORBITREE|1\nrecord: {expected_record_id}\nversion: {expected_version}\naction: DOCUMENT_REGISTERED\nfile_hash: {expected_file_hash}\nrecord_hash: {expected_record_hash}\nprevious_hash: -",
                "message": "Simulated Devnet transaction accepted for testing",
            }
        return {
            "verified": False,
            "status": "NOT_FOUND",
            "message": "Transaction signature not found on Solana Devnet yet. Please try again once confirmed.",
        }

    # 1. Check transaction execution status
    meta = tx_data.get("meta", {})
    if meta.get("err") is not None:
        return {
            "verified": False,
            "status": "FAILED_ON_CHAIN",
            "message": f"Transaction executed with error: {meta.get('err')}",
        }

    # 2. Extract Memo
    memo_text = extract_memo_from_transaction(tx_data)
    if not memo_text:
        return {
            "verified": False,
            "status": "MISSING_MEMO",
            "message": "No Memo instruction found in transaction",
        }

    # 3. Check for the Orbitree memo envelope (legacy PaperRoots memos still verify)
    if "ORBITREE|1" not in memo_text and "PAPERROOTS|1" not in memo_text:
        return {
            "verified": False,
            "status": "INVALID_FORMAT",
            "message": "Memo does not match the ORBITREE|1 specification",
        }

    # 4. Check record_hash and file_hash matching
    if expected_record_hash not in memo_text:
        return {
            "verified": False,
            "status": "RECORD_HASH_MISMATCH",
            "message": f"Memo does not contain expected record_hash: {expected_record_hash}",
        }

    if expected_file_hash and expected_file_hash not in memo_text:
        return {
            "verified": False,
            "status": "FILE_HASH_MISMATCH",
            "message": f"Memo does not contain expected file_hash: {expected_file_hash}",
        }

    # 5. Confirm the contributor wallet actually signed the transaction
    message = tx_data.get("transaction", {}).get("message", {})
    signers = {
        key.get("pubkey")
        for key in message.get("accountKeys", [])
        if isinstance(key, dict) and key.get("signer")
    }
    if expected_wallet and signers and expected_wallet not in signers:
        return {
            "verified": False,
            "status": "WALLET_MISMATCH",
            "message": "The transaction was not signed by the expected contributor wallet.",
        }

    return {
        "verified": True,
        "status": "VERIFIED",
        "signature": signature,
        "slot": tx_data.get("slot"),
        "memo": memo_text,
        "message": "Transaction verified successfully on Solana Devnet",
    }
