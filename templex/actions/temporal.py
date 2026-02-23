"""getValidVersion — Deterministic point-in-time retrieval.

Given a Work ID and a target date, traverses the diachronic chain of
Component Temporal Versions to isolate the exact text legally active
on that specific date. 100% deterministic — no probabilistic inference.
"""

from templex.db.connection import KuzuConnection


def get_valid_version(work_id: str, target_date: str) -> dict | None:
    """Fetch the Expression (CTV) valid at a specific point in time.

    Args:
        work_id: Canonical Work ID (e.g., "IPC-124A").
        target_date: ISO date string (e.g., "2024-08-15").

    Returns:
        Dict with expr_id, text_content, valid_from, valid_to, or None.
    """
    conn = KuzuConnection.get_connection()

    # Retrieve all CTVs for this Work
    result = conn.execute(
        """
        MATCH (w:Work {work_id: $wid})-[:HAS_VERSION]->(e:Expression)
        RETURN e.expr_id, e.text_content, e.valid_from, e.valid_to
        ORDER BY e.valid_from
        """,
        {"wid": work_id},
    )

    versions = []
    while result.has_next():
        row = result.get_next()
        versions.append({
            "expr_id": row[0],
            "text_content": row[1],
            "valid_from": row[2],
            "valid_to": row[3],
        })

    if not versions:
        return None

    # Deterministic temporal filtering
    for v in versions:
        vf = v["valid_from"]
        vt = v["valid_to"]

        # Check: valid_from <= target_date AND (valid_to IS NULL or valid_to > target_date)
        if vf <= target_date:
            if not vt or vt == "" or vt > target_date:
                return {
                    "work_id": work_id,
                    "expr_id": v["expr_id"],
                    "text_content": v["text_content"],
                    "valid_from": v["valid_from"],
                    "valid_to": v["valid_to"],
                    "target_date": target_date,
                    "status": "active",
                }

    # If no version covers the target date, the provision didn't exist yet
    # or was fully repealed
    earliest = versions[0]["valid_from"]
    latest_to = versions[-1].get("valid_to", "")

    if target_date < earliest:
        return {
            "work_id": work_id,
            "status": "not_yet_enacted",
            "message": f"This provision was not enacted until {earliest}.",
        }

    if latest_to and target_date >= latest_to:
        return {
            "work_id": work_id,
            "status": "repealed",
            "repealed_on": latest_to,
            "message": f"This provision was repealed/replaced on {latest_to}.",
            "last_text": versions[-1]["text_content"],
        }

    return None


def get_all_versions(work_id: str) -> list[dict]:
    """Retrieve the full diachronic chain of all CTVs for a Work.

    Returns list of versions ordered chronologically.
    """
    conn = KuzuConnection.get_connection()
    result = conn.execute(
        """
        MATCH (w:Work {work_id: $wid})-[:HAS_VERSION]->(e:Expression)
        RETURN e.expr_id, e.text_content, e.valid_from, e.valid_to
        ORDER BY e.valid_from
        """,
        {"wid": work_id},
    )

    versions = []
    while result.has_next():
        row = result.get_next()
        versions.append({
            "expr_id": row[0],
            "text_content": row[1],
            "valid_from": row[2],
            "valid_to": row[3],
        })
    return versions
