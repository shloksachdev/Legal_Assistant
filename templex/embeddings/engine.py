"""CPU-optimized embedding engine using all-MiniLM-L6-v2.

Generates 384-dimensional dense vector embeddings for legal text.
Lazy-loads the model on first use to conserve startup memory.
"""

import os
import requests
import numpy as np
from templex.config import EMBEDDING_MODEL_NAME

class EmbeddingEngine:
    """Wrapper around HuggingFace Inference API to conserve RAM on free tiers."""

    @classmethod
    def _get_headers(cls):
        token = os.getenv("HF_TOKEN")
        if not token:
            raise ValueError("HF_TOKEN environment variable is required for embeddings.")
        return {"Authorization": f"Bearer {token}"}

    @classmethod
    def _call_api(cls, payload: dict) -> list:
        api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/{EMBEDDING_MODEL_NAME}"
        response = requests.post(api_url, headers=cls._get_headers(), json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"HuggingFace API Error ({response.status_code}): {response.text}")
        return response.json()

    @classmethod
    def encode_batch(cls, texts: list[str]) -> np.ndarray:
        """Encode a list of texts into embeddings. Returns shape (N, 384)."""
        if not texts:
            return np.array([])
        results = cls._call_api({"inputs": texts})
        return np.array(results)

    @classmethod
    def encode_query(cls, text: str) -> np.ndarray:
        """Encode a single query string. Returns shape (384,)."""
        results = cls._call_api({"inputs": text})
        return np.array(results)

    @classmethod
    def cosine_similarity(cls, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
