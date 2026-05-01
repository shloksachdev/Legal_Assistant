"""ContextBuilder — Token-budget context accumulator for TempLex tools.

Replaces raw [:N] slicing across all tools with a principled budget tracker.
Tools add chunks one at a time; the builder stops accepting once the budget
is exhausted and appends a pagination hint for the LLM.
"""

from __future__ import annotations


class ContextBuilder:
    """Accumulates tool output chunks up to a character budget.

    Usage
    -----
    cb = ContextBuilder(max_chars=2500)
    cb.add(event_text, label="Event 1")
    cb.add(event_text, label="Event 2")
    output = cb.build()   # Returns formatted string with pagination hint if truncated
    """

    def __init__(self, max_chars: int = 2500) -> None:
        self.max_chars = max_chars
        self._chunks: list[str] = []
        self._used: int = 0
        self.was_truncated: bool = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def add(self, text: str, label: str = "") -> bool:
        """Add a text chunk to the context.

        Parameters
        ----------
        text  : The text chunk to add (will be truncated if it partially fits).
        label : Optional section label prepended to the chunk.

        Returns
        -------
        bool — True if the full chunk was added, False if budget was exhausted.
        """
        if self.was_truncated:
            return False

        chunk = f"[{label}]\n{text}" if label else text
        available = self.max_chars - self._used

        if available <= 0:
            self.was_truncated = True
            return False

        if len(chunk) > available:
            # Partially fit this chunk
            chunk = chunk[:available] + "...[truncated]"
            self.was_truncated = True

        self._chunks.append(chunk)
        self._used += len(chunk)
        return not self.was_truncated

    def remaining(self) -> int:
        """Remaining character budget."""
        return max(0, self.max_chars - self._used)

    def build(self) -> str:
        """Return the accumulated context as a single formatted string.
        If truncated, appends a hint for the LLM to request the next page.
        """
        out = "\n\n".join(self._chunks)
        if self.was_truncated:
            out += "\n\n...[More results available — call the same tool with page=2 to continue]"
        return out

    def is_empty(self) -> bool:
        return len(self._chunks) == 0
