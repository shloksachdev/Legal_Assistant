"""LangChain tools for TempLex GraphRAG.

These tools wrap the deterministic graph retrieval functions from `templex.actions`
so the LLM can invoke them.
"""

from langchain_core.tools import tool
from templex.actions.resolve import resolve_item_reference
from templex.actions.temporal import get_valid_version, get_all_versions
from templex.actions.causality import trace_causality
from templex.actions.aggregate import aggregate_impact


@tool
def resolve_reference_tool(query: str, top_k: int = 5) -> str:
    """Resolve a natural language reference to a canonical Work ID.
    Use this FIRST when the user asks about a legal concept (like "sedition" or "murder") 
    to find the exact Work ID (e.g. IPC-124A).
    
    Args:
        query: Natural language description (e.g., "sedition law in India").
        top_k: Number of candidate Expressions to return.
    """
    result = resolve_item_reference(query, top_k)
    if not result:
        return "No matching provisions found."
    
    # Return a formatted string instead of raw dict for the LLM
    output = f"Best match: {result['title']} (Work ID: {result['work_id']})\n"
    output += f"Score: {result['score']:.4f}\n"
    output += f"Text Preview: {result['text_preview']}...\n\n"
    
    if len(result.get('all_candidates', [])) > 1:
        output += "Other candidates found:\n"
        for c in result['all_candidates'][1:]:
            output += f"- Work ID: {c['work_id']} (Score: {c['score']:.4f})\n"
            
    return output


@tool
def get_version_tool(work_id: str, target_date: str) -> str:
    """Fetch the exact text of a legal provision (Work ID) valid at a specific date.
    Use this when the user asks what the law was on a specific date.
    
    Args:
        work_id: Exact Work ID retrieved from resolve_reference_tool (e.g., "IPC-124A").
        target_date: ISO date string (YYYY-MM-DD, e.g., "2024-08-15").
    """
    result = get_valid_version(work_id, target_date)
    if not result:
        return f"No valid version found for {work_id} on {target_date}."
    
    if result.get("status") == "active":
        return f"Status: Active\nText: {result['text_content'][:800]}...\nValid From: {result['valid_from']}\nValid To: {result.get('valid_to', 'Present')}"
    elif result.get("status") == "not_yet_enacted":
        return result["message"]
    elif result.get("status") == "repealed":
        return f"{result['message']}\n\nLast active text:\n{result['last_text'][:800]}..."
    
    return str(result)


@tool
def trace_history_tool(work_id: str) -> str:
    """Reconstruct the complete legislative history of a legal provision.
    Use this when the user asks how a law has changed over time, what replaced it, or when it was enacted/repealed.
    
    Args:
        work_id: Exact Work ID retrieved from resolve_reference_tool (e.g., "IPC-124A").
    """
    
    # Try tracing the causality with the provided ID
    result = trace_causality(work_id)
    
    # If the LLM guessed a Work ID (like 'IPC-375') that isn't actually in the DB, 
    # the result will have an error. We catch this and auto-resolve it to the closest real ID!
    if "error" in result:
        # Pass the hallucinated ID down. The resolve_item_reference function
        # will now automatically append the necessary semantic context keywords itself!
        resolution = resolve_item_reference(work_id, top_k=1)
        if resolution and "work_id" in resolution:
            print(f"Auto-resolved '{work_id}' -> {resolution['work_id']} via semantic search")
            work_id = resolution["work_id"]
            result = trace_causality(work_id)
            
            # If it STILL errors, return the error
            if "error" in result:
                return result["error"]
        else:
            return result["error"]
        
    output = f"Legislative History for {result['work_title']} (Work ID: {result['work_id']})\n"
    output += f"Total Versions: {result['total_versions']}\n\n"
    
    for event in result.get("events", []):
        action = event.get("action")
        if action:
            output += f"--- Event: {action['effective_date']} ({action['action_type'].upper()}) ---\n"
            output += f"Action ID: {action['action_id']}\n"
            output += f"Source: {action['source_ref']}\n"
            output += f"Description: {action['description']}\n\n"
        
        # Prevent massive diffs from blowing up the context window / cutting off the LLM
        # Llama 3B Inference API limits are 4096 tokens. We must clamp it hard.
        if event.get("diff"):
            diff_text = event['diff']
            if len(diff_text) > 800:
                diff_text = diff_text[:800] + "\n...[DIFF TRUNCATED TO SAVE SPACE]..."
            output += f"Changes:\n```diff\n{diff_text}\n```\n\n"
        elif event.get("new_text"):
            new_text = event['new_text']
            if len(new_text) > 800:
                new_text = new_text[:800] + " ...[TEXT TRUNCATED]..."
            output += f"New Text:\n{new_text}\n\n"
            
    # Hard clamp the entire output as a final safety measure for the HuggingFace API limit
    if len(output) > 2500:
         output = output[:2500] + "\n\n...[HISTORY TRUNCATED DUE TO LENGTH LIMITS]..."
         
    return output


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
    output = f"Summary of {action.get('description')} ({action.get('effective_date')})\n"
    output += f"Action ID: {action.get('action_id')}\n"
    output += f"Source: {action.get('source_ref')}\n\n"
    
    summary = result.get("summary", {})
    output += f"Total Provisions Terminated: {summary.get('provisions_terminated')}\n"
    output += f"Total Provisions Initiated: {summary.get('provisions_initiated')}\n"
    output += f"Total Works Affected: {summary.get('works_affected')}\n\n"
    
    if result.get("terminated_expressions"):
        output += "Terminated Provisions:\n"
        for expr in result["terminated_expressions"]:
            output += f"- Work ID: {expr['work_id']}\n"
        output += "\n"
        
    if result.get("initiated_expressions"):
        output += "Initiated Provisions:\n"
        for expr in result["initiated_expressions"]:
            output += f"- Work ID: {expr['work_id']}\n"
            
    return output

# List of all available tools
TEMPLEX_TOOLS = [
    resolve_reference_tool,
    get_version_tool,
    trace_history_tool,
    aggregate_impact_tool
]
