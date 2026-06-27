"""Centralized configuration for TempLex GraphRAG."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

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
HF_FALLBACK_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "HuggingFaceH4/zephyr-7b-beta",
    "mistralai/Mistral-7B-Instruct-v0.3",
]


def refresh_env() -> None:
    """Reload .env values into the current process."""
    load_dotenv(override=True)


def get_hf_settings() -> tuple[str, str, list[str]]:
    """Return the latest Hugging Face runtime settings."""
    refresh_env()
    token = os.getenv("HF_TOKEN", "")
    model = os.getenv("HF_MODEL", HF_MODEL)
    return token, model, list(HF_FALLBACK_MODELS)

# ─── CourtListener ────────────────────────────────────────────────────────────
COURTLISTENER_API_TOKEN = os.getenv("COURTLISTENER_API_TOKEN", "")
COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"

# ─── Indian Kanoon ────────────────────────────────────────────────────────────
INDIANKANOON_API_TOKEN = os.getenv("INDIANKANOON_API_TOKEN", "")
INDIANKANOON_BASE_URL = "https://api.indiankanoon.org"

# ─── API Server ───────────────────────────────────────────────────────────────
API_HOST = "127.0.0.1"
API_PORT = 8000

# ─── Scope Boost Weights ──────────────────────────────────────────────────────
# Applied additively during re-ranking in resolve_item_reference().
# Nothing is excluded — these are purely additive to raw cosine similarity score.
SCOPE_BOOST_VALIDITY     = 0.15   # Expression was ACTIVE on the reference_date
SCOPE_BOOST_DOMAIN       = 0.10   # Work domain matches user's selected domains
SCOPE_BOOST_JURISDICTION = 0.08   # Work jurisdiction matches user's selection

# ─── Autonomous Research Pipeline ──────────────────────────────────────────────
MAX_SEARCH_QUERIES = 5
MAX_INGEST_PER_TURN = 3
CONFIDENCE_THRESHOLD = 0.65

# ─── High-Confidence Research Pipeline (legacy/tools.py aliases) ────────────
INGESTION_CONFIDENCE_THRESHOLD = 0.65  # Min cosine+boost score to proceed with ingestion
INGESTION_MAX_QUERIES     = 5          # Number of speculative query variants to generate
INGESTION_MAX_SNIPPETS    = 50         # Max metadata snippets across all queries
INGESTION_TOP_K_INGEST    = 3          # Only ingest the top-K highest-confidence documents

