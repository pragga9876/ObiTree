import hashlib
import json
import os


def hash_file(file_path: str) -> str:
    """
    Calculate the SHA-256 checksum of an original file on disk.
    Reads in 64KB chunks to efficiently handle large documents.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for hashing: {file_path}")

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def hash_bytes(data: bytes) -> str:
    """
    Calculate SHA-256 checksum of in-memory bytes.
    """
    return hashlib.sha256(data).hexdigest()


def canonicalize_json(record: dict) -> str:
    """
    Create a deterministic canonical JSON string:
    - Keys sorted alphabetically
    - No whitespace around separators
    - UTF-8 characters preserved
    """
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def hash_record(record: dict) -> str:
    """
    Calculate the record_hash (SHA-256) of a canonical record.
    """
    canonical_str = canonicalize_json(record)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
