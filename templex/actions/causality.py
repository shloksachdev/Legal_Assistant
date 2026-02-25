"""traceCausality — Backward causal edge traversal with textual diff.

Reconstructs the complete legislative history of a provision by
traversing Action → Expression causal edges and computing exact
textual diffs between adjacent Component Temporal Versions.
"""

import difflib
from templex.db.connection import KuzuConnection
from templex.actions.temporal import get_all_versions


def trace_causality(work_id: str) -> dict:
    """Reconstruct the full legislative lineage of a Work, including cross-Work replacements.

    Args:
        work_id: Canonical Work ID (e.g., "IPC-376" or "BNS-63").

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

    # We will do a full graph traversal to find the "lineage family".
    # 1. Start with the given work_id's expressions.
    # 2. Look forward: What Action TERMINATED them, and what did that Action INITIATE?
    # 3. Look backward: What Action INITIATED them, and what did that Action TERMINATE?
    
    # First, let's just get the chain of expressions in chronological order for this specific work.
    # To keep it simple but support jumping to the new law, we'll traverse forward from the 
    # latest expression of the current work if it was terminated.
    
    versions = get_all_versions(work_id)
    if not versions:
        return {
            "work_id": work_id,
            "work_title": work_title,
            "error": "No versions found for this Work.",
        }

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
        "work_id": work_id
    })

    # Subsequent versions within the same Work
    for i in range(1, len(versions)):
        old_v = versions[i - 1]
        new_v = versions[i]

        action = _find_initiating_action(conn, new_v["expr_id"])
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
            "work_id": work_id
        })

    # NOW: Look for successor laws (e.g. BNS replacing IPC)
    # Get the last version we have
    last_v = versions[-1]
    
    # Did an Action TERMINATE this last expression?
    term_action = _find_terminating_action(conn, last_v["expr_id"])
    
    if term_action:
        # What did this Action INITIATE? (The successor laws)
        successors = _find_initiated_expressions(conn, term_action["action_id"])
        
        for succ in successors:
            diff = _compute_diff(last_v["text_content"], succ["text_content"])
            
            # Fetch the new Work's Title
            w_res = conn.execute("MATCH (w:Work {work_id: $wid}) RETURN w.title", {"wid": succ["work_id"]})
            succ_title = w_res.get_next()[0] if w_res.has_next() else succ["work_id"]
            
            events.append({
                "event_index": len(events),
                "action": term_action,
                "old_text": last_v["text_content"],
                "new_text": succ["text_content"],
                "diff": diff,
                "valid_from": succ["valid_from"],
                "valid_to": succ["valid_to"],
                "event_type": "replacement",
                "work_id": succ["work_id"],
                "notes": f"Replaced by {succ_title} ({succ['work_id']})"
            })

    # NOW: Look for predecessor laws (e.g. answering about BNS, tracing back to IPC)
    # If the user asked for BNS-63 directly, we should show its predecessor
    first_v = versions[0]
    if first_action:
        # What did the initiating action TERMINATE? (The predecessor laws)
        predecessors = _find_terminated_expressions(conn, first_action["action_id"])
        
        # Insert predecessors at the beginning of the events list
        pred_events = []
        for pred in predecessors:
            # We don't have the text *before* the predecessor easily here, 
            # so we just show the predecessor's text as the "old_text" leading up to our first_v
            diff = _compute_diff(pred["text_content"], first_v["text_content"])
            
            # Fetch the old Work's Title
            w_res = conn.execute("MATCH (w:Work {work_id: $wid}) RETURN w.title", {"wid": pred["work_id"]})
            pred_title = w_res.get_next()[0] if w_res.has_next() else pred["work_id"]
            
            pred_events.append({
                "event_index": -1, # Marker for pre-history
                "action": first_action,
                "old_text": pred["text_content"],
                "new_text": first_v["text_content"],
                "diff": diff,
                "valid_from": first_v["valid_from"],
                "valid_to": first_v["valid_to"],
                "event_type": "successor_of",
                "work_id": pred["work_id"],
                "notes": f"Replaced {pred_title} ({pred['work_id']})"
            })
            
        # Prepend to events
        events = pred_events + events

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

def _find_terminating_action(conn, expr_id: str) -> dict | None:
    """Find the Action node that TERMINATES a given Expression."""
    result = conn.execute(
        """
        MATCH (a:Action)-[:TERMINATES]->(e:Expression {expr_id: $eid})
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

def _find_initiated_expressions(conn, action_id: str) -> list[dict]:
    """Find all Expressions INITIATED by an Action."""
    result = conn.execute(
        """
        MATCH (a:Action {action_id: $aid})-[:INITIATES]->(e:Expression)
        RETURN e.expr_id, e.work_id, e.text_content, e.valid_from, e.valid_to
        """,
        {"aid": action_id},
    )
    
    exprs = []
    while result.has_next():
        row = result.get_next()
        exprs.append({
            "expr_id": row[0],
            "work_id": row[1],
            "text_content": row[2],
            "valid_from": row[3],
            "valid_to": row[4],
        })
    return exprs

def _find_terminated_expressions(conn, action_id: str) -> list[dict]:
    """Find all Expressions TERMINATED by an Action."""
    result = conn.execute(
        """
        MATCH (a:Action {action_id: $aid})-[:TERMINATES]->(e:Expression)
        RETURN e.expr_id, e.work_id, e.text_content, e.valid_from, e.valid_to
        """,
        {"aid": action_id},
    )
    
    exprs = []
    while result.has_next():
        row = result.get_next()
        exprs.append({
            "expr_id": row[0],
            "work_id": row[1],
            "text_content": row[2],
            "valid_from": row[3],
            "valid_to": row[4],
        })
    return exprs


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
