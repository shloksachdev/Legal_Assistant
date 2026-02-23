"""Structural parser for legal text hierarchy extraction.

Uses regex + heuristics to identify titles, chapters, articles,
sections, and paragraphs from semi-structured legal text.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ParsedWork:
    """Represents a parsed legal structural component."""
    work_id: str
    title: str
    work_type: str  # statute, title, chapter, article, section, paragraph
    text_content: str = ""
    children: list["ParsedWork"] = field(default_factory=list)


# ── Regex patterns for common legal structural markers ─────────────────────
PATTERNS = {
    "title": re.compile(
        r"^(?:TITLE|TÍTULO)\s+([IVXLCDM\d]+)[.\s—\-:]+(.+)$",
        re.IGNORECASE | re.MULTILINE,
    ),
    "chapter": re.compile(
        r"^(?:CHAPTER|CAPÍTULO)\s+([IVXLCDM\d]+)[.\s—\-:]+(.+)$",
        re.IGNORECASE | re.MULTILINE,
    ),
    "article": re.compile(
        r"^(?:Art(?:icle)?\.?|Section)\s+(\d+[A-Z]?)[.\s—\-:]+(.*)$",
        re.IGNORECASE | re.MULTILINE,
    ),
    "paragraph": re.compile(
        r"^\((\d+)\)\s+(.+)$",
        re.MULTILINE,
    ),
}


def parse_legal_text(text: str, base_id: str = "DOC",
                     jurisdiction: str = "Unknown") -> ParsedWork:
    """Parse raw legal text into a hierarchy of ParsedWork nodes.

    Args:
        text: Raw legal text content.
        base_id: Base identifier for work IDs.
        jurisdiction: Jurisdiction label.

    Returns:
        Root ParsedWork node with nested children.
    """
    root = ParsedWork(
        work_id=base_id,
        title=base_id,
        work_type="statute",
    )

    # Split text into lines and attempt structural parsing
    lines = text.strip().split("\n")
    current_parent = root
    current_text_buffer = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        matched = False
        for level, pattern in PATTERNS.items():
            match = pattern.match(line)
            if match:
                # Flush text buffer to current parent
                if current_text_buffer:
                    current_parent.text_content = " ".join(current_text_buffer)
                    current_text_buffer = []

                num = match.group(1)
                title_text = match.group(2).strip() if match.lastindex > 1 else ""
                child = ParsedWork(
                    work_id=f"{base_id}-{level[0].upper()}{num}",
                    title=f"{level.capitalize()} {num}" + (
                        f" - {title_text}" if title_text else ""
                    ),
                    work_type=level,
                )

                # Simple nesting: articles go under chapters, etc.
                if level in ("title", "chapter"):
                    root.children.append(child)
                    current_parent = child
                else:
                    current_parent.children.append(child)

                matched = True
                break

        if not matched:
            current_text_buffer.append(line)

    # Flush remaining buffer
    if current_text_buffer:
        current_parent.text_content = " ".join(current_text_buffer)

    return root
