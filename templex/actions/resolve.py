"""resolveItemReference — Semantic vector search to anchor a Work ID.

Takes an ambiguous natural language reference and uses embedding similarity
to locate the most relevant Expression node, then returns its parent Work ID.
This is the ONLY probabilistic step in the retrieval pipeline.
"""

import numpy as np
from templex.db.connection import KuzuConnection
from templex.embeddings.engine import EmbeddingEngine


def resolve_item_reference(query: str, top_k: int = 5) -> dict | None:
    """Resolve a natural language reference to a canonical Work ID.

    Args:
        query: Natural language description (e.g., "sedition law in India").
        top_k: Number of candidate Expressions to consider.

    Returns:
        Dict with work_id, expr_id, title, score, or None if not found.
    """
    # Encode the query
    query_embedding = EmbeddingEngine.encode_query(query)

    # Retrieve all expressions with their embeddings
    conn = KuzuConnection.get_connection()
    result = conn.execute(
        """
        MATCH (e:Expression)
        RETURN e.expr_id, e.work_id, e.text_content, e.embedding
        """
    )

    candidates = []
    while result.has_next():
        row = result.get_next()
        expr_id = row[0]
        work_id = row[1]
        text = row[2]
        emb = row[3]

        if emb is None:
            continue

        # Compute cosine similarity
        emb_array = np.array(emb, dtype=np.float32)
        score = EmbeddingEngine.cosine_similarity(query_embedding, emb_array)
        candidates.append({
            "expr_id": expr_id,
            "work_id": work_id,
            "text_preview": text[:200],
            "score": score,
        })

    if not candidates:
        return None

    # Sort by similarity descending, take best match
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    # Fetch the Work title
    work_result = conn.execute(
        "MATCH (w:Work {work_id: $wid}) RETURN w.title",
        {"wid": best["work_id"]},
    )
    title = ""
    if work_result.has_next():
        title = work_result.get_next()[0]

    return {
        "work_id": best["work_id"],
        "expr_id": best["expr_id"],
        "title": title,
        "score": best["score"],
        "text_preview": best["text_preview"],
        "all_candidates": candidates[:top_k],
    }
