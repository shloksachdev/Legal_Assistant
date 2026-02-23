"""CPU-optimized embedding engine using all-MiniLM-L6-v2.

Generates 384-dimensional dense vector embeddings for legal text.
Lazy-loads the model on first use to conserve startup memory.
"""

import numpy as np
from templex.config import EMBEDDING_MODEL_NAME


class EmbeddingEngine:
    """Singleton wrapper around sentence-transformers for CPU inference."""

    _model = None

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
        return cls._model

    @classmethod
    def encode_batch(cls, texts: list[str]) -> np.ndarray:
        """Encode a list of texts into embeddings. Returns shape (N, 384)."""
        model = cls._load_model()
        return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

    @classmethod
    def encode_query(cls, text: str) -> np.ndarray:
        """Encode a single query string. Returns shape (384,)."""
        model = cls._load_model()
        return model.encode(text, show_progress_bar=False, convert_to_numpy=True)

    @classmethod
    def cosine_similarity(cls, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
