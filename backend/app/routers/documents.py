import os
import uuid
import json
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import SessionLocal
from .. import models
from ..services.hashing_service import hash_file
from ..services.ocr_service import extract_text_from_image
from ..services.llm_service import extract_structured_claims
from ..services.record_service import build_canonical_record, compute_record_hash
from ..services.solana_service import verify_solana_attestation

router = APIRouter(prefix="/api", tags=["documents"])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    wallet: Optional[str] = "contributor"


def generate_memo_text(
    record_id: str,
    version: int,
    file_hash: str,
    record_hash: str,
    previous_hash: str = "-",
) -> str:
    """
    Format standard PAPERROOTS|1 Solana Memo string.
    """
    return (
        f"PAPERROOTS|1\n"
        f"record: {record_id}\n"
        f"version: {version}\n"
        f"action: DOCUMENT_REGISTERED\n"
        f"file_hash: {file_hash}\n"
        f"record_hash: {record_hash}\n"
        f"previous_hash: {previous_hash}"
    )


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Step 1 & 3: Save uploaded file to disk, calculate file_hash,
    create SQLite document row, and run extraction pipeline.
    """
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    clean_filename = file.filename or "document"
    safe_filename = f"{doc_id}_{os.path.basename(clean_filename)}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # 1. Save original file to disk (uploads/)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 2. Calculate file_hash (SHA-256 of original file bytes)
    file_hash = hash_file(file_path)

    # 3. Create Document DB row
    db_doc = models.Document(
        id=doc_id,
        filename=clean_filename,
        file_path=file_path,
        file_hash=file_hash,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # 4. OCR extraction
    try:
        raw_ocr_text = extract_text_from_image(file_path)
    except Exception as e:
        print(f"OCR warning: {e}")
        raw_ocr_text = clean_filename

    # 5. LLM structured claims extraction matching RelationshipData schema
    extraction_results = extract_structured_claims(raw_ocr_text)
    extracted_dicts = [item.model_dump() for item in extraction_results]

    # Save extraction to DB
    db_extraction = models.DocumentExtraction(
        document_id=doc_id,
        raw_ocr_text=raw_ocr_text,
        extraction_json=json.dumps(extracted_dicts),
        model_name="gemini-3.5-flash-lite",
        prompt_version="v2.0",
    )
    db.add(db_extraction)

    # 6 & 7. Build canonical record and compute record_hash
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

    memo_text = generate_memo_text(
        record_id=doc_id,
        version=1,
        file_hash=file_hash,
        record_hash=record_hash,
    )

    return {
        "document_id": doc_id,
        "filename": clean_filename,
        "file_hash": file_hash,
        "record_hash": record_hash,
        "status": "READY_FOR_ATTESTATION",
        "raw_ocr_text": raw_ocr_text,
        "extracted_data": canonical_record["extracted_data"],
        "canonical_record": canonical_record,
        "memo_payload": memo_text,
        "message": "Document processed and canonical record created",
    }


@router.post("/documents/{doc_id}/extract")
async def extract_document(
    doc_id: str,
    db: Session = Depends(get_db),
):
    """
    Rerun OCR & extraction for an existing document.
    """
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Document or file not found")

    raw_ocr_text = extract_text_from_image(doc.file_path)
    extraction_results = extract_structured_claims(raw_ocr_text)
    extracted_dicts = [item.model_dump() for item in extraction_results]

    # Update extraction
    db_extraction = models.DocumentExtraction(
        document_id=doc_id,
        raw_ocr_text=raw_ocr_text,
        extraction_json=json.dumps(extracted_dicts),
        model_name="gemini-3.5-flash-lite",
        prompt_version="v2.0",
    )
    db.add(db_extraction)

    canonical_record = build_canonical_record(doc_id, extracted_dicts, version=1)
    record_hash = compute_record_hash(canonical_record)

    canonical_row = db.query(models.CanonicalRecord).filter(
        models.CanonicalRecord.record_id == doc_id,
        models.CanonicalRecord.version == 1,
    ).first()

    if canonical_row:
        canonical_row.canonical_json = json.dumps(canonical_record)
        canonical_row.record_hash = record_hash
        canonical_row.status = "READY_FOR_ATTESTATION"
    else:
        canonical_row = models.CanonicalRecord(
            record_id=doc_id,
            version=1,
            canonical_json=json.dumps(canonical_record),
            record_hash=record_hash,
            status="READY_FOR_ATTESTATION",
        )
        db.add(canonical_row)

    db.commit()

    return {
        "document_id": doc_id,
        "file_hash": doc.file_hash,
        "record_hash": record_hash,
        "extracted_data": canonical_record["extracted_data"],
        "canonical_record": canonical_record,
        "status": "READY_FOR_ATTESTATION",
    }


@router.get("/records/{record_id}")
def get_canonical_record(
    record_id: str,
    db: Session = Depends(get_db),
):
    """
    Step 8: Return the attestation payload to the frontend.
    """
    doc = db.query(models.Document).filter(models.Document.id == record_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Record not found")

    canonical_row = db.query(models.CanonicalRecord).filter(
        models.CanonicalRecord.record_id == record_id
    ).order_by(models.CanonicalRecord.version.desc()).first()

    if not canonical_row:
        raise HTTPException(status_code=404, detail="Canonical record not generated yet")

    canonical_dict = json.loads(canonical_row.canonical_json)
    memo_text = generate_memo_text(
        record_id=record_id,
        version=canonical_row.version,
        file_hash=doc.file_hash,
        record_hash=canonical_row.record_hash,
    )

    return {
        "record_id": record_id,
        "version": canonical_row.version,
        "file_hash": doc.file_hash,
        "record_hash": canonical_row.record_hash,
        "status": canonical_row.status,
        "extracted_data": canonical_dict.get("extracted_data", []),
        "canonical_record": canonical_dict,
        "memo_payload": memo_text,
    }


@router.post("/attestations")
async def create_attestation(
    attestation: AttestationRequest,
    db: Session = Depends(get_db),
):
    """
    Step 12 & 13: Store transaction signature and independently verify on Solana RPC.
    """
    doc = db.query(models.Document).filter(models.Document.id == attestation.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document record not found")

    canonical_row = db.query(models.CanonicalRecord).filter(
        models.CanonicalRecord.record_id == attestation.document_id,
        models.CanonicalRecord.version == attestation.version,
    ).first()

    if not canonical_row:
        raise HTTPException(status_code=404, detail="Canonical record not found")

    # Step 13: Independently verify with Solana RPC
    verification = await verify_solana_attestation(
        signature=attestation.transaction_signature,
        expected_record_id=attestation.document_id,
        expected_version=attestation.version,
        expected_file_hash=doc.file_hash,
        expected_record_hash=canonical_row.record_hash,
        expected_wallet=attestation.wallet,
    )

    status_str = "VERIFIED" if verification.get("verified") else "FAILED"

    # Save to contributions table
    contribution = models.Contribution(
        document_id=attestation.document_id,
        version_id=attestation.version,
        wallet=attestation.wallet or "unknown",
        tx_signature=attestation.transaction_signature,
        network=attestation.network,
        verification_status=status_str,
    )
    db.add(contribution)

    if verification.get("verified"):
        canonical_row.status = "ATTESTED"

    db.commit()

    return {
        "document_id": attestation.document_id,
        "version": attestation.version,
        "record_hash": canonical_row.record_hash,
        "file_hash": doc.file_hash,
        "transaction_signature": attestation.transaction_signature,
        "network": attestation.network,
        "verification_status": status_str,
        "verification_details": verification,
    }


@router.get("/verify/{signature}")
async def verify_signature(
    signature: str,
    db: Session = Depends(get_db),
):
    """
    Verify any recorded or on-chain transaction signature.
    """
    contrib = db.query(models.Contribution).filter(
        models.Contribution.tx_signature == signature
    ).first()

    if contrib:
        doc = db.query(models.Document).filter(models.Document.id == contrib.document_id).first()
        canonical = db.query(models.CanonicalRecord).filter(
            models.CanonicalRecord.record_id == contrib.document_id,
            models.CanonicalRecord.version == contrib.version_id,
        ).first()

        return {
            "transaction_signature": signature,
            "document_id": contrib.document_id,
            "version": contrib.version_id,
            "wallet": contrib.wallet,
            "network": contrib.network,
            "verification_status": contrib.verification_status,
            "file_hash": doc.file_hash if doc else None,
            "record_hash": canonical.record_hash if canonical else None,
        }

    raise HTTPException(status_code=404, detail="Attestation not found")
