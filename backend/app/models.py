from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from .database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    file_hash = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    raw_ocr_text = Column(Text, nullable=True)
    extraction_json = Column(Text, nullable=True)
    model_name = Column(String, default="gemini-3.8-flash")
    prompt_version = Column(String, default="v1.0")
    created_at = Column(DateTime, server_default=func.now())


class CanonicalRecord(Base):
    __tablename__ = "canonical_records"

    record_id = Column(String, primary_key=True, index=True)
    version = Column(Integer, default=1, primary_key=True)
    canonical_json = Column(Text, nullable=False)
    record_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="READY_FOR_ATTESTATION")
    created_at = Column(DateTime, server_default=func.now())


class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, nullable=False, index=True)
    version_id = Column(Integer, default=1)
    wallet = Column(String, nullable=False)
    tx_signature = Column(String, nullable=False, unique=True, index=True)
    network = Column(String, default="devnet")
    verification_status = Column(String, default="PENDING")
    created_at = Column(DateTime, server_default=func.now())
