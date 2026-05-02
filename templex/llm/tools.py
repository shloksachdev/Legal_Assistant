"""LangChain tools for TempLex GraphRAG.

These tools wrap the deterministic graph retrieval functions from `templex.actions`
so the LLM can invoke them.

Scope is injected per-session via set_session_scope() — the LLM never passes it
as an argument. This keeps tool signatures clean for the small LLM.
"""

from langchain_core.tools import tool
from templex.actions.resolve import resolve_item_reference
from templex.actions.temporal import get_valid_version, get_all_versions
from templex.actions.causality import trace_causality
from templex.actions.aggregate import aggregate_impact
from templex.llm.context_builder import ContextBuilder

# ── Session scope & ID — set by agent.py before each chat turn ──────────────────
_current_scope = None   # QueryScope | None
_current_session_id = "" # str


def set_session_state(session_id: str, scope) -> None:
    """Called by TempLexChatAgent before each tool execution turn."""
    global _current_scope, _current_session_id
    _current_scope = scope
    _current_session_id = session_id


def _get_scope():
    """Return the current session scope (may be None)."""
    return _current_scope


def _get_session_id():
    """Return the current session ID."""
    return _current_session_id


# ── Source formatting ──────────────────────────────────────────────────────────

def _format_source(source_ref: str) -> str:
    """Format a source_ref into a citation string for the LLM."""
    if not source_ref:
        return ""
    if source_ref.startswith("http"):
        return f"[{source_ref}]({source_ref})"
    return source_ref


# ── Tools ──────────────────────────────────────────────────────────────────────

@tool
def resolve_reference_tool(query: str, top_k: int = 5) -> str:
    """Resolve a natural language reference to a canonical Work ID.
    Use this FIRST when the user asks about a legal concept (like "sedition" or "murder")
    to find the exact Work ID (e.g. IPC-124A).

    Args:
        query: Natural language description (e.g., "sedition law in India").
        top_k: Number of candidate Expressions to return.
    """
    result = resolve_item_reference(query, top_k, scope=_get_scope())
    if not result:
        return "No matching provisions found."

    output = f"Best match: {result['title']} (Work ID: {result['work_id']})\n"
    if result.get("source_url"):
        output += f"Source URL: {result['source_url']}\n"
    output += f"Score: {result['score']:.4f} (raw: {result.get('raw_score', result['score']):.4f})\n"
    output += f"Text Preview: {result['text_preview']}...\n\n"

    if len(result.get("all_candidates", [])) > 1:
        output += "Other candidates found:\n"
        for c in result["all_candidates"][1:]:
            output += f"- Work ID: {c['work_id']} (Score: {c['score']:.4f})\n"

    return output


@tool
def get_version_tool(work_id: str, target_date: str = "") -> str:
    """Fetch the exact text of a legal provision (Work ID) valid at a specific date.
    Use this when the user asks what the law was on a specific date.
    If target_date is not provided, uses the session's reference date (default: today).

    Args:
        work_id:     Exact Work ID retrieved from resolve_reference_tool (e.g., "IPC-124A").
        target_date: ISO date string (YYYY-MM-DD). Leave empty to use session reference date.
    """
    from datetime import date as _date

    # Fall back to session reference date if not provided
    scope = _get_scope()
    if not target_date:
        target_date = scope.reference_date if scope else str(_date.today())

    result = get_valid_version(work_id, target_date)
    if not result:
        return f"No valid version found for {work_id} on {target_date}."

    if result.get("status") == "active":
        cb = ContextBuilder(max_chars=800)
        cb.add(result["text_content"], label=f"{work_id} (valid {result['valid_from']} – {result.get('valid_to', 'present')})")
        return cb.build()
    elif result.get("status") == "not_yet_enacted":
        return result["message"]
    elif result.get("status") == "repealed":
        cb = ContextBuilder(max_chars=800)
        cb.add(result.get("last_text", ""), label=f"Last active text of {work_id}")
        return f"{result['message']}\n\n{cb.build()}"

    return str(result)


@tool
def trace_history_tool(work_id: str, page: int = 1) -> str:
    """Reconstruct the complete legislative history of a legal provision.
    Use this when the user asks how a law has changed over time, what replaced it,
    or when it was enacted/repealed. History is always unrestricted — all periods
    are accessible regardless of the session scope.

    Args:
        work_id: Exact Work ID retrieved from resolve_reference_tool (e.g., "IPC-124A").
        page:    Page of history to retrieve (default 1, each page has 3 events).
    """
    # Auto-resolve if the Work ID is hallucinated
    result = trace_causality(work_id, page=page)

    if "error" in result:
        resolution = resolve_item_reference(work_id, top_k=1)
        if resolution and "work_id" in resolution:
            print(f"Auto-resolved '{work_id}' -> {resolution['work_id']} via semantic search")
            work_id = resolution["work_id"]
            result  = trace_causality(work_id, page=page)
            if "error" in result:
                return result["error"]
        else:
            return result["error"]

    cb = ContextBuilder(max_chars=2500)

    header = (
        f"Legislative History for {result['work_title']} (Work ID: {result['work_id']})\n"
        f"Total Versions: {result['total_versions']} | "
        f"Page {result['page']} of events (showing {len(result['events'])} of {result['total_events']} events)\n\n"
    )
    cb.add(header)

    for event in result.get("events", []):
        action = event.get("action")
        event_text = ""
        if action:
            event_text += f"--- Event: {action['effective_date']} ({action['action_type'].upper()}) ---\n"
            event_text += f"Action ID: {action['action_id']}\n"
            event_text += f"**CITE THIS SOURCE**: {_format_source(action['source_ref'])}\n"
            event_text += f"Description: {action['description']}\n\n"

        if event.get("diff"):
            diff_text = event["diff"][:600] + "\n...[DIFF TRUNCATED]..." if len(event["diff"]) > 600 else event["diff"]
            event_text += f"Changes:\n```diff\n{diff_text}\n```\n\n"
        elif event.get("new_text"):
            new_text = event["new_text"][:600] + " ...[TEXT TRUNCATED]..." if len(event["new_text"]) > 600 else event["new_text"]
            event_text += f"New Text:\n{new_text}\n\n"

        if not cb.add(event_text):
            break

    if result.get("has_more"):
        cb.add(f"\n[Page {page + 1} available — call trace_history_tool with page={page + 1} for more events]")

    return cb.build()


@tool
def aggregate_impact_tool(action_id: str) -> str:
    """Summarize the systemic impact of a legislative Action (a new law, amendment, or repeal).
    Use this to see EVERYTHING a specific act changed (what it repealed, what it introduced).

    Args:
        action_id: Action ID found via trace_history_tool (e.g., "ACT-BNS-2024").
    """
    result = aggregate_impact(action_id)
    if "error" in result:
        return result["error"]

    action = result.get("action", {})
    cb = ContextBuilder(max_chars=2000)

    header = (
        f"Summary of {action.get('description')} ({action.get('effective_date')})\n"
        f"Action ID: {action.get('action_id')}\n"
        f"**CITE THIS SOURCE**: {_format_source(action.get('source_ref', ''))}\n\n"
    )
    cb.add(header)

    summary = result.get("summary", {})
    stats = (
        f"Total Provisions Terminated: {summary.get('provisions_terminated')}\n"
        f"Total Provisions Initiated: {summary.get('provisions_initiated')}\n"
        f"Total Works Affected: {summary.get('works_affected')}\n\n"
    )
    cb.add(stats)

    if result.get("terminated_expressions"):
        cb.add("Terminated Provisions:\n" + "\n".join(
            f"- Work ID: {expr['work_id']}" for expr in result["terminated_expressions"]
        ) + "\n\n")

    if result.get("initiated_expressions"):
        cb.add("Initiated Provisions:\n" + "\n".join(
            f"- Work ID: {expr['work_id']}" for expr in result["initiated_expressions"]
        ))

    return cb.build()


@tool
def fetch_live_cases_tool(query: str, max_results: int = 3) -> str:
    """Search the live CourtListener database to fetch new cases.
    Use this ONLY for US law queries.
    Provide a highly precise boolean/technical legal query.
    """
    from templex.ingestion.graph_populator import ingest_from_courtlistener
    import contextlib
    import io

    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        ingest_from_courtlistener(query, max_results=max_results)

    stdout_output = f.getvalue()

    if "No opinions found" in stdout_output:
        return "No new live cases found for this query."

    return (
        f"Successfully fetched and ingested up to {max_results} live cases based on '{query}'. "
        f"You MUST now use resolve_reference_tool to search the local database for these new cases."
    )


@tool
def fetch_indian_cases_tool(queries: list[str], doctypes: str = "judgments,laws") -> str:
    """Run the High-Confidence Autonomous Research Pipeline for Indian Law.
    This tool will run multiple searches, re-rank the metadata locally, and automatically
    ingest the top 3 most relevant full-text documents into the local graph.

    Args:
        queries:  A list of 3-5 diverse boolean queries (e.g., ["sedition IPC 124A", "BNS section 152"]).
        doctypes: 'laws' for Acts/statutes, 'supremecourt' for SC judgments.
    """
    from templex.llm.research import ResearchPipeline

    if not queries:
        return "You must provide at least one query in the queries list."

    # Execute the autonomous pipeline
    result = ResearchPipeline.execute_indian_law_research(
        original_prompt=queries[0], # Use the first query as the baseline for re-ranking
        queries=queries,
        doctypes=doctypes,
        scope=_get_scope(),
        session_id=_get_session_id()
    )

    return result


@tool
def ingest_document_tool(tid: str, source: str = "indiankanoon") -> str:
    """Fetch and ingest the full text of a single legal document by its ID.
    Use this after fetch_indian_cases_tool to fetch the full text of a specific
    document that looks relevant. Only call for documents you actually need.

    Args:
        tid:    Document ID from fetch_indian_cases_tool result (e.g. "1234567").
        source: Data source — currently only "indiankanoon" is supported.
    """
    from templex.ingestion.indiankanoon import IndianKanoonClient
    from templex.ingestion.graph_populator import _ingest_seed_data, initialize_schema
    from templex.embeddings.engine import EmbeddingEngine
    from templex.config import INDIANKANOON_API_TOKEN

    if not INDIANKANOON_API_TOKEN:
        return "INDIANKANOON_API_TOKEN is not configured."

    client = IndianKanoonClient()

    # Fetch metadata + full text for this one document
    text_content = client.fetch_document_text(tid)
    if not text_content:
        return f"Could not fetch document text for tid={tid}."

    work_id  = f"IK-{tid}"
    expr_id  = f"IK-EXP-{tid}-1"
    action_id = f"ACT-IK-{tid}"
    source_url = f"https://indiankanoon.org/doc/{tid}/"

    new_data = {
        "works": [{
            "work_id":       work_id,
            "title":         f"Indian Kanoon Document {tid}",
            "jurisdiction":  "India",
            "work_type":     "judgment",
            "domain":        "other",
            "parent_work_id": "",
        }],
        "expressions": [{
            "expr_id":      expr_id,
            "work_id":      work_id,
            "text_content": text_content[:6000],
            "valid_from":   "1947-01-01",
            "valid_to":     "",
        }],
        "actions": [{
            "action_id":    action_id,
            "action_type":  "judgment",
            "description":  f"Indian Kanoon document {tid}",
            "effective_date": "1947-01-01",
            "source_ref":   source_url,
            "initiates":    [expr_id],
            "terminates":   [],
        }],
    }

    initialize_schema()
    _ingest_seed_data(new_data)

    return (
        f"Successfully fetched and ingested document tid={tid} from Indian Kanoon. "
        f"Source: {source_url}. "
        f"You MUST now use resolve_reference_tool to find it in the local database."
    )


# ── Tool registry ──────────────────────────────────────────────────────────────
TEMPLEX_TOOLS = [
    resolve_reference_tool,
    get_version_tool,
    trace_history_tool,
    aggregate_impact_tool,
    fetch_live_cases_tool,
    fetch_indian_cases_tool,
    ingest_document_tool,
]
