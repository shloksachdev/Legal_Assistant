"""KuzuDB schema definition — LRMoo-inspired ontology for temporal legal modeling.

Node tables:
  - Work: Abstract, enduring legal concept (statute, article, section, paragraph)
  - Expression: Component Temporal Version (CTV) with exact validity interval + embedding
  - Action: First-class legislative event (enact, amend, repeal, replace)

Relationship tables:
  - HAS_PART: Hierarchical structure (Work → Work)
  - HAS_VERSION: Links Work to its temporal Expressions
  - TERMINATES: Action → Expression (marks end of CTV validity)
  - INITIATES: Action → Expression (marks start of CTV validity)
  - CAUSED_BY: Action → Action (legislative causality chain)
"""

from templex.db.connection import KuzuConnection


def initialize_schema():
    """Create all node and relationship tables if they don't exist."""
    conn = KuzuConnection.get_connection()

    # ── Node tables ───────────────────────────────────────────────────────
    _safe_execute(conn, """
        CREATE NODE TABLE IF NOT EXISTS Work (
            work_id STRING,
            title STRING,
            jurisdiction STRING,
            work_type STRING,
            parent_work_id STRING,
            PRIMARY KEY (work_id)
        )
    """)

    _safe_execute(conn, """
        CREATE NODE TABLE IF NOT EXISTS Expression (
            expr_id STRING,
            work_id STRING,
            text_content STRING,
            valid_from STRING,
            valid_to STRING,
            embedding FLOAT[384],
            PRIMARY KEY (expr_id)
        )
    """)

    _safe_execute(conn, """
        CREATE NODE TABLE IF NOT EXISTS Action (
            action_id STRING,
            action_type STRING,
            description STRING,
            effective_date STRING,
            source_ref STRING,
            PRIMARY KEY (action_id)
        )
    """)

    # ── Relationship tables ───────────────────────────────────────────────
    _safe_execute(conn, """
        CREATE REL TABLE IF NOT EXISTS HAS_PART (
            FROM Work TO Work
        )
    """)

    _safe_execute(conn, """
        CREATE REL TABLE IF NOT EXISTS HAS_VERSION (
            FROM Work TO Expression
        )
    """)

    _safe_execute(conn, """
        CREATE REL TABLE IF NOT EXISTS TERMINATES (
            FROM Action TO Expression
        )
    """)

    _safe_execute(conn, """
        CREATE REL TABLE IF NOT EXISTS INITIATES (
            FROM Action TO Expression
        )
    """)

    _safe_execute(conn, """
        CREATE REL TABLE IF NOT EXISTS CAUSED_BY (
            FROM Action TO Action
        )
    """)


def _safe_execute(conn, query: str):
    """Execute a query, ignoring errors for already-existing objects."""
    try:
        conn.execute(query)
    except RuntimeError:
        pass  # Table already exists
