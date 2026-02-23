"""Session-based chat agent for TempLex.

This provides a simple multi-turn chat model backed by a Hugging Face LLM.
It keeps per-session history so the model can answer follow‑up / cross
questions based on earlier answers (the “articles” in the output).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict
from uuid import uuid4

from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .config import HF_MODEL, HF_TOKEN


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
            "about legal provisions and their evolution over time.\n\n"
            "The conversation may include long excerpts of laws, cases, or other "
            "articles in earlier messages. Treat those earlier answers as the "
            "canonical 'article text' for this chat session and use them as your "
            "primary context when the user asks follow‑up or cross questions.\n\n"
            "Requirements:\n"
            "- Always ground your answers in the information already shown in the "
            "  conversation whenever possible.\n"
            "- When the user asks a cross question (e.g. 'what about clause (b)?', "
            "  'compare with the previous article', 'summarise the above'), infer "
            "  what they are referring to from prior messages and answer based on "
            "  that context.\n"
            "- If something is not present in the conversation so far, say that it "
            "  is not available instead of inventing details.\n"
            "- Respond in clear, structured paragraphs and use bullet points where helpful."
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

        # Call the LLM
        result = self._llm.invoke(lc_messages)
        if isinstance(result, AIMessage):
            assistant_text = result.content
        else:
            # Fallback for older / different return types
            assistant_text = getattr(result, "content", str(result))

        assistant_msg: ChatMessage = {
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": [],
        }

        # Update stored history so the model can answer cross‑questions later
        history.append({"role": "user", "content": message})
        history.append(assistant_msg)

        return {
            "response": assistant_text,
            "tool_calls": [],
        }


# Singleton used by the FastAPI server and CLI
chat_agent = TempLexChatAgent()

