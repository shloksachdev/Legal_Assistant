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

from .config import get_hf_settings
from .llm.tools import TEMPLEX_TOOLS, set_session_scope
from .actions.scope import QueryScope
from .status import push_status


Role = Literal["user", "assistant"]


class ToolCall(TypedDict, total=False):
    tool: str
    input: Any
    output_preview: str


class ChatMessage(TypedDict, total=False):
    role: Role
    content: str
    tool_calls: List[ToolCall]


class OutputParser:
    """Clean and format LLM output for better readability."""
    
    @staticmethod
    def parse(text: str) -> str:
        """
        Clean output by:
        - Normalizing markdown headers
        - Adding consistent spacing between sections
        - Removing trailing/leading whitespace
        - Removing hash separators used as dividers
        """
        # Remove excessive hashes (#### and higher to ##)
        text = re.sub(r'^#{4,}', '##', text, flags=re.MULTILINE)
        
        # Add blank lines before headers for better spacing
        text = re.sub(r'\n(#{1,3} )', r'\n\n\1', text)
        
        # Normalize multiple blank lines to max 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Ensure proper spacing after code blocks
        text = re.sub(r'```\n([^\n])', r'```\n\n\1', text)
        
        # Clean up heading spacing (ensure blank line after headers)
        text = re.sub(r'(#{1,3} .+)\n([^\n])', r'\1\n\n\2', text)
        
        # Remove hash symbols used as separators (---# or #---)
        text = re.sub(r'\n\-{3,}#+\n', '\n\n', text)
        text = re.sub(r'\n#+\-{3,}\n', '\n\n', text)
        
        # Remove leading/trailing hash separators
        text = re.sub(r'^#+\s*\n', '', text)
        text = re.sub(r'\n\s*#+$', '', text)
        
        return text.strip()


class TempLexChatAgent:
    """Lightweight in‑memory chat agent with session history."""

    def __init__(self) -> None:
        self._hf_token = ""
        self._hf_model = ""
        self._model_candidates: List[str] = []
        self._llm: ChatHuggingFace | None = None
        self._current_model_idx = 0

        self._refresh_runtime_settings(force=True)

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
            "5. 'fetch_indian_cases_tool': Fetch INDIAN law from Indian Kanoon (indiankanoon.org). Use this for ANY query about Indian constitutional law, IPC, BNS, Supreme Court/High Court judgments, or Indian statutes. SPECULATIVE EXPANSION: You must provide an array of 3-5 diverse boolean queries (ANDD/ORR/NOTT) to ensure high recall. Example: {\"queries\": [\"sedition ANDD IPC 124A\", \"BNS section 152\", \"sedition supreme court landmark\"], \"doctypes\": \"laws\"}. After fetch, immediately use 'resolve_reference_tool'.\n"
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

    def _refresh_runtime_settings(self, force: bool = False) -> None:
        token, model, fallback_models = get_hf_settings()

        candidates: List[str] = []
        for candidate in [model, *fallback_models]:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        should_rebuild = (
            force
            or token != self._hf_token
            or candidates != self._model_candidates
            or self._llm is None
        )

        self._hf_token = token
        self._hf_model = model
        self._model_candidates = candidates

        if should_rebuild:
            self._current_model_idx = 0
            self._llm = self._build_llm(self._model_candidates[0]) if self._model_candidates and self._hf_token else None

    def _ensure_llm(self) -> None:
        self._refresh_runtime_settings()
        if self._llm is None:
            raise RuntimeError(
                "HF_TOKEN is not set. Add it to .env and restart the backend, then try again."
            )

    def _build_llm(self, model_id: str, custom_token: str | None = None) -> ChatHuggingFace:
        token = custom_token or self._hf_token
        if not token:
            raise RuntimeError("HF_TOKEN is not set.")
        base_llm = HuggingFaceEndpoint(
            repo_id=model_id,
            huggingfacehub_api_token=token,
            max_new_tokens=512,
            temperature=0.2,
            timeout=45,
        )
        return ChatHuggingFace(llm=base_llm)

    def _get_current_llm(self, custom_token: str | None = None) -> ChatHuggingFace:
        if custom_token:
            return self._build_llm(self._model_candidates[self._current_model_idx], custom_token)
        self._ensure_llm()
        return self._llm

    def _try_switch_model(self, custom_token: str | None = None) -> ChatHuggingFace | None:
        if self._current_model_idx + 1 >= len(self._model_candidates):
            return None
        self._current_model_idx += 1
        if not custom_token:
            self._llm = self._build_llm(self._model_candidates[self._current_model_idx])
            return self._llm
        return self._build_llm(self._model_candidates[self._current_model_idx], custom_token)

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
    def chat(self, session_id: str, message: str, custom_token: str | None = None) -> Dict[str, Any]:
        """Send a message in a session and get the model response."""
        if not session_id:
            raise ValueError("session_id is required")

        current_llm = self._get_current_llm(custom_token)

        if session_id not in self._sessions:
            self._sessions[session_id] = {"history": [], "scope": None}

        session = self._sessions[session_id]
        history = session["history"]
        scope   = session.get("scope")  # QueryScope | None

        # Inject scope into tool layer so all tools use it automatically
        from .llm.tools import set_session_scope
        set_session_scope(scope, session_id=session_id)
        push_status(session_id, "Processing prompt...")

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
            "2. If the query is about Indian law and the local search fails, use 'fetch_indian_cases_tool' first, then 'ingest_document_tool' for the most relevant tid.\n"
            "3. If the query is about US law and the local search fails, use 'fetch_live_cases_tool'.\n"
            "4. Format your final answer with: Markdown headings, bullet points for key facts, and clickable source links at the very bottom.\n"
            "5. Be EXTREMELY relevant to the user's exact question. Do NOT dump unrelated legal text.\n"
            "6. NEVER answer from internal knowledge if the tool returns no results."
        )))
        lc_messages.append(HumanMessage(content=message))

        # We will loop to support tool execution
        tool_calls_history = []
        max_iterations = 8
        courtlistener_fetched = False  # Track if we've already tried CourtListener for this turn
        
        for _ in range(max_iterations):
            # Call the LLM
            try:
                result = current_llm.invoke(lc_messages)
            except Exception as exc:
                err_text = str(exc)
                if "model_not_supported" in err_text or "not supported by any provider" in err_text:
                    new_llm = self._try_switch_model(custom_token)
                    if new_llm:
                        current_llm = new_llm
                        continue
                raise
            
            assistant_text = getattr(result, "content", str(result))
            
            # Check if the LLM output a JSON tool call
            json_match = re.search(r"```json\s*(.*?)\s*```", assistant_text, re.DOTALL)
            
            if json_match:
                try:
                    tool_request = json.loads(json_match.group(1))
                    tool_name = tool_request.get("tool")
                    tool_args = tool_request.get("args", {})
                    
                    push_status(session_id, f"Executing tool: {tool_name}...")
                    
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
                            # Route by jurisdiction: Indian queries → autonomous_research_tool (full pipeline),
                            # US queries → fetch_live_cases_tool
                            observation = (
                                f"Tool '{tool_name}' returned: {tool_out}\n\n"
                                "SYSTEM COMMAND: The data is not in the local database. You must fetch it live.\n"
                                "JURISDICTION ROUTING RULES:\n"
                                "- If the query is about Indian law (Constitution, IPC, BNS, Indian SC/HC cases, Indian amendments) "
                                "→ use 'autonomous_research_tool' with the user's original question. "
                                "This will automatically expand queries, fetch metadata, re-rank with confidence scoring, "
                                "and ingest only the highest-quality documents.\n"
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
                    push_status(session_id, "Analyzing tool results...")
                    
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
            force_result = current_llm.invoke(lc_messages)
            assistant_text = getattr(force_result, "content", str(force_result))
            # If it's still a JSON tool call somehow, fall back gracefully
            if "```json" in assistant_text:
                assistant_text = "I gathered information but was unable to synthesize a final answer. Please try rephrasing your question."

        # Apply output parser for better formatting
        # assistant_text = OutputParser.parse(assistant_text)
        
        assistant_msg: ChatMessage = {
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": tool_calls_history,
        }

        # Update stored history
        history.append({"role": "user", "content": message})
        history.append(assistant_msg)

        # ── Generate follow-up suggestions ────────────────────────────────
        suggestions = []
        try:
            push_status(session_id, "Generating follow-up suggestions...")
            suggest_messages = [
                SystemMessage(content=(
                    "Based on the conversation, generate exactly 3 short follow-up questions "
                    "the user might ask next. Output ONLY a JSON array of 3 strings, nothing else. "
                    "Example: [\"What replaced this law?\", \"Show the full timeline\", \"Compare with BNS\"]"
                )),
                HumanMessage(content=f"User asked: {message}\n\nAssistant answered: {assistant_text[:500]}"),
            ]
            suggest_result = self._invoke_with_retry(suggest_messages)
            suggest_text = getattr(suggest_result, "content", "")
            # Extract JSON array from response
            arr_match = re.search(r'\[.*?\]', suggest_text, re.DOTALL)
            if arr_match:
                parsed = json.loads(arr_match.group())
                if isinstance(parsed, list):
                    suggestions = [str(s).strip() for s in parsed[:3] if s]
        except Exception as e:
            print(f"  [TempLex] Suggestion generation failed (non-critical): {e}")

        # ── Collect structured timeline data from tool calls ──────────────
        timeline = None
        for tc in tool_calls_history:
            if tc["tool"] == "trace_history_tool":
                # Re-run to get structured data (the tool output in history is text)
                try:
                    from .actions.causality import trace_causality
                    trace_args = tc.get("input", "{}")
                    if isinstance(trace_args, str):
                        trace_args = json.loads(trace_args.replace("'", '"'))
                    work_id = trace_args.get("work_id", "")
                    if work_id:
                        timeline = trace_causality(work_id)
                except Exception:
                    pass
                break

        return {
            "response": assistant_text,
            "tool_calls": tool_calls_history,
            "suggestions": suggestions,
            "timeline": timeline,
        }

    # ── Streaming Chat API ------------------------------------------------
    def chat_stream(self, session_id: str, message: str, custom_token: str | None = None):
        """Generator version of chat() that yields chunks for SSE streaming.

        Yields dicts with:
          {"type": "token",     "content": "..."}      — text chunk
          {"type": "tool_call", "tool": "...", ...}     — tool invocation event
          {"type": "done",      "content": "...", ...}  — final signal
        """
        if not session_id:
            raise ValueError("session_id is required")

        current_llm = self._get_current_llm(custom_token)

        if session_id not in self._sessions:
            self._sessions[session_id] = {"history": [], "scope": None}

        session = self._sessions[session_id]
        history = session["history"]
        scope   = session.get("scope")

        from .llm.tools import set_session_scope
        set_session_scope(scope, session_id=session_id)

        scope_note = ""
        if scope:
            scope_note = (
                f"\n\nSESSION SCOPE: The user is viewing law as of {scope.reference_date}. "
                f"In-scope active results are ranked higher but all history and "
                f"cross-domain results remain accessible. {scope.describe()}"
            )

        from .status import push_status
        import time

        sys_len = len(self._system_prompt + scope_note)
        push_status(session_id, f"Built context: {len(history)} prior turns, {sys_len} char system prompt")

        lc_messages: List[Any] = [SystemMessage(content=self._system_prompt + scope_note)]

        for msg in history:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            else:
                lc_messages.append(AIMessage(content=msg["content"]))

        lc_messages.append(SystemMessage(content=(
            "REMINDER — CRITICAL RULES FOR THIS TURN:\n"
            "1. ALWAYS use 'resolve_reference_tool' first to search the local database.\n"
                "2. If the query is about Indian law and the local search fails, use 'fetch_indian_cases_tool' first, then 'ingest_document_tool' for the most relevant tid.\n"
                "3. If the query is about US law and the local search fails, use 'fetch_live_cases_tool'.\n"
                "4. Format your final answer with: Markdown headings, bullet points for key facts, and clickable source links at the very bottom.\n"
                "5. Be EXTREMELY relevant to the user's exact question. Do NOT dump unrelated legal text.\n"
                "6. NEVER answer from internal knowledge if the tool returns no results."
        )))
        lc_messages.append(HumanMessage(content=message))

        tool_calls_history = []
        max_iterations = 8
        courtlistener_fetched = False
        assistant_text = ""
        model_name = getattr(current_llm, "model", "LLM")

        for iteration in range(1, max_iterations + 1):
            push_status(session_id, f"Calling {model_name} (pass {iteration}, {len(lc_messages)} messages)...")
            t0 = time.time()
            try:
                result = current_llm.invoke(lc_messages)
            except Exception as exc:
                err_text = str(exc)
                if "model_not_supported" in err_text or "not supported by any provider" in err_text:
                    new_llm = self._try_switch_model(custom_token)
                    if new_llm:
                        current_llm = new_llm
                        push_status(session_id, "Model limit reached, switching model...")
                        continue
                push_status(session_id, f"LLM Error: {err_text[:100]}")
                raise
            
            elapsed = time.time() - t0
            assistant_text = getattr(result, "content", str(result))
            push_status(session_id, f"LLM responded in {elapsed:.1f}s ({len(assistant_text)} chars)")

            json_match = re.search(r"```json\s*(.*?)\s*```", assistant_text, re.DOTALL)

            if json_match:
                try:
                    tool_request = json.loads(json_match.group(1))
                    tool_name = tool_request.get("tool")
                    tool_args = tool_request.get("args", {})

                    lc_messages.append(AIMessage(content=assistant_text))
                    yield {"type": "tool_call", "tool": tool_name, "input": str(tool_args)}
                    
                    args_str = json.dumps(tool_args)[:40] + "..." if len(json.dumps(tool_args)) > 40 else json.dumps(tool_args)
                    push_status(session_id, f"Tool call: {tool_name}({args_str})")

                    t0_tool = time.time()
                    tool_out = "Tool not found."
                    for t in TEMPLEX_TOOLS:
                        if t.name == tool_name:
                            try:
                                tool_out = t.invoke(tool_args)
                            except Exception as e:
                                tool_out = f"Error executing tool: {e}"
                            break
                    t_elapsed = time.time() - t0_tool

                    tool_out_str = str(tool_out)
                    preview = tool_out_str.replace("\n", " ")[:60] + "..." if len(tool_out_str) > 60 else tool_out_str
                    push_status(session_id, f"← {tool_name} returned in {t_elapsed:.1f}s: {preview}")

                    tool_calls_history.append({
                        "tool": tool_name,
                        "input": str(tool_args),
                        "output_preview": tool_out_str[:100] + "..." if len(tool_out_str) > 100 else tool_out_str
                    })

                    if tool_name == "resolve_reference_tool" and "No matching provisions found" in tool_out_str:
                        if not courtlistener_fetched:
                            courtlistener_fetched = True
                            observation = (
                                f"Tool '{tool_name}' returned: {tool_out}\n\n"
                                "SYSTEM COMMAND: The data is not in the local database. You must fetch it live.\n"
                                "JURISDICTION ROUTING RULES:\n"
                                "- If the query is about Indian law → use 'autonomous_research_tool' with the user's original question.\n"
                                "- If the query is about US law → use 'fetch_live_cases_tool'.\n"
                                "Do NOT attempt to answer yet. ONLY output the JSON tool call now."
                            )
                            lc_messages.append(HumanMessage(content=observation))
                            push_status(session_id, "Local search failed. Routing to autonomous research.")
                            continue
                        else:
                            assistant_text = (
                                "I was unable to find relevant information about your query in either the local database "
                                "or the live data sources."
                            )
                            break

                    observation = f"Tool '{tool_name}' returned:\n{tool_out}\n\nBased on this, either use another tool, or provide your final answer."
                    lc_messages.append(HumanMessage(content=observation))
                    push_status(session_id, f"Feeding {len(observation)} chars of tool output back to LLM...")
                    continue
                except json.JSONDecodeError:
                    lc_messages.append(AIMessage(content=assistant_text))
                    lc_messages.append(HumanMessage(content="Your JSON was malformed. Please fix it and try again, or provide your final answer."))
                    push_status(session_id, "Malformed JSON detected, requesting LLM fix...")
                    continue
            else:
                break
        else:
            lc_messages.append(SystemMessage(content=(
                "You have used several tools. You MUST now stop calling tools and provide your "
                "final answer to the user's question based on the information gathered so far. "
                "Do NOT output any JSON. Write your final answer now."
            )))
            push_status(session_id, f"Calling {model_name} (final pass)...")
            t0 = time.time()
            try:
                force_result = current_llm.invoke(lc_messages)
            except Exception as exc:
                new_llm = self._try_switch_model(custom_token)
                if new_llm:
                    current_llm = new_llm
                    force_result = current_llm.invoke(lc_messages)
                else:
                    raise
            elapsed = time.time() - t0
            assistant_text = getattr(force_result, "content", str(force_result))
            push_status(session_id, f"LLM responded in {elapsed:.1f}s ({len(assistant_text)} chars)")
            
            if "```json" in assistant_text:
                assistant_text = "I gathered information but was unable to synthesize a final answer. Please try rephrasing your question."

        # Apply output parser for better formatting
        # assistant_text = OutputParser.parse(assistant_text)
        
        push_status(session_id, f"Streaming final response ({len(assistant_text)} chars)...")
        
        # Stream the final text in chunks
        chunk_size = 12
        for i in range(0, len(assistant_text), chunk_size):
            yield {"type": "token", "content": assistant_text[i:i + chunk_size]}

        # Store in history
        assistant_msg: ChatMessage = {
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": tool_calls_history,
        }
        history.append({"role": "user", "content": message})
        history.append(assistant_msg)

        yield {"type": "done", "content": assistant_text, "tool_calls": tool_calls_history}


# Singleton used by the FastAPI server and CLI
chat_agent = TempLexChatAgent()

