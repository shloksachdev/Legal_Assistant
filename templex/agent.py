"""Session-based chat agent for TempLex.

This provides a simple multi-turn chat model backed by a Hugging Face LLM.
It keeps per-session history so the model can answer follow‑up / cross
questions based on earlier answers (the “articles” in the output).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict
import json
import re
from uuid import uuid4

from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .config import HF_MODEL, HF_TOKEN
from .llm.tools import TEMPLEX_TOOLS, set_session_scope
from .actions.scope import QueryScope


Role = Literal["user", "assistant"]


class ToolCall(TypedDict, total=False):
    tool: str
    input: Any
    output_preview: str


class ChatMessage(TypedDict, total=False):
    role: Role
    content: str
    tool_calls: List[ToolCall]


class TempLexChatAgent:
    """Lightweight in‑memory chat agent with session history."""

    def __init__(self) -> None:
        if not HF_TOKEN:
            raise RuntimeError(
                "HF_TOKEN is not set. Please configure your Hugging Face token in the environment."
            )

        base_llm = HuggingFaceEndpoint(
            repo_id=HF_MODEL,
            huggingfacehub_api_token=HF_TOKEN,
            max_new_tokens=512,
            temperature=0.2,
        )

        self._llm = ChatHuggingFace(llm=base_llm)

        # Each session stores {"history": [...], "scope": QueryScope | None}
        self._sessions: Dict[str, Dict[str, Any]] = {}

        self._system_prompt = (
            "You are TempLex, a legal reasoning assistant that answers questions "
            "about legal provisions and their evolution over time. You have tools "
            "to search a deterministic graph database of legal changes.\n\n"
            "The conversation may include long excerpts of laws, cases, or other "
            "articles in earlier messages. Treat those earlier answers as the "
            "canonical 'article text' for this chat session and use them as your "
            "primary context when the user asks follow-up or cross questions.\n\n"
            "TOOLS AVAILABLE:\n"
            "1. 'resolve_reference_tool': Use this FIRST to find the exact Work ID (e.g. IPC-124A) based on a query (e.g. 'sedition' or 'rape'). Args: {\"query\": \"<search text>\"}\n"
            "2. 'get_version_tool': Fetch the exact text of a Work ID valid at a specific date. Args: {\"work_id\": \"<id>\", \"target_date\": \"<YYYY-MM-DD>\"}\n"
            "3. 'trace_history_tool': See the full legislative history (when it was enacted/repealed) of a Work ID. Args: {\"work_id\": \"<id>\"}\n"
            "4. 'aggregate_impact_tool': See everything a specific legislative Action (e.g. 'ACT-BNS-2024') changed. Args: {\"action_id\": \"<id>\"}\n"
            "5. 'fetch_indian_cases_tool': Fetch INDIAN law from Indian Kanoon (indiankanoon.org). Use this for ANY query about Indian constitutional law, IPC, BNS, Supreme Court/High Court judgments, or Indian statutes. Use ANDD/ORR/NOTT boolean operators. Set doctypes='laws' for Acts/statutes, 'supremecourt' for SC judgments. Example: {\"query\": \"44th amendment ANDD property right\", \"doctypes\": \"laws\"}. After fetch, immediately use 'resolve_reference_tool'.\n"
            "6. 'fetch_live_cases_tool': Fetch US case law from CourtListener. Use ONLY for US law queries. Args: {\"query\": \"<search string>\"}\n\n"
            "CRITICAL INSTRUCTIONS FOR TOOLS:\n"
            "- YOU MUST NEVER guess a 'work_id' (e.g. do not guess 'IPC Section 375').\n"
            "- YOU MUST ALWAYS use 'resolve_reference_tool' FIRST if you don't confidently know the exact hyphenated Work ID (e.g. IPC-376).\n"
            "HOW TO USE TOOLS:\n"
            "If you need to use a tool to look up information, YOU MUST output EXACTLY ONE JSON block wrapped in ```json tags with the tool name and arguments. Like this:\n"
            "```json\n"
            "{\n"
            "  \"tool\": \"resolve_reference_tool\",\n"
            "  \"args\": {\"query\": \"sedition\"}\n"
            "}\n"
            "```\n"
            "DO NOT output anything else except the JSON block when calling a tool.\n\n"
            "RESPONSE GUIDELINES:\n"
            "Your response shape should be DRIVEN by the user's question, not by a fixed template. Adapt:\n"
            "- If the user asks a simple factual question, give a direct, concise answer.\n"
            "- If the user asks for history or a trace, use headings and a timeline format.\n"
            "- If the user asks for a comparison, use a table or paired bullet points.\n"
            "- ALWAYS use Markdown for formatting (headings, bullets).\n"
            "- ALWAYS end with a '**Sources:**' section citing the '**CITE THIS SOURCE**' text from the tool output. NEVER invent URLs. If the source is plain text, cite it as plain text.\n"
            "- NEVER answer from your own knowledge if tools return no results. Say the data is not in the database.\n\n"
            "EXAMPLES (note how the shape changes based on the question type):\n"
            "---\n"
            "User: What is Article 21?\n"
            "TempLex:\n"
            "Article 21 of the Indian Constitution guarantees the **right to life and personal liberty**. No person shall be deprived of their life or personal liberty except according to a procedure established by law.\n\n"
            "Over the years, the Supreme Court has expanded its scope to include the right to livelihood, health, education, and a dignified life.\n\n"
            "**Sources:**\n"
            "- The Constitution of India, Part III\n"
            "---\n"
            "User: How did the law on rape change from IPC to BNS?\n"
            "TempLex:\n"
            "### Evolution of Rape Law: IPC Section 376 → BNS Section 63\n\n"
            "**1860 – Original IPC Section 376:**\n"
            "- Minimum 7 years rigorous imprisonment.\n"
            "- Aggravated cases (victim under 16): minimum 10 years.\n\n"
            "**2013 – Criminal Law Amendment (Post-Nirbhaya):**\n"
            "- Minimum raised to 10 years for all cases.\n"
            "- New aggravating categories added: police officers, armed forces, persons in positions of trust.\n\n"
            "**2024 – BNS Section 63 (IPC Replaced):**\n"
            "- Minimum 10 years retained.\n"
            "- Definition now explicitly includes **digital penetration**.\n"
            "- New aggravating category: crimes during communal or sectarian violence.\n\n"
            "**Sources:**\n"
            "- Criminal Law (Amendment) Act, 2013 (Act No. 13 of 2013)\n"
            "- Bharatiya Nyaya Sanhita, 2023 (Act No. 45 of 2023)\n"
        )

    # ── Session management -------------------------------------------------
    def create_session(self, scope: "QueryScope | None" = None) -> str:
        """Create a new chat session and return its ID."""
        from .actions.scope import QueryScope as _QueryScope
        session_id = str(uuid4())
        self._sessions[session_id] = {
            "history": [],
            "scope": scope,
        }
        return session_id

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Return the stored message history for a session."""
        session = self._sessions.get(session_id, {})
        return list(session.get("history", []))

    # ── Chat API -----------------------------------------------------------
    def chat(self, session_id: str, message: str) -> Dict[str, Any]:
        """Send a message in a session and get the model response."""
        if not session_id:
            raise ValueError("session_id is required")

        if session_id not in self._sessions:
            self._sessions[session_id] = {"history": [], "scope": None}

        session = self._sessions[session_id]
        history = session["history"]
        scope   = session.get("scope")  # QueryScope | None

        # Inject scope into tool layer so all tools use it automatically
        from .llm.tools import set_session_scope
        set_session_scope(scope)

        # Build scope-aware system prompt suffix
        scope_note = ""
        if scope:
            scope_note = (
                f"\n\nSESSION SCOPE: The user is viewing law as of {scope.reference_date}. "
                f"In-scope active results are ranked higher but all history and "
                f"cross-domain results remain accessible. {scope.describe()}"
            )

        # Build LangChain message list: system + prior turns + new user message
        lc_messages: List[Any] = [SystemMessage(content=self._system_prompt + scope_note)]

        for msg in history:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            else:
                lc_messages.append(AIMessage(content=msg["content"]))

        # Re-inject a SystemMessage reminder before EVERY user turn.
        # Small models (3B) suffer from "recency bias" — they mimic the style of the
        # most recent message in history instead of following the original system prompt.
        # Placing a fresh SystemMessage right before the new HumanMessage overrides this.
        lc_messages.append(SystemMessage(content=(
            "REMINDER — CRITICAL RULES FOR THIS TURN:\n"
            "1. ALWAYS use 'resolve_reference_tool' first to search the local database.\n"
            "2. If the local search fails ('No matching provisions found'), use 'fetch_live_cases_tool' with a precise boolean legal query.\n"
            "3. Format your final answer with: Markdown headings, bullet points for key facts, and clickable source links at the very bottom.\n"
            "4. Be EXTREMELY relevant to the user's exact question. Do NOT dump unrelated legal text.\n"
            "5. NEVER answer from internal knowledge if the tool returns no results."
        )))
        lc_messages.append(HumanMessage(content=message))

        # We will loop to support tool execution
        tool_calls_history = []
        max_iterations = 8
        courtlistener_fetched = False  # Track if we've already tried CourtListener for this turn
        
        for _ in range(max_iterations):
            # Call the LLM
            result = self._llm.invoke(lc_messages)
            
            assistant_text = getattr(result, "content", str(result))
            
            # Check if the LLM output a JSON tool call
            json_match = re.search(r"```json\s*(.*?)\s*```", assistant_text, re.DOTALL)
            
            if json_match:
                try:
                    tool_request = json.loads(json_match.group(1))
                    tool_name = tool_request.get("tool")
                    tool_args = tool_request.get("args", {})
                    
                    # Record the AI's tool request message in history
                    lc_messages.append(AIMessage(content=assistant_text))
                    
                    # Find and run the tool
                    tool_out = "Tool not found."
                    for t in TEMPLEX_TOOLS:
                        if t.name == tool_name:
                            try:
                                tool_out = t.invoke(tool_args)
                            except Exception as e:
                                tool_out = f"Error executing tool: {e}"
                            break
                            
                    # Record the call for the frontend
                    tool_calls_history.append({
                        "tool": tool_name,
                        "input": str(tool_args),
                        "output_preview": str(tool_out)[:100] + "..." if len(str(tool_out)) > 100 else str(tool_out)
                    })
                    
                    # HARD INTERCEPT: Stop the 3B model from hallucinating if retrieval fails
                    if tool_name == "resolve_reference_tool" and "No matching provisions found" in str(tool_out):
                        if not courtlistener_fetched:
                            courtlistener_fetched = True
                            # Route by jurisdiction: Indian queries → Indian Kanoon, US queries → CourtListener
                            observation = (
                                f"Tool '{tool_name}' returned: {tool_out}\n\n"
                                "SYSTEM COMMAND: The data is not in the local database. You must fetch it live.\n"
                                "JURISDICTION ROUTING RULES:\n"
                                "- If the query is about Indian law (Constitution, IPC, BNS, Indian SC/HC cases, Indian amendments) "
                                "→ use 'fetch_indian_cases_tool' with ANDD/ORR/NOTT operators and appropriate doctypes ('laws' for Acts, 'supremecourt' for SC judgments).\n"
                                "- If the query is about US law → use 'fetch_live_cases_tool'.\n"
                                "Do NOT attempt to answer yet. ONLY output the JSON tool call now."
                            )
                            lc_messages.append(HumanMessage(content=observation))
                            continue
                        else:
                            # Second miss AFTER a live fetch — data is genuinely unavailable
                            assistant_text = (
                                "I was unable to find relevant information about your query in either the local database "
                                "or the live data sources. The specific provision or case may not be indexed. "
                                "Please verify your query terms or try a more specific legal reference."
                            )
                            break
                    
                    # Append the tool message to our message list (as a human observation of the tool)
                    observation = f"Tool '{tool_name}' returned:\n{tool_out}\n\nBased on this, either use another tool, or provide your final answer."
                    lc_messages.append(HumanMessage(content=observation))
                    
                    # Loop back to let the LLM see the tool output and generate a final response
                    continue
                except json.JSONDecodeError:
                    lc_messages.append(AIMessage(content=assistant_text))
                    lc_messages.append(HumanMessage(content="Your JSON was malformed. Please fix it and try again, or provide your final answer."))
                    continue
            else:
                # No JSON found, this is the final textual response
                break
        else:
            # Force a final synthesis from whatever context was accumulated
            lc_messages.append(SystemMessage(content=(
                "You have used several tools. You MUST now stop calling tools and provide your "
                "final answer to the user's question based on the information gathered so far. "
                "Do NOT output any JSON. Write your final answer now."
            )))
            force_result = self._llm.invoke(lc_messages)
            assistant_text = getattr(force_result, "content", str(force_result))
            # If it's still a JSON tool call somehow, fall back gracefully
            if "```json" in assistant_text:
                assistant_text = "I gathered information but was unable to synthesize a final answer. Please try rephrasing your question."

        assistant_msg: ChatMessage = {
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": tool_calls_history,
        }

        # Update stored history
        history.append({"role": "user", "content": message})
        history.append(assistant_msg)

        return {
            "response": assistant_text,
            "tool_calls": tool_calls_history,
        }


# Singleton used by the FastAPI server and CLI
chat_agent = TempLexChatAgent()

