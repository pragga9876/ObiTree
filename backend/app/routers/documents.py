import os
import re
import uuid
import json
import secrets
import shutil
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import config
from ..database import SessionLocal
from .. import models
from ..services.graph_service import build_project_graph
from ..services.hashing_service import hash_bytes
from ..services.ocr_service import extract_text_from_image
from ..services.llm_service import extract_structured_claims
from ..services.record_service import build_canonical_record, compute_record_hash
from ..services.solana_service import verify_solana_attestation
from ..services.storage_service import (
    StorageError,
    materialize_document,
    resolve_image_url,
    save_upload,
)

router = APIRouter(prefix="/api", tags=["documents"])

MEMO_VERSION = "ORBITREE|1"
LEGACY_MEMO_PREFIXES = ("ORBITREE|1", "PAPERROOTS|1")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AttestationRequest(BaseModel):
    document_id: str
    version: int = 1
    transaction_signature: str
    network: str = "devnet"
    wallet: str


def generate_memo_text(
    record_id: str,
    version: int,
    file_hash: str,
    record_hash: str,
    previous_hash: str = "-",
) -> str:
    return (
        f"{MEMO_VERSION}\n"
        f"record: {record_id}\n"
        f"version: {version}\n"
        f"action: DOCUMENT_REGISTERED\n"
        f"file_hash: {file_hash}\n"
        f"record_hash: {record_hash}\n"
        f"previous_hash: {previous_hash}"
    )


# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------

def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:48] or "chronicle"


def _project_previous_hash(
    db: Session,
    project_id: str,
    exclude_document_id: Optional[str] = None,
    before_link_id: Optional[int] = None,
) -> str:
    """Hash of the most recently sealed clipping in this project."""
    query = (
        db.query(models.Contribution)
        .join(
            models.ProjectDocument,
            models.Contribution.document_id == models.ProjectDocument.document_id,
        )
        .filter(
            models.ProjectDocument.project_id == project_id,
            models.Contribution.verification_status == "VERIFIED",
        )
    )
    if exclude_document_id:
        query = query.filter(models.Contribution.document_id != exclude_document_id)
    if before_link_id is not None:
        query = query.filter(models.ProjectDocument.id < before_link_id)
    latest = query.order_by(models.ProjectDocument.id.desc()).first()
    if not latest:
        return "-"

    record = (
        db.query(models.CanonicalRecord)
        .filter(
            models.CanonicalRecord.record_id == latest.document_id,
            models.CanonicalRecord.version == latest.version_id,
        )
        .first()
    )
    return record.record_hash if record else "-"


def _project_for_document(db: Session, document_id: str) -> Optional[models.Project]:
    link = (
        db.query(models.ProjectDocument)
        .filter(models.ProjectDocument.document_id == document_id)
        .first()
    )
    if not link:
        return None
    return db.query(models.Project).filter(models.Project.id == link.project_id).first()


def _project_counts(db: Session, project_id: str) -> dict:
    links = (
        db.query(models.ProjectDocument)
        .filter(models.ProjectDocument.project_id == project_id)
        .all()
    )
    document_ids = [row.document_id for row in links]
    contributions = []
    if document_ids:
        contributions = (
            db.query(models.Contribution)
            .filter(models.Contribution.document_id.in_(document_ids))
            .all()
        )
    uploader_wallets = {link.added_by for link in links if link.added_by}
    contributor_wallets = uploader_wallets | {
        c.wallet for c in contributions if c.wallet
    }
    sealed = [c for c in contributions if c.verification_status == "VERIFIED"]
    return {
        "clippings": len(document_ids),
        "contributors": len(contributor_wallets),
        "attestations": len(sealed),
        "sealed_documents": len({c.document_id for c in sealed}),
        "document_ids": document_ids,
    }


def _project_summary(db: Session, project: models.Project) -> dict:
    counts = _project_counts(db, project.id)
    return {
        "id": project.id,
        "title": project.title,
        "subject_name": project.subject_name,
        "description": project.description,
        "created_by": project.created_by,
        "created_at": project.created_at.isoformat(sep=" ", timespec="seconds")
        if isinstance(project.created_at, datetime)
        else project.created_at,
        "share_path": f"/#/memorial/{project.id}",
        "clippings": counts["clippings"],
        "contributors": counts["contributors"],
        "attestations": counts["attestations"],
        "sealed_documents": counts["sealed_documents"],
    }


def _latest_extraction(db: Session, document_id: str):
    return (
        db.query(models.DocumentExtraction)
        .filter(models.DocumentExtraction.document_id == document_id)
        .order_by(models.DocumentExtraction.created_at.desc())
        .first()
    )


def _latest_canonical(db: Session, document_id: str):
    return (
        db.query(models.CanonicalRecord)
        .filter(models.CanonicalRecord.record_id == document_id)
        .order_by(models.CanonicalRecord.version.desc())
        .first()
    )


def _latest_contribution(db: Session, document_id: str):
    return (
        db.query(models.Contribution)
        .filter(models.Contribution.document_id == document_id)
        .order_by(models.Contribution.created_at.desc())
        .first()
    )


def _iso(value) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return value


def _document_payload(db: Session, document: models.Document, project: Optional[models.Project]):
    canonical_row = _latest_canonical(db, document.id)
    extraction = _latest_extraction(db, document.id)
    contributions = (
        db.query(models.Contribution)
        .filter(models.Contribution.document_id == document.id)
        .order_by(models.Contribution.created_at.asc(), models.Contribution.id.asc())
        .all()
    )

    canonical = {}
    if canonical_row:
        try:
            canonical = json.loads(canonical_row.canonical_json)
        except json.JSONDecodeError:
            canonical = {}

    previous_hash = "-"
    link = None
    if project:
        link = (
            db.query(models.ProjectDocument)
            .filter(
                models.ProjectDocument.project_id == project.id,
                models.ProjectDocument.document_id == document.id,
            )
            .first()
        )
        if link:
            previous_hash = _project_previous_hash(db, project.id, before_link_id=link.id)

    attestations = [
        {
            "wallet": contribution.wallet,
            "tx_signature": contribution.tx_signature,
            "network": contribution.network,
            "verification_status": contribution.verification_status,
            "verified": contribution.verification_status == "VERIFIED",
            "created_at": _iso(contribution.created_at),
        }
        for contribution in contributions
    ]
    sealed = [item for item in attestations if item["verified"]]
    primary = sealed[-1] if sealed else (attestations[-1] if attestations else None)
    image_url = resolve_image_url(document)

    memo = ""
    if canonical_row:
        memo = generate_memo_text(
            record_id=document.id,
            version=canonical_row.version,
            file_hash=document.file_hash,
            record_hash=canonical_row.record_hash,
            previous_hash=previous_hash,
        )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "file_hash": document.file_hash,
        "record_hash": canonical_row.record_hash if canonical_row else None,
        "image_url": image_url,
        "status": canonical_row.status if canonical_row else "PROCESSING",
        "version": canonical_row.version if canonical_row else 1,
        "created_at": _iso(document.created_at),
        "model_name": extraction.model_name if extraction else None,
        "extracted_data": canonical.get("extracted_data", []),
        "canonical_record": canonical,
        "memo_payload": memo,
        "uploader_wallet": link.added_by if link else None,
        "wallet": primary["wallet"] if primary else None,
        "tx_signature": primary["tx_signature"] if primary else None,
        "verification_status": primary["verification_status"] if primary else "UNATTESTED",
        "network": primary["network"] if primary else "devnet",
        "attestations": attestations,
        "attested_wallets": [item["wallet"] for item in sealed],
        "sealed": bool(sealed),
        "claim_count": len(canonical.get("claims", [])),
        "previous_hash": previous_hash,
    }


def _project_payload(db: Session, project: models.Project) -> dict:
    links = (
        db.query(models.ProjectDocument)
        .filter(models.ProjectDocument.project_id == project.id)
        .order_by(models.ProjectDocument.created_at.asc())
        .all()
    )

    documents = []
    for link in links:
        document = (
            db.query(models.Document).filter(models.Document.id == link.document_id).first()
        )
        if document:
            documents.append(_document_payload(db, document, project))

    graph = build_project_graph(project.subject_name, documents)
    summary = _project_summary(db, project)
    merged_count = len(documents) - graph["stats"].get("unmerged", 0)
    summary["description"] = (
        f"A living family chronicle reconstructed from {merged_count} independent "
        f"clipping{'s' if merged_count != 1 else ''} naming {project.subject_name}, "
        "sealed on Solana."
    )

    return {
        "project": summary,
        "documents": documents,
        "graph": graph,
        "ledger": graph["ledger"],
        "reasoning": graph["reasoning"],
        "stats": graph["stats"],
    }


def _resolve_project(
    db: Session,
    project_id: Optional[str],
    subject_name: str,
    wallet: Optional[str],
) -> models.Project:
    if project_id:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Memorial project not found")
        return project

    base = _slugify(subject_name)
    new_id = f"{base}-{secrets.token_hex(3)}"
    while db.query(models.Project).filter(models.Project.id == new_id).first():
        new_id = f"{base}-{secrets.token_hex(3)}"

    project = models.Project(
        id=new_id,
        title=f"The {subject_name} Family Chronicle",
        subject_name=subject_name,
        description="A living memorial assembled from independent newspaper clippings.",
        created_by=wallet,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _primary_subject(extracted_dicts) -> str:
    names = [
        str(item.get("subject") or "").strip()
        for item in extracted_dicts
        if str(item.get("subject") or "").strip()
        and str(item.get("subject")).strip().lower() not in {"unknown", "none"}
    ]
    if not names:
        return "Unidentified Memorial"
    counts = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = (
        db.query(models.Project).order_by(models.Project.created_at.desc()).limit(60).all()
    )
    return {"projects": [_project_summary(db, project) for project in projects]}


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Memorial project not found")
    return _project_payload(db, project)


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    wallet: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Save a clipping, run OCR + Gemini extraction, attach it to a memorial
    project (created on the first contribution) and return its attestation memo.
    """
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    clean_filename = file.filename or "document"
    safe_filename = f"{doc_id}_{os.path.basename(clean_filename)}"

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    file_hash = hash_bytes(content)

    try:
        stored = save_upload(safe_filename, content, file.content_type)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    work_dir = tempfile.mkdtemp(prefix="obitree-")
    working_path = os.path.join(work_dir, safe_filename)
    with open(working_path, "wb") as f:
        f.write(content)

    db_doc = models.Document(
        id=doc_id,
        filename=clean_filename,
        file_path=stored["local_path"],
        file_hash=file_hash,
        storage_backend=stored["backend"],
        storage_path=stored["path"],
        image_url=stored["url"],
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    try:
        try:
            raw_ocr_text = extract_text_from_image(working_path)
        except Exception as exc:
            print(f"OCR warning: {exc}")
            raw_ocr_text = clean_filename

        extraction_results = extract_structured_claims(
            raw_ocr_text, image_path=working_path
        )
        extracted_dicts = [item.model_dump() for item in extraction_results]
        model_used = getattr(extraction_results, "model_name", "gemini-3.5-flash-lite")
        api_key_failed = getattr(extraction_results, "api_key_failed", False)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    db_extraction = models.DocumentExtraction(
        document_id=doc_id,
        raw_ocr_text=raw_ocr_text,
        extraction_json=json.dumps(extracted_dicts),
        model_name=model_used,
        prompt_version="v2.1",
    )
    db.add(db_extraction)

    canonical_record = build_canonical_record(
        record_id=doc_id,
        extracted_data=extracted_dicts,
        version=1,
    )
    record_hash = compute_record_hash(canonical_record)

    db_canonical = models.CanonicalRecord(
        record_id=doc_id,
        version=1,
        canonical_json=json.dumps(canonical_record),
        record_hash=record_hash,
        status="READY_FOR_ATTESTATION",
    )
    db.add(db_canonical)
    db.commit()

    subject_name = _primary_subject(extracted_dicts)
    project = _resolve_project(db, project_id, subject_name, wallet)

    link = models.ProjectDocument(
        project_id=project.id,
        document_id=doc_id,
        added_by=wallet,
    )
    db.add(link)
    db.commit()

    previous_hash = _project_previous_hash(db, project.id, exclude_document_id=doc_id)
    memo_text = generate_memo_text(
        record_id=doc_id,
        version=1,
        file_hash=file_hash,
        record_hash=record_hash,
        previous_hash=previous_hash,
    )

    return {
        "document_id": doc_id,
        "filename": clean_filename,
        "file_hash": file_hash,
        "image_url": stored["url"],
        "record_hash": record_hash,
        "status": "READY_FOR_ATTESTATION",
        "raw_ocr_text": raw_ocr_text,
        "extracted_data": canonical_record["extracted_data"],
        "canonical_record": canonical_record,
        "memo_payload": memo_text,
        "previous_hash": previous_hash,
        "model_name": model_used,
        "api_key_failed": api_key_failed,
        "project": _project_summary(db, project),
        "message": "Clipping archived and added to the family chronicle",
    }


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    extraction = _latest_extraction(db, doc_id)
    payload = _document_payload(db, document, _project_for_document(db, doc_id))
    payload["raw_ocr_text"] = extraction.raw_ocr_text if extraction else ""
    return payload


@router.post("/documents/{doc_id}/extract")
async def extract_document(doc_id: str, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        file_path = materialize_document(document)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    raw_ocr_text = extract_text_from_image(file_path)
    extraction_results = extract_structured_claims(
        raw_ocr_text, image_path=file_path
    )
    extracted_dicts = [item.model_dump() for item in extraction_results]
    model_used = getattr(extraction_results, "model_name", "gemini-3.5-flash-lite")

    db_extraction = models.DocumentExtraction(
        document_id=doc_id,
        raw_ocr_text=raw_ocr_text,
        extraction_json=json.dumps(extracted_dicts),
        model_name=model_used,
        prompt_version="v2.1",
    )
    db.add(db_extraction)

    canonical_record = build_canonical_record(doc_id, extracted_dicts, version=1)
    record_hash = compute_record_hash(canonical_record)

    canonical_row = _latest_canonical(db, doc_id)
    if canonical_row:
        canonical_row.canonical_json = json.dumps(canonical_record)
        canonical_row.record_hash = record_hash
        canonical_row.status = "READY_FOR_ATTESTATION"
    else:
        db.add(
            models.CanonicalRecord(
                record_id=doc_id,
                version=1,
                canonical_json=json.dumps(canonical_record),
                record_hash=record_hash,
                status="READY_FOR_ATTESTATION",
            )
        )

    db.commit()

    project = _project_for_document(db, doc_id)
    previous_hash = (
        _project_previous_hash(db, project.id, exclude_document_id=doc_id)
        if project
        else "-"
    )

    return {
        "document_id": doc_id,
        "file_hash": document.file_hash,
        "record_hash": record_hash,
        "extracted_data": canonical_record["extracted_data"],
        "canonical_record": canonical_record,
        "model_name": model_used,
        "api_key_failed": getattr(extraction_results, "api_key_failed", False),
        "status": "READY_FOR_ATTESTATION",
        "memo_payload": generate_memo_text(
            record_id=doc_id,
            version=1,
            file_hash=document.file_hash,
            record_hash=record_hash,
            previous_hash=previous_hash,
        ),
        "previous_hash": previous_hash,
    }


@router.get("/records/{record_id}")
def get_canonical_record(record_id: str, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(models.Document.id == record_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Record not found")

    canonical_row = _latest_canonical(db, record_id)
    if not canonical_row:
        raise HTTPException(status_code=404, detail="Canonical record not generated yet")

    canonical_dict = json.loads(canonical_row.canonical_json)
    project = _project_for_document(db, record_id)
    previous_hash = (
        _project_previous_hash(db, project.id, exclude_document_id=record_id)
        if project
        else "-"
    )

    return {
        "record_id": record_id,
        "version": canonical_row.version,
        "file_hash": document.file_hash,
        "record_hash": canonical_row.record_hash,
        "status": canonical_row.status,
        "extracted_data": canonical_dict.get("extracted_data", []),
        "canonical_record": canonical_dict,
        "memo_payload": generate_memo_text(
            record_id=record_id,
            version=canonical_row.version,
            file_hash=document.file_hash,
            record_hash=canonical_row.record_hash,
            previous_hash=previous_hash,
        ),
        "previous_hash": previous_hash,
        "project": _project_summary(db, project) if project else None,
    }


@router.post("/attestations")
async def create_attestation(
    attestation: AttestationRequest,
    db: Session = Depends(get_db),
):
    document = (
        db.query(models.Document)
        .filter(models.Document.id == attestation.document_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document record not found")

    canonical_row = _latest_canonical(db, attestation.document_id)
    if not canonical_row:
        raise HTTPException(status_code=404, detail="Canonical record not found")

    configured_network = config.solana_network()
    if attestation.network != configured_network:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This backend verifies {configured_network} transactions, "
                f"but the attestation claims {attestation.network}."
            ),
        )

    wallet = (attestation.wallet or "").strip()
    if not wallet:
        raise HTTPException(
            status_code=400,
            detail="A connected wallet address is required to attest a record.",
        )

    existing_wallet_seal = (
        db.query(models.Contribution)
        .filter(
            models.Contribution.document_id == attestation.document_id,
            models.Contribution.wallet == wallet,
            models.Contribution.verification_status == "VERIFIED",
        )
        .first()
    )
    if (
        existing_wallet_seal
        and existing_wallet_seal.tx_signature != attestation.transaction_signature
    ):
        raise HTTPException(
            status_code=409,
            detail="This wallet has already attested this record. A second witness must use a different wallet.",
        )

    verification = await verify_solana_attestation(
        signature=attestation.transaction_signature,
        expected_record_id=attestation.document_id,
        expected_version=attestation.version,
        expected_file_hash=document.file_hash,
        expected_record_hash=canonical_row.record_hash,
        expected_wallet=wallet,
    )

    status_str = "VERIFIED" if verification.get("verified") else "FAILED"

    existing = (
        db.query(models.Contribution)
        .filter(models.Contribution.tx_signature == attestation.transaction_signature)
        .first()
    )
    if existing:
        existing.verification_status = status_str
        existing.wallet = wallet
        contribution = existing
    else:
        contribution = models.Contribution(
            document_id=attestation.document_id,
            version_id=attestation.version,
            wallet=wallet,
            tx_signature=attestation.transaction_signature,
            network=attestation.network,
            verification_status=status_str,
        )
        db.add(contribution)

    if verification.get("verified"):
        canonical_row.status = "ATTESTED"

    db.commit()

    if not verification.get("verified"):
        # The failed attempt is recorded for audit, but the response is a
        # rejection so the UI can never present it as a valid attestation.
        status_code = 502 if verification.get("status") == "RPC_ERROR" else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": verification.get("message"),
                "status": verification.get("status"),
                "verification_details": verification,
            },
        )

    project = _project_for_document(db, attestation.document_id)
    document_payload = _document_payload(db, document, project)
    return {
        "document_id": attestation.document_id,
        "version": attestation.version,
        "record_hash": canonical_row.record_hash,
        "file_hash": document.file_hash,
        "transaction_signature": attestation.transaction_signature,
        "wallet": contribution.wallet,
        "network": attestation.network,
        "verification_status": status_str,
        "verification_details": verification,
        "attestations": document_payload["attestations"],
        "sealed": document_payload["sealed"],
        "project": _project_summary(db, project) if project else None,
    }


@router.get("/verify/{signature}")
async def verify_signature(signature: str, db: Session = Depends(get_db)):
    contribution = (
        db.query(models.Contribution)
        .filter(models.Contribution.tx_signature == signature)
        .first()
    )

    if contribution:
        document = (
            db.query(models.Document)
            .filter(models.Document.id == contribution.document_id)
            .first()
        )
        canonical = _latest_canonical(db, contribution.document_id)

        return {
            "transaction_signature": signature,
            "document_id": contribution.document_id,
            "version": contribution.version_id,
            "wallet": contribution.wallet,
            "network": contribution.network,
            "verification_status": contribution.verification_status,
            "file_hash": document.file_hash if document else None,
            "record_hash": canonical.record_hash if canonical else None,
        }

    raise HTTPException(status_code=404, detail="Attestation not found")
