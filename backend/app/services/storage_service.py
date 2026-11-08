import base64
import binascii
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

import httpx

from .. import config

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"

# Supabase/S3 reject object keys outside this alphabet. Browsers allow spaces,
# '#' and non-ASCII in filenames, so normalize before building the key.
_UNSAFE_OBJECT_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class StorageError(RuntimeError):
    pass


def sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename or "").strip()
    stem, dot, suffix = base.rpartition(".")
    if dot:
        stem = _UNSAFE_OBJECT_CHARS.sub("_", stem).strip("._") or "clipping"
        suffix = _UNSAFE_OBJECT_CHARS.sub("", suffix).lower()
        return f"{stem}.{suffix}" if suffix else stem
    return _UNSAFE_OBJECT_CHARS.sub("_", base).strip("._") or "clipping"


def _headers() -> dict:
    key = config.supabase_service_role_key()
    headers = {"apikey": key}
    # New-style keys (sb_secret_.../sb_publishable_...) are opaque, not JWTs.
    # Sending them as a Bearer token makes Storage reject the request with
    # "Invalid Compact JWS"; legacy JWT keys still need Authorization.
    if not key.startswith(("sb_secret_", "sb_publishable_")):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _response_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()[:300]
    if isinstance(payload, dict):
        code = payload.get("code") or payload.get("statusCode")
        message = payload.get("message") or payload.get("error")
        if code and message:
            return f"{code}: {message}"
        if message:
            return str(message)
    return str(payload)[:300]


def _raise_for_status(action: str, response: httpx.Response) -> None:
    """Keep Supabase's own error message; the gateway hides it behind HTTP 400."""
    if not response.is_error:
        return
    detail = _response_detail(response)
    suffix = f": {detail}" if detail else ""
    raise StorageError(f"Supabase Storage {action} failed (HTTP {response.status_code}{suffix})")


def key_role() -> str | None:
    """Identify the configured key without verification, so logs can warn."""
    key = config.supabase_service_role_key()
    if key.startswith("sb_secret_"):
        return "secret"
    if key.startswith("sb_publishable_"):
        return "publishable"
    if not key.startswith("eyJ"):
        return None
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, binascii.Error):
        return None
    return data.get("role")


def check_bucket() -> dict:
    bucket = quote(config.supabase_storage_bucket(), safe="")
    url = f"{config.supabase_url()}/storage/v1/bucket/{bucket}"
    try:
        response = httpx.get(url, headers=_headers(), timeout=10.0)
    except httpx.HTTPError as exc:
        raise StorageError(f"Supabase Storage bucket check failed: {exc}") from exc
    _raise_for_status("bucket check", response)
    payload = response.json()
    return {
        "id": payload.get("id") or payload.get("name"),
        "public": payload.get("public"),
        "file_size_limit": payload.get("file_size_limit"),
        "allowed_mime_types": payload.get("allowed_mime_types"),
    }


def _object_url(object_path: str) -> str:
    bucket = quote(config.supabase_storage_bucket(), safe="")
    return f"{config.supabase_url()}/storage/v1/object/{bucket}/{quote(object_path, safe='/')}"


def _signed_url(object_path: str) -> str:
    bucket = quote(config.supabase_storage_bucket(), safe="")
    url = (
        f"{config.supabase_url()}/storage/v1/object/sign/"
        f"{bucket}/{quote(object_path, safe='/')}"
    )
    try:
        response = httpx.post(
            url,
            headers={**_headers(), "Content-Type": "application/json"},
            json={"expiresIn": config.supabase_signed_url_ttl()},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise StorageError(f"Supabase Storage signed URL failed: {exc}") from exc
    _raise_for_status("signed URL", response)
    signed = response.json().get("signedURL")
    if not signed:
        raise StorageError("Supabase did not return a signed URL for the clipping.")
    if signed.startswith("http"):
        return signed
    # The Storage API returns a path relative to /storage/v1.
    return f"{config.supabase_url()}/storage/v1{signed}"


def public_url(object_path: str) -> str:
    bucket = quote(config.supabase_storage_bucket(), safe="")
    if config.supabase_storage_public():
        return (
            f"{config.supabase_url()}/storage/v1/object/public/"
            f"{bucket}/{quote(object_path, safe='/')}"
        )
    try:
        return _signed_url(object_path)
    except (httpx.HTTPError, ValueError) as exc:
        raise StorageError(f"Could not create a signed URL: {exc}") from exc


def save_upload(
    filename: str, content: bytes, content_type: str | None = None
) -> dict:
    """
    Persist an original clipping. Supabase Storage is used when configured;
    otherwise the file is written to backend/uploads for local development.
    """
    safe_name = sanitize_filename(filename)
    if config.supabase_storage_enabled():
        object_path = f"clippings/{safe_name}"
        try:
            response = httpx.post(
                _object_url(object_path),
                headers={
                    **_headers(),
                    "x-upsert": "true",
                    "Content-Type": content_type or "application/octet-stream",
                },
                content=content,
                timeout=60.0,
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"Supabase Storage upload failed: {exc}") from exc
        _raise_for_status("upload", response)
        return {
            "backend": "supabase",
            "path": object_path,
            "url": public_url(object_path),
            "local_path": None,
        }

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_DIR / safe_name
    local_path.write_bytes(content)
    return {
        "backend": "local",
        "path": safe_name,
        "url": f"/uploads/{quote(safe_name)}",
        "local_path": str(local_path),
    }


def resolve_image_url(document) -> str | None:
    if document is None:
        return None
    backend = getattr(document, "storage_backend", None) or "local"
    storage_path = getattr(document, "storage_path", None)
    file_path = getattr(document, "file_path", None)

    if backend == "supabase" and storage_path:
        try:
            return public_url(storage_path)
        except (httpx.HTTPError, StorageError):
            return getattr(document, "image_url", None)
    if storage_path:
        return f"/uploads/{quote(storage_path)}"
    if file_path:
        return f"/uploads/{quote(os.path.basename(file_path))}"
    return getattr(document, "image_url", None)


def materialize_document(document) -> str:
    """
    Return a local filesystem path for OCR/extraction, downloading the object
    from Supabase Storage when the container has no persistent uploads folder.
    """
    backend = getattr(document, "storage_backend", None) or "local"
    storage_path = getattr(document, "storage_path", None)
    file_path = getattr(document, "file_path", None)

    if backend == "supabase" and storage_path:
        cached = Path(tempfile.gettempdir()) / "obitree-storage" / os.path.basename(
            storage_path
        )
        cached.parent.mkdir(parents=True, exist_ok=True)
        if cached.exists():
            return str(cached)
        try:
            response = httpx.get(
                _object_url(storage_path), headers=_headers(), timeout=60.0
            )
        except httpx.HTTPError as exc:
            raise StorageError(
                f"The stored clipping could not be downloaded: {exc}"
            ) from exc
        _raise_for_status("download", response)
        cached.write_bytes(response.content)
        return str(cached)

    candidates = []
    if file_path:
        candidates.append(Path(file_path))
    if storage_path:
        candidates.append(UPLOAD_DIR / storage_path)
    if file_path:
        candidates.append(UPLOAD_DIR / os.path.basename(file_path))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise StorageError("The original clipping is not available in storage.")
