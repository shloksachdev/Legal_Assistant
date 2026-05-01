"""Graph populator — maps parsed or seed data into KuzuDB's LRMoo schema.

Handles creation of Work, Expression (CTV), and Action nodes,
along with all hierarchical and causal relationship edges.
Generates embeddings for Expression nodes during ingestion.
"""

import json
from pathlib import Path
from templex.db.connection import KuzuConnection
from templex.db.schema import initialize_schema
from templex.embeddings.engine import EmbeddingEngine
from templex.config import SEED_DIR
from templex.ingestion.courtlistener import CourtListenerClient


def load_seed_data():
    """Load all seed data JSON files into KuzuDB."""
    initialize_schema()

    seed_files = list(SEED_DIR.glob("*.json"))
    for seed_file in seed_files:
        print(f"  Loading seed: {seed_file.name}")
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _ingest_seed_data(data)

    print(f"  ✓ Loaded {len(seed_files)} seed file(s)")


def ingest_from_courtlistener(query: str, max_results: int = 5):
    """Fetch opinions from CourtListener and ingest them natively into KuzuDB."""
    client = CourtListenerClient()
    if not client.is_available:
        print("[Error] COURTLISTENER_API_TOKEN is not configured in .env")
        return

    print(f"  Fetching cases from CourtListener for query: '{query}'")
    clusters = client.search_opinions(query, max_results=max_results)
    if not clusters:
        print("  No opinions found.")
        return

    new_data = {"works": [], "expressions": [], "actions": []}

    import concurrent.futures
    
    def process_cluster(cluster):
        if not cluster.get("opinions"):
            return None
            
        opinion_id = cluster["opinions"][0]["id"]
        opinion_data = client.fetch_opinion(opinion_id)
        if not opinion_data:
            return None

        work_id = f"CL-OP-{opinion_id}"
        expr_id = f"CL-EXP-{opinion_id}-1"
        action_id = f"ACT-CL-{opinion_id}"
        
        title = cluster.get("caseName", f"Court Opinion {opinion_id}")
        date_filed = cluster.get("dateFiled", "1970-01-01")
        
        # safely extract text
        text_content = opinion_data.get("plain_text")
        if not text_content:
            text_content = cluster["opinions"][0].get("snippet", "(No plain text available)")
            
        return {
            "work": {
                "work_id": work_id,
                "title": title,
                "jurisdiction": cluster.get("court", "Unknown"),
                "work_type": "opinion",
                "parent_work_id": ""
            },
            "expression": {
                "expr_id": expr_id,
                "work_id": work_id,
                "text_content": text_content,
                "valid_from": date_filed,
                "valid_to": ""
            },
            "action": {
                "action_id": action_id,
                "action_type": "judgment",
                "description": f"Judgment issued for {title}",
                "effective_date": date_filed,
                "source_ref": f"CourtListener ID {opinion_id}",
                "initiates": [expr_id],
                "terminates": []
            }
        }
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_results) as executor:
        results = list(executor.map(process_cluster, clusters))
        
    for res in results:
        if res:
            new_data["works"].append(res["work"])
            new_data["expressions"].append(res["expression"])
            new_data["actions"].append(res["action"])
        
    print(f"  Processing {len(new_data['works'])} downloaded opinions...")
    initialize_schema()
    _ingest_seed_data(new_data)
    print("  ✓ CourtListener data fully ingested.")


def _ingest_seed_data(data: dict):
    """Ingest a single seed data JSON document into the graph."""
    conn = KuzuConnection.get_connection()

    # ── Create Work nodes ─────────────────────────────────────────────
    for work in data.get("works", []):
        conn.execute(
            """
            MERGE (w:Work {work_id: $work_id})
            SET w.title = $title,
                w.jurisdiction = $jurisdiction,
                w.work_type = $work_type,
                w.parent_work_id = $parent_work_id
            """,
            {
                "work_id": work["work_id"],
                "title": work["title"],
                "jurisdiction": work["jurisdiction"],
                "work_type": work["work_type"],
                "parent_work_id": work.get("parent_work_id", ""),
            },
        )

    # ── Create HAS_PART edges (hierarchy) ─────────────────────────────
    for work in data.get("works", []):
        if work.get("parent_work_id"):
            try:
                conn.execute(
                    """
                    MATCH (parent:Work {work_id: $parent_id}),
                          (child:Work {work_id: $child_id})
                    MERGE (parent)-[:HAS_PART]->(child)
                    """,
                    {
                        "parent_id": work["parent_work_id"],
                        "child_id": work["work_id"],
                    },
                )
            except RuntimeError:
                pass  # Edge may already exist

    # ── Create Expression (CTV) nodes with embeddings ─────────────────
    expressions = data.get("expressions", [])
    if expressions:
        texts = [e["text_content"] for e in expressions]
        embeddings = EmbeddingEngine.encode_batch(texts)

        for expr, emb in zip(expressions, embeddings):
            emb_list = emb.tolist()
            conn.execute(
                """
                MERGE (e:Expression {expr_id: $expr_id})
                SET e.work_id = $work_id,
                    e.text_content = $text_content,
                    e.valid_from = $valid_from,
                    e.valid_to = $valid_to,
                    e.embedding = $embedding
                """,
                {
                    "expr_id": expr["expr_id"],
                    "work_id": expr["work_id"],
                    "text_content": expr["text_content"],
                    "valid_from": expr["valid_from"],
                    "valid_to": expr.get("valid_to", ""),
                    "embedding": emb_list,
                },
            )

            # ── HAS_VERSION edge: Work → Expression ───────────────────
            try:
                conn.execute(
                    """
                    MATCH (w:Work {work_id: $work_id}),
                          (e:Expression {expr_id: $expr_id})
                    MERGE (w)-[:HAS_VERSION]->(e)
                    """,
                    {
                        "work_id": expr["work_id"],
                        "expr_id": expr["expr_id"],
                    },
                )
            except RuntimeError:
                pass

    # ── Create Action nodes and causal edges ──────────────────────────
    for action in data.get("actions", []):
        conn.execute(
            """
            MERGE (a:Action {action_id: $action_id})
            SET a.action_type = $action_type,
                a.description = $description,
                a.effective_date = $effective_date,
                a.source_ref = $source_ref
            """,
            {
                "action_id": action["action_id"],
                "action_type": action["action_type"],
                "description": action["description"],
                "effective_date": action["effective_date"],
                "source_ref": action.get("source_ref", ""),
            },
        )

        # ── TERMINATES edges: Action → Expression ─────────────────────
        for expr_id in action.get("terminates", []):
            try:
                conn.execute(
                    """
                    MATCH (a:Action {action_id: $action_id}),
                          (e:Expression {expr_id: $expr_id})
                    MERGE (a)-[:TERMINATES]->(e)
                    """,
                    {"action_id": action["action_id"], "expr_id": expr_id},
                )
            except RuntimeError:
                pass

        # ── INITIATES edges: Action → Expression ──────────────────────
        for expr_id in action.get("initiates", []):
            try:
                conn.execute(
                    """
                    MATCH (a:Action {action_id: $action_id}),
                          (e:Expression {expr_id: $expr_id})
                    MERGE (a)-[:INITIATES]->(e)
                    """,
                    {"action_id": action["action_id"], "expr_id": expr_id},
                )
            except RuntimeError:
                pass
