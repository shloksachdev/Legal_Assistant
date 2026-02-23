"""aggregateImpact — Multi-hop traversal for systemic legislative impact.

Given an Action node, traverses all TERMINATES/INITIATES edges to collect
every affected Expression and their parent Works, producing a structured
summary of the total legislative impact of a single event.
"""

from templex.db.connection import KuzuConnection


def aggregate_impact(action_id: str) -> dict:
    """Summarize the systemic impact of a legislative Action.

    Args:
        action_id: Canonical Action ID (e.g., "ACT-BNS-2024").

    Returns:
        Dict with the action metadata, lists of terminated and initiated
        provisions, and affected Work nodes.
    """
    conn = KuzuConnection.get_connection()

    # Get Action metadata
    action_result = conn.execute(
        """
        MATCH (a:Action {action_id: $aid})
        RETURN a.action_type, a.description, a.effective_date, a.source_ref
        """,
        {"aid": action_id},
    )

    action_meta = None
    if action_result.has_next():
        row = action_result.get_next()
        action_meta = {
            "action_id": action_id,
            "action_type": row[0],
            "description": row[1],
            "effective_date": row[2],
            "source_ref": row[3],
        }

    if not action_meta:
        return {"error": f"Action '{action_id}' not found."}

    # Find all TERMINATED expressions
    terminated = _get_related_expressions(conn, action_id, "TERMINATES")

    # Find all INITIATED expressions
    initiated = _get_related_expressions(conn, action_id, "INITIATES")

    # Collect unique affected Works
    affected_work_ids = set()
    for expr in terminated + initiated:
        affected_work_ids.add(expr["work_id"])

    affected_works = []
    for wid in affected_work_ids:
        result = conn.execute(
            "MATCH (w:Work {work_id: $wid}) RETURN w.title, w.work_type, w.jurisdiction",
            {"wid": wid},
        )
        if result.has_next():
            row = result.get_next()
            affected_works.append({
                "work_id": wid,
                "title": row[0],
                "work_type": row[1],
                "jurisdiction": row[2],
            })

    return {
        "action": action_meta,
        "terminated_expressions": terminated,
        "initiated_expressions": initiated,
        "affected_works": affected_works,
        "summary": {
            "provisions_terminated": len(terminated),
            "provisions_initiated": len(initiated),
            "works_affected": len(affected_works),
        },
    }


def _get_related_expressions(conn, action_id: str,
                             rel_type: str) -> list[dict]:
    """Get all Expression nodes connected to an Action via a relationship."""
    result = conn.execute(
        f"""
        MATCH (a:Action {{action_id: $aid}})-[:{rel_type}]->(e:Expression)
        RETURN e.expr_id, e.work_id, e.text_content, e.valid_from, e.valid_to
        """,
        {"aid": action_id},
    )

    expressions = []
    while result.has_next():
        row = result.get_next()
        expressions.append({
            "expr_id": row[0],
            "work_id": row[1],
            "text_content": row[2],
            "valid_from": row[3],
            "valid_to": row[4],
        })
    return expressions
