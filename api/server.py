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
from templex.actions.scope import QueryScope
from templex.actions.resolve import resolve_item_reference
from templex.actions.temporal import get_valid_version, get_all_versions
from templex.actions.causality import trace_causality
from templex.actions.aggregate import aggregate_impact
from templex.db.connection import KuzuConnection
from templex.db.schema import initialize_schema
from templex.ingestion.graph_populator import load_seed_data
from templex.status import get_statuses, clear_statuses

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


class ScopePayload(BaseModel):
    reference_date: str | None = None
    domains: list[str] = []
    jurisdictions: list[str] = []


class NewSessionRequest(BaseModel):
    scope: ScopePayload | None = None


# ── Chat Endpoints ───────────────────────────────────────────────────────

@app.post("/api/chat/new")
async def create_session(req: NewSessionRequest | None = None):
    """Create a new chat session with optional scope."""
    scope = None
    if req and req.scope:
        scope = QueryScope(
            reference_date=req.scope.reference_date,
            domains=req.scope.domains,
            jurisdictions=req.scope.jurisdictions
        )
    
    session_id = chat_agent.create_session(scope=scope)
    return {"session_id": session_id}


@app.get("/api/scope/options")
async def get_scope_options():
    """Returns available filter options live from the graph."""
    conn = KuzuConnection.get_connection()
    
    # Fetch distinct values from the graph
    domains_res = conn.execute("MATCH (w:Work) RETURN DISTINCT w.domain")
    jurisd_res = conn.execute("MATCH (w:Work) RETURN DISTINCT w.jurisdiction")
    date_res = conn.execute("MATCH (e:Expression) RETURN MIN(e.valid_from), MAX(e.valid_from)")
    
    domains = []
    while domains_res.has_next():
        val = domains_res.get_next()[0]
        if val: domains.append(val)
        
    jurisdictions = []
    while jurisd_res.has_next():
        val = jurisd_res.get_next()[0]
        if val: jurisdictions.append(val)
        
    earliest = "1800-01-01"
    latest = "2024-07-01"
    if date_res.has_next():
        row = date_res.get_next()
        earliest = row[0] or earliest
        latest = row[1] or latest
        
    return {
        "domains": sorted(domains),
        "jurisdictions": sorted(jurisdictions),
        "date_range": {"earliest": earliest, "latest": latest}
    }


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


@app.get("/api/chat/status/{session_id}")
async def get_session_status(session_id: str):
    """Get the real-time execution logs for a session."""
    return {"logs": get_statuses(session_id)}


@app.post("/api/chat/status/clear/{session_id}")
async def clear_session_status(session_id: str):
    """Clear logs before starting a new chat turn."""
    clear_statuses(session_id)
    return {"status": "cleared"}


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
