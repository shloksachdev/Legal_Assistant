"""resolveItemReference — Semantic vector search to anchor a Work ID.

Takes an ambiguous natural language reference and uses embedding similarity
to locate the most relevant Expression node, then returns its parent Work ID.
This is the ONLY probabilistic step in the retrieval pipeline.

Scope boost (optional): if a QueryScope is passed, expressions that were
ACTIVE on the reference date, match the selected domains, or match the
selected jurisdictions receive additive score bonuses. Nothing is ever
excluded — the full graph is always scanned.
"""

import numpy as np
from templex.db.connection import KuzuConnection
from templex.embeddings.engine import EmbeddingEngine


def resolve_item_reference(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.35,
    scope=None,          # QueryScope | None — imported lazily to avoid circular deps
) -> dict | None:
    """Resolve a natural language reference to a canonical Work ID.

    Args:
        query:               Natural language description (e.g., "sedition law in India").
        top_k:               Number of candidate Expressions to return.
        similarity_threshold: Minimum score (after boost) required for a match.
        scope:               Optional QueryScope — adds validity/domain/jurisdiction boosts.

    Returns:
        Dict with work_id, expr_id, title, score, or None if not found.
    """

    # Globally improve semantic matching by appending strong context keywords
    contextualized_query = query
    if "law text" not in query.lower():
        contextualized_query = f"{query} law text title definition"

    # Encode the query
    query_embedding = EmbeddingEngine.encode_query(contextualized_query)

    # ── Full graph scan — join Work so we get domain + jurisdiction for boosting ──
    conn = KuzuConnection.get_connection()
    result = conn.execute(
        """
        MATCH (w:Work)-[:HAS_VERSION]->(e:Expression)
        RETURN e.expr_id, e.work_id, e.text_content, e.embedding,
               e.valid_from, e.valid_to,
               w.domain, w.jurisdiction
        """
    )

    candidates = []
    while result.has_next():
        row = result.get_next()
        expr_id      = row[0]
        work_id      = row[1]
        text         = row[2]
        emb          = row[3]
        valid_from   = row[4] or ""
        valid_to     = row[5] or ""
        domain       = row[6] or ""
        jurisdiction = row[7] or ""

        if emb is None:
            continue

        # Raw cosine similarity
        emb_array = np.array(emb, dtype=np.float32)
        raw_score = float(EmbeddingEngine.cosine_similarity(query_embedding, emb_array))

        candidate = {
            "expr_id":      expr_id,
            "work_id":      work_id,
            "text_preview": text[:200],
            "raw_score":    raw_score,
            "valid_from":   valid_from,
            "valid_to":     valid_to,
            "domain":       domain,
            "jurisdiction": jurisdiction,
        }

        # Apply scope boost (additive, never subtractive)
        if scope is not None:
            candidate["score"] = scope.apply_boost(candidate)
        else:
            candidate["score"] = raw_score

        candidates.append(candidate)

    if not candidates:
        return None

    # Sort by boosted score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    # Threshold check (against boosted score)
    if best["score"] < similarity_threshold:
        return None

    # Fetch Work title and source URL for the best match
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
        title      = row[0] or ""
        source_url = row[1] or ""

    return {
        "work_id":       best["work_id"],
        "expr_id":       best["expr_id"],
        "title":         title,
        "source_url":    source_url,
        "score":         best["score"],
        "raw_score":     best["raw_score"],
        "text_preview":  best["text_preview"],
        "all_candidates": candidates[:top_k],
    }
