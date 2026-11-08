import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from . import models
from .routers import documents

# Configure unified application logging to console and backend/app.log
LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.log"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("paperroots")
logger.info("Starting PaperRoots backend server...")

app = FastAPI(title="PaperRoots API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize all database tables
Base.metadata.create_all(bind=engine)

# Include API routes
app.include_router(documents.router)


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "paperroots-backend",
        "database": "sqlite",
    }
