"""FastAPI server — REST + Chat API for TempLex GraphRAG.

Endpoints:
  POST /api/chat        — Send a chat message (multi-turn)
  POST /api/chat/new    — Create a new session
  GET  /api/chat/history/{session_id} — Get message history
  POST /api/query       — Legacy single-shot query
  GET  /api/schema      — Graph statistics
  POST /api/seed        — Load seed data
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from templex.agent import TempLexChatAgent, chat_agent
from templex.actions.resolve import resolve_item_reference
from templex.actions.temporal import get_valid_version, get_all_versions
from templex.actions.causality import trace_causality
from templex.actions.aggregate import aggregate_impact
from templex.db.connection import KuzuConnection
from templex.db.schema import initialize_schema
from templex.ingestion.graph_populator import load_seed_data

app = FastAPI(
    title="TempLex GraphRAG",
    description="Deterministic Temporal Legal Reasoning Chat Agent API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response models ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class QueryRequest(BaseModel):
    query: str
    date: str | None = None


class ResolveRequest(BaseModel):
    query: str


class VersionRequest(BaseModel):
    work_id: str
    target_date: str


class TraceRequest(BaseModel):
    work_id: str


class AggregateRequest(BaseModel):
    action_id: str


# ── Chat Endpoints ───────────────────────────────────────────────────────

@app.post("/api/chat/new")
async def create_session():
    """Create a new chat session."""
    session_id = chat_agent.create_session()
    return {"session_id": session_id}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send a message and get a conversational response."""
    try:
        result = chat_agent.chat(req.session_id, req.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/history/{session_id}")
async def get_history(session_id: str):
    """Get message history for a session."""
    messages = chat_agent.get_history(session_id)
    return {"session_id": session_id, "messages": messages}


# ── Direct Action Endpoints (kept for programmatic access) ───────────────

@app.post("/api/resolve")
async def resolve_reference(req: ResolveRequest):
    """Resolve a natural language reference to a Work ID."""
    result = resolve_item_reference(req.query)
    if result is None:
        raise HTTPException(status_code=404, detail="No matching provision found.")
    return result


@app.post("/api/version")
async def get_version(req: VersionRequest):
    """Get the text valid at a specific date."""
    result = get_valid_version(req.work_id, req.target_date)
    if result is None:
        raise HTTPException(status_code=404, detail="No version found.")
    return result


@app.post("/api/trace")
async def trace_work(req: TraceRequest):
    """Trace the full legislative lineage of a Work."""
    result = trace_causality(req.work_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/aggregate")
async def aggregate_action(req: AggregateRequest):
    """Aggregate the impact of a legislative action."""
    result = aggregate_impact(req.action_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/schema")
async def get_schema_stats():
    """Get graph statistics."""
    conn = KuzuConnection.get_connection()
    work_count = _count(conn, "MATCH (w:Work) RETURN count(w)")
    expr_count = _count(conn, "MATCH (e:Expression) RETURN count(e)")
    action_count = _count(conn, "MATCH (a:Action) RETURN count(a)")

    return {
        "nodes": {
            "works": work_count,
            "expressions": expr_count,
            "actions": action_count,
            "total": work_count + expr_count + action_count,
        },
        "status": "connected",
    }


@app.post("/api/seed")
async def seed_database():
    """Load seed data into the graph."""
    try:
        load_seed_data()
        stats = await get_schema_stats()
        return {"message": "Seed data loaded successfully.", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup():
    """Initialize schema on server start."""
    initialize_schema()


def _count(conn, query: str) -> int:
    result = conn.execute(query)
    if result.has_next():
        return result.get_next()[0]
    return 0
