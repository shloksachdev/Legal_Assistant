"""QueryScope — Session scope context for TempLex Graph RAG.

Stores the user's selected reference date, domains, and jurisdictions.
Applies additive relevance boosts during re-ranking in resolve_item_reference().
Nothing is ever excluded — boosts are purely additive to the cosine similarity score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from templex.config import (
    SCOPE_BOOST_DOMAIN,
    SCOPE_BOOST_JURISDICTION,
    SCOPE_BOOST_VALIDITY,
)


@dataclass
class QueryScope:
    """Holds the user's scope preferences for a chat session.

    Attributes
    ----------
    reference_date:  ISO date string (YYYY-MM-DD).
        The point-in-time anchor. Expressions ACTIVE on this date get a
        validity boost. Defaults to today, meaning "current law".
    domains:         List of legal domains the user is interested in
        (e.g. ["criminal", "constitutional"]). Empty = all domains, no boost.
    jurisdictions:   List of jurisdictions (e.g. ["India"]). Empty = all, no boost.
    """

    reference_date: str = ""          # set in __post_init__
    domains:        list[str] = field(default_factory=list)
    jurisdictions:  list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.reference_date:
            self.reference_date = str(date.today())

    # ── Core boost method ──────────────────────────────────────────────────────

    def apply_boost(self, candidate: dict) -> float:
        """Compute the boosted score for a candidate expression.

        Parameters
        ----------
        candidate : dict with keys:
            raw_score    (float)  — cosine similarity score before boost
            valid_from   (str)    — ISO date when expression became active
            valid_to     (str)    — ISO date when expression was terminated ("" = still active)
            domain       (str)    — legal domain of the parent Work
            jurisdiction (str)    — jurisdiction of the parent Work

        Returns
        -------
        float — boosted score (raw_score + applicable bonuses)
        """
        score = candidate.get("raw_score", 0.0)

        # ── Validity boost: was this expression the ACTIVE law on reference_date? ──
        vf = candidate.get("valid_from", "")
        vt = candidate.get("valid_to", "")
        is_active_on_ref_date = (
            bool(vf) and vf <= self.reference_date
            and (not vt or vt > self.reference_date)
        )
        if is_active_on_ref_date:
            score += SCOPE_BOOST_VALIDITY

        # ── Domain boost ──────────────────────────────────────────────────────
        if self.domains and candidate.get("domain") in self.domains:
            score += SCOPE_BOOST_DOMAIN

        # ── Jurisdiction boost ────────────────────────────────────────────────
        if self.jurisdictions and candidate.get("jurisdiction") in self.jurisdictions:
            score += SCOPE_BOOST_JURISDICTION

        return score

    # ── Helpers ────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize for storage in session dict or API response."""
        return {
            "reference_date": self.reference_date,
            "domains":        self.domains,
            "jurisdictions":  self.jurisdictions,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QueryScope":
        """Deserialize from a dict (e.g. from API request body)."""
        return cls(
            reference_date=d.get("reference_date", str(date.today())),
            domains=d.get("domains", []),
            jurisdictions=d.get("jurisdictions", []),
        )

    def describe(self) -> str:
        """Human-readable summary for the system prompt."""
        parts = [f"reference date: {self.reference_date}"]
        if self.domains:
            parts.append(f"domains: {', '.join(self.domains)}")
        if self.jurisdictions:
            parts.append(f"jurisdictions: {', '.join(self.jurisdictions)}")
        return " | ".join(parts)
