"""Autonomous Research Pipeline.

Coordinates multi-query expansion, metadata re-ranking, and parallel ingestion
to ensure high-confidence retrieval from live APIs while protecting credits.
"""

import concurrent.futures
import numpy as np
from typing import List, Dict, Any

from templex.config import (
    MAX_SEARCH_QUERIES,
    MAX_INGEST_PER_TURN,
    CONFIDENCE_THRESHOLD,
    SCOPE_BOOST_VALIDITY,
    SCOPE_BOOST_DOMAIN,
)
from templex.embeddings.engine import EmbeddingEngine
from templex.ingestion.indiankanoon import IndianKanoonClient
from templex.ingestion.graph_populator import _ingest_seed_data, initialize_schema
from templex.actions.scope import QueryScope
from templex.status import push_status


class ResearchPipeline:
    """Orchestrates the fetch, re-rank, and ingest loop."""

    @staticmethod
    def execute_indian_law_research(
        original_prompt: str,
        queries: List[str],
        doctypes: str = "judgments,laws",
        scope: QueryScope | None = None,
        session_id: str = ""
    ) -> str:
        """Run the high-confidence pipeline for Indian Kanoon."""
        client = IndianKanoonClient()
        if not client.is_available:
            return "INDIANKANOON_API_TOKEN is not configured."

        # Limit max queries to avoid excessive API hits
        queries = queries[:MAX_SEARCH_QUERIES]
        
        # ── Step 1: Parallel API Fetch (Metadata Only) ──
        push_status(session_id, f"Executing {len(queries)} parallel search queries...")
        print(f"  [Research] Executing {len(queries)} parallel queries...")
        
        all_metadata = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(queries)) as executor:
            # Map queries to the search function
            future_to_query = {
                executor.submit(client.search, q, max_results=10, doctypes=doctypes): q 
                for q in queries
            }
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    results = future.result()
                    all_metadata.extend(results)
                except Exception as e:
                    print(f"  [Research] Search failed: {e}")

        if not all_metadata:
            return "No documents found across any search queries."

        # ── Step 2: Deduplication ──
        unique_docs: Dict[str, dict] = {}
        for doc in all_metadata:
            tid = str(doc.get("tid", ""))
            if tid and tid not in unique_docs:
                unique_docs[tid] = doc

        docs_list = list(unique_docs.values())
        print(f"  [Research] Fetched {len(docs_list)} unique metadata snippets.")

        # ── Step 3: Fast Local Re-Ranking (EmbeddingEngine) ──
        push_status(session_id, f"Fetched {len(docs_list)} snippets. Re-ranking locally...")
        query_emb = EmbeddingEngine.encode_query(original_prompt)
        
        # Build text to encode for each snippet (Title + Snippet)
        snippet_texts = [
            f"{doc.get('title', '')} {doc.get('headline', '')}" 
            for doc in docs_list
        ]
        
        snippet_embs = EmbeddingEngine.encode_batch(snippet_texts)
        
        scored_docs = []
        for i, doc in enumerate(docs_list):
            raw_score = float(EmbeddingEngine.cosine_similarity(query_emb, snippet_embs[i]))
            
            # Apply Scope Boosts to the metadata to favor session constraints
            boosted_score = raw_score
            if scope:
                # Basic validity boost: if it was published before/on reference date
                pub_date = doc.get("publishdate", "")
                if pub_date and pub_date <= scope.reference_date:
                    boosted_score += SCOPE_BOOST_VALIDITY
                    
                # Basic domain boost: match docsource to domain keywords
                source = doc.get("docsource", "").lower()
                for domain in scope.work_types:
                    if domain.lower() in source:
                        boosted_score += SCOPE_BOOST_DOMAIN
                        break
                        
            doc["_relevance_score"] = boosted_score
            doc["_raw_score"] = raw_score
            scored_docs.append(doc)

        # ── Step 4: The 90% Confidence Filter ──
        scored_docs.sort(key=lambda x: x["_relevance_score"], reverse=True)
        high_confidence_docs = [
            d for d in scored_docs if d["_relevance_score"] >= CONFIDENCE_THRESHOLD
        ]
        
        if not high_confidence_docs:
            top_score = scored_docs[0]['_relevance_score'] if scored_docs else 0
            return (
                f"Searched {len(queries)} queries and evaluated {len(docs_list)} snippets, "
                f"but none met the {CONFIDENCE_THRESHOLD*100}% relevance threshold. "
                f"(Top score was {top_score:.2f}). Please rephrase your query."
            )

        # Apply Hard Cap
        to_ingest = high_confidence_docs[:MAX_INGEST_PER_TURN]
        push_status(session_id, f"Found {len(high_confidence_docs)} relevant docs. Fetching top {len(to_ingest)} full texts...")
        print(f"  [Research] {len(to_ingest)} documents passed confidence threshold. Initiating parallel full-text fetch...")

        # ── Step 5: Parallel Full-Text Fetch & Ingest ──
        new_data = {"works": [], "expressions": [], "actions": []}
        
        def fetch_and_prepare(doc_meta: dict) -> dict | None:
            tid = doc_meta.get("tid")
            text_content = client.fetch_document_text(tid)
            if not text_content:
                return None
                
            title = doc_meta.get("title", f"Indian Kanoon Document {tid}")
            docsource = doc_meta.get("docsource", "Indian Kanoon")
            date_filed = doc_meta.get("publishdate", "1947-01-01")

            work_id = f"IK-{tid}"
            expr_id = f"IK-EXP-{tid}-1"
            action_id = f"ACT-IK-{tid}"
            source_url = f"https://indiankanoon.org/doc/{tid}/"

            return {
                "work": {
                    "work_id": work_id,
                    "title": title,
                    "jurisdiction": "India",
                    "work_type": "judgment" if "court" in docsource.lower() else "statute",
                    "domain": "other",  # Will rely on graph_populator or manual tagging later
                    "parent_work_id": "",
                },
                "expression": {
                    "expr_id": expr_id,
                    "work_id": work_id,
                    "text_content": text_content[:6000],  # Still cap at 6k to protect embedding memory
                    "valid_from": date_filed,
                    "valid_to": "",
                },
                "action": {
                    "action_id": action_id,
                    "action_type": "judgment",
                    "description": f"Document: {title} ({docsource})",
                    "effective_date": date_filed,
                    "source_ref": source_url,
                    "initiates": [expr_id],
                    "terminates": [],
                },
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(to_ingest)) as executor:
            fetched_results = list(executor.map(fetch_and_prepare, to_ingest))
            
        push_status(session_id, "Parsing LRMoo structure and generating embeddings...")
            
        for res in fetched_results:
            if res:
                new_data["works"].append(res["work"])
                new_data["expressions"].append(res["expression"])
                new_data["actions"].append(res["action"])

        if new_data["works"]:
            push_status(session_id, "Inserting new nodes into Kùzu Graph...")
            initialize_schema()
            _ingest_seed_data(new_data)
            push_status(session_id, "Ingestion complete. Resuming semantic search...")
            
            summary = "Autonomous Research Complete. Successfully fetched and ingested:\n"
            for w in new_data["works"]:
                summary += f"- {w['title']} (Work ID: {w['work_id']})\n"
            summary += "\nYou MUST now use 'resolve_reference_tool' to locate these in the local graph."
            return summary
            
        return "Failed to download full text for the high-confidence documents."
