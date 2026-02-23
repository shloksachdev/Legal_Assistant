"""CourtListener API client — optional live data ingestion from Free Law Project.

Provides programmatic access to 9M+ legal opinions and statutes.
Falls back gracefully if no API token is configured.
"""

import requests
from templex.config import COURTLISTENER_API_TOKEN, COURTLISTENER_BASE_URL


class CourtListenerClient:
    """REST client for CourtListener API v4."""

    def __init__(self):
        self.base_url = COURTLISTENER_BASE_URL
        self.headers = {}
        if COURTLISTENER_API_TOKEN:
            self.headers["Authorization"] = f"Token {COURTLISTENER_API_TOKEN}"

    @property
    def is_available(self) -> bool:
        return bool(COURTLISTENER_API_TOKEN)

    def search_opinions(self, query: str, jurisdiction: str = "",
                        max_results: int = 10) -> list[dict]:
        """Search for court opinions matching a query."""
        params = {
            "q": query,
            "type": "o",  # opinions
            "order_by": "score desc",
        }
        if jurisdiction:
            params["court"] = jurisdiction

        try:
            resp = requests.get(
                f"{self.base_url}/search/",
                params=params,
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])[:max_results]
        except requests.RequestException as e:
            print(f"[CourtListener] Search failed: {e}")
            return []

    def fetch_opinion(self, opinion_id: int) -> dict | None:
        """Fetch a specific court opinion by ID."""
        try:
            resp = requests.get(
                f"{self.base_url}/opinions/{opinion_id}/",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"[CourtListener] Fetch failed: {e}")
            return None

    def fetch_cluster(self, cluster_id: int) -> dict | None:
        """Fetch an opinion cluster (case grouping)."""
        try:
            resp = requests.get(
                f"{self.base_url}/clusters/{cluster_id}/",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"[CourtListener] Cluster fetch failed: {e}")
            return None
