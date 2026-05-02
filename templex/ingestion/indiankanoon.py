"""Indian Kanoon API client — live ingestion of Indian legal data.

Provides programmatic access to 3 crore+ Indian legal documents including
Supreme Court judgments, High Court orders, Central Acts, and Constitutional
provisions. Falls back gracefully if no API token is configured.

API Reference: https://api.indiankanoon.org/documentation/
"""

import re
import requests
from templex.config import INDIANKANOON_API_TOKEN, INDIANKANOON_BASE_URL


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode basic entities to get plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text


class IndianKanoonClient:
    """REST client for the Indian Kanoon API v1."""

    def __init__(self):
        self.base_url = INDIANKANOON_BASE_URL
        self.headers = {"Accept": "application/json"}
        if INDIANKANOON_API_TOKEN:
            self.headers["Authorization"] = f"Token {INDIANKANOON_API_TOKEN}"

    @property
    def is_available(self) -> bool:
        return bool(INDIANKANOON_API_TOKEN)

    def search(
        self,
        query: str,
        max_results: int = 5,
        doctypes: str = "judgments,laws",
    ) -> list[dict]:
        """Search Indian Kanoon for documents matching a query.

        Args:
            query:       Full-text boolean query (e.g. '44th amendment property right').
            max_results: Maximum number of results to return (paged at 10/page).
            doctypes:    Comma-separated Indian Kanoon doctype filter.
                         Use 'supremecourt' for SC only, 'laws' for Acts/statutes,
                         'judgments' for SC+HC+District courts.

        Returns:
            List of result dicts with keys: tid, title, headline, docsource.
        """
        params = {
            "formInput": query,
            "pagenum": 0,
        }
        if doctypes:
            params["doctypes"] = doctypes

        try:
            resp = requests.post(
                f"{self.base_url}/search/",
                data=params,
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            docs = data.get("docs", [])
            return docs[:max_results]
        except requests.RequestException as e:
            print(f"[IndianKanoon] Search failed: {e}")
            return []

    def fetch_document(self, tid: int | str) -> dict | None:
        """Fetch the full text of an Indian Kanoon document by ID.

        Args:
            tid: The document TID returned by the search API.

        Returns:
            Dict with keys: doc (HTML), title, docsource, or None on failure.
        """
        try:
            resp = requests.post(
                f"{self.base_url}/doc/{tid}/",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"[IndianKanoon] Document fetch failed for TID {tid}: {e}")
            return None

    def fetch_document_text(self, tid: int | str) -> str | None:
        """Fetch and strip the plain text of a document by TID."""
        data = self.fetch_document(tid)
        if not data:
            return None
        html = data.get("doc", "")
        return _strip_html(html) if html else None
