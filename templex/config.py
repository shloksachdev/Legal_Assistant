"""Centralized configuration for TempLex GraphRAG."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "kuzu_data"
SEED_DIR = BASE_DIR / "seed_data"

# ─── Embedding Model ─────────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ─── LLM Configuration (Hugging Face Inference API) ──────────────────────────
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.2-3B-Instruct")

# ─── CourtListener ────────────────────────────────────────────────────────────
COURTLISTENER_API_TOKEN = os.getenv("COURTLISTENER_API_TOKEN", "")
COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"

# ─── API Server ───────────────────────────────────────────────────────────────
API_HOST = "127.0.0.1"
API_PORT = 8000
