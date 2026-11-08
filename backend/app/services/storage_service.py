import os
import tempfile
from pathlib import Path
from urllib.parse import quote

import httpx

from .. import config

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"


class StorageError(RuntimeError):
    pass


def _object_url(object_path: str) -> str:
    bucket = quote(config.supabase_storage_bucket(), safe="")
    return f"{config.supabase_url()}/storage/v1/object/{bucket}/{quote(object_path, safe='/')}"


def _headers() -> dict:
    key = config.supabase_service_role_key()
    return {"Authorization": f"Bearer {key}", "apikey": key}


def _signed_url(object_path: str) -> str:
    bucket = quote(config.supabase_storage_bucket(), safe="")
    url = (
        f"{config.supabase_url()}/storage/v1/object/sign/"
        f"{bucket}/{quote(object_path, safe='/')}"
    )
    response = httpx.post(
        url,
        headers={**_headers(), "Content-Type": "application/json"},
        json={"expiresIn": config.supabase_signed_url_ttl()},
        timeout=30.0,
    )
    response.raise_for_status()
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
    if config.supabase_storage_enabled():
        object_path = f"clippings/{filename}"
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
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError(f"Supabase Storage upload failed: {exc}") from exc
        return {
            "backend": "supabase",
            "path": object_path,
            "url": public_url(object_path),
            "local_path": None,
        }

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_DIR / filename
    local_path.write_bytes(content)
    return {
        "backend": "local",
        "path": filename,
        "url": f"/uploads/{quote(filename)}",
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
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError(
                f"The stored clipping could not be downloaded: {exc}"
            ) from exc
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
