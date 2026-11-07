import uuid
import hashlib
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import Base, engine, SessionLocal
from . import models

app = FastAPI(title="ObiTree API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure SQLite database tables exist
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health(db: Session = Depends(get_db)):
    # Verify SQLite connectivity
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "obitree-backend",
        "database": "sqlite"
    }


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"

    db_doc = models.Document(
        id=doc_id,
        filename=file.filename or "document",
        file_hash=file_hash,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return {
        "id": db_doc.id,
        "filename": db_doc.filename,
        "file_hash": db_doc.file_hash,
        "status": "uploaded",
        "message": f"Document uploaded successfully (ID: {db_doc.id})"
    }
