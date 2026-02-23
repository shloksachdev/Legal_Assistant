"""traceCausality — Backward causal edge traversal with textual diff.

Reconstructs the complete legislative history of a provision by
traversing Action → Expression causal edges and computing exact
textual diffs between adjacent Component Temporal Versions.
"""

import difflib
from templex.db.connection import KuzuConnection
from templex.actions.temporal import get_all_versions


def trace_causality(work_id: str) -> dict:
    """Reconstruct the full legislative lineage of a Work.

    Args:
        work_id: Canonical Work ID (e.g., "BR-CF88-ART6").

    Returns:
        Dict with work title, version count, and ordered list of
        {action, old_text, new_text, diff, dates} entries.
    """
    conn = KuzuConnection.get_connection()

    # Get Work metadata
    work_result = conn.execute(
        "MATCH (w:Work {work_id: $wid}) RETURN w.title, w.jurisdiction",
        {"wid": work_id},
    )
    work_title = ""
    jurisdiction = ""
    if work_result.has_next():
        row = work_result.get_next()
        work_title = row[0]
        jurisdiction = row[1]

    # Get all versions chronologically
    versions = get_all_versions(work_id)
    if not versions:
        return {
            "work_id": work_id,
            "work_title": work_title,
            "error": "No versions found for this Work.",
        }

    # Build the causality chain
    events = []

    # First version: find the INITIATES action
    first_action = _find_initiating_action(conn, versions[0]["expr_id"])
    events.append({
        "event_index": 0,
        "action": first_action,
        "old_text": None,
        "new_text": versions[0]["text_content"],
        "diff": None,
        "valid_from": versions[0]["valid_from"],
        "valid_to": versions[0]["valid_to"],
        "event_type": "enactment",
    })

    # Subsequent versions: find TERMINATES/INITIATES action pairs and compute diffs
    for i in range(1, len(versions)):
        old_v = versions[i - 1]
        new_v = versions[i]

        # Find the Action that terminates the old version
        action = _find_initiating_action(conn, new_v["expr_id"])

        # Compute textual diff
        diff = _compute_diff(old_v["text_content"], new_v["text_content"])

        events.append({
            "event_index": i,
            "action": action,
            "old_text": old_v["text_content"],
            "new_text": new_v["text_content"],
            "diff": diff,
            "valid_from": new_v["valid_from"],
            "valid_to": new_v["valid_to"],
            "event_type": "amendment",
        })

    return {
        "work_id": work_id,
        "work_title": work_title,
        "jurisdiction": jurisdiction,
        "total_versions": len(versions),
        "events": events,
    }


def _find_initiating_action(conn, expr_id: str) -> dict | None:
    """Find the Action node that INITIATES a given Expression."""
    result = conn.execute(
        """
        MATCH (a:Action)-[:INITIATES]->(e:Expression {expr_id: $eid})
        RETURN a.action_id, a.action_type, a.description,
               a.effective_date, a.source_ref
        """,
        {"eid": expr_id},
    )

    if result.has_next():
        row = result.get_next()
        return {
            "action_id": row[0],
            "action_type": row[1],
            "description": row[2],
            "effective_date": row[3],
            "source_ref": row[4],
        }
    return None


def _compute_diff(old_text: str, new_text: str) -> str:
    """Compute a unified textual diff between two CTV texts."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="Previous Version",
        tofile="Current Version",
        lineterm="",
    )
    return "\n".join(diff)
