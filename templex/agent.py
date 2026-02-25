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
from .llm.tools import TEMPLEX_TOOLS


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

        # Wrap the raw endpoint as a chat model so it uses the
        # provider's conversational interface instead of plain
        # text-generation.
        self._llm = ChatHuggingFace(llm=base_llm)

        self._sessions: Dict[str, List[ChatMessage]] = {}

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
            "4. 'aggregate_impact_tool': See everything a specific legislative Action (e.g. 'ACT-BNS-2024') changed. Args: {\"action_id\": \"<id>\"}\n\n"
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
            "FINAL ANSWER FORMATTING:\n"
            "Once you have gathered enough information using tools to answer the user's question, "
            "provide your final answer in rich, conversational natural language without any JSON.\n"
            "You MUST format your answer similarly to standard LLM responses with these guidelines:\n"
            "1. Start with a conversational introduction directly addressing the user's question.\n"
            "2. Use Markdown headings (e.g. `### Section 124A of the Indian Penal Code`) to divide topics.\n"
            "3. Provide the full historical context (when it was enacted, what the punishments were).\n"
            "4. Clearly explain the current transition or repeal status, detailing what replaced it (e.g. BNS sections) and its new punishments.\n"
            "5. Use bullet points for listing punishments, conditions, or key facts.\n"
            "6. Always ground your facts in the tool output, but write it fluidly as an expert legal assistant.\n"
        )

    # ── Session management -------------------------------------------------
    def create_session(self) -> str:
        """Create a new chat session and return its ID."""
        session_id = str(uuid4())
        self._sessions[session_id] = []
        return session_id

    def get_history(self, session_id: str) -> List[ChatMessage]:
        """Return the stored message history for a session."""
        return list(self._sessions.get(session_id, []))

    # ── Chat API -----------------------------------------------------------
    def chat(self, session_id: str, message: str) -> Dict[str, Any]:
        """Send a message in a session and get the model response.

        Returns a JSON‑serializable dict compatible with the existing frontend:
        {
          "response": <assistant text>,
          "tool_calls": <list>  # currently empty but kept for compatibility
        }
        """
        if not session_id:
            raise ValueError("session_id is required")

        if session_id not in self._sessions:
            # Auto‑create a session if the ID is unknown
            self._sessions[session_id] = []

        history = self._sessions[session_id]

        # Build LangChain message list: system + prior turns + new user message
        lc_messages: List[Any] = [SystemMessage(content=self._system_prompt)]

        for msg in history:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            else:
                lc_messages.append(AIMessage(content=msg["content"]))

        lc_messages.append(HumanMessage(content=message))

        # We will loop to support tool execution
        tool_calls_history = []
        max_iterations = 5
        
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
            assistant_text = "Sorry, I hit the maximum number of tool iterations without producing a final answer."

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

