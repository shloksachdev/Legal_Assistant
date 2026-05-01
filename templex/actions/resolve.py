"""resolveItemReference — Semantic vector search to anchor a Work ID.

Takes an ambiguous natural language reference and uses embedding similarity
to locate the most relevant Expression node, then returns its parent Work ID.
This is the ONLY probabilistic step in the retrieval pipeline.
"""

import numpy as np
from templex.db.connection import KuzuConnection
from templex.embeddings.engine import EmbeddingEngine


def resolve_item_reference(query: str, top_k: int = 5, similarity_threshold: float = 0.35) -> dict | None:
    """Resolve a natural language reference to a canonical Work ID.

    Args:
        query: Natural language description (e.g., "sedition law in India").
        top_k: Number of candidate Expressions to consider.
        similarity_threshold: Minimum cosine similarity score required for a match.

    Returns:
        Dict with work_id, expr_id, title, score, or None if not found.
    """
    
    # Globally improve semantic matching by appending strong context keywords
    # This prevents short alphanumeric inputs (like "IPC-375") from accidentally matching
    # nodes that just happen to share random sub-tokens (like BNS-113).
    contextualized_query = query
    if "law text" not in query.lower():
        contextualized_query = f"{query} law text title definition"
        
    # Encode the query
    query_embedding = EmbeddingEngine.encode_query(contextualized_query)

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
        score = float(EmbeddingEngine.cosine_similarity(query_embedding, emb_array))
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
    
    # Check threshold to prevent returning completely irrelevant matches
    if best["score"] < similarity_threshold:
        return None

    # Fetch the Work title and source URL
    work_result = conn.execute(
        """
        MATCH (w:Work {work_id: $wid})
        OPTIONAL MATCH (a:Action)-[:INITIATES]->(e:Expression {expr_id: $eid})
        RETURN w.title, a.source_ref LIMIT 1
        """,
        {"wid": best["work_id"], "eid": best["expr_id"]},
    )
    title = ""
    source_url = ""
    if work_result.has_next():
        row = work_result.get_next()
        title = row[0] or ""
        source_url = row[1] or ""

    return {
        "work_id": best["work_id"],
        "expr_id": best["expr_id"],
        "title": title,
        "source_url": source_url,
        "score": best["score"],
        "text_preview": best["text_preview"],
        "all_candidates": candidates[:top_k],
    }
