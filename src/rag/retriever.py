"""
Asymmetric Case Retriever for Spotify Support

Performs hybrid semantic search (kNN dense vector on problem_vector + BM25 keyword matching)
to retrieve historical solved customer support cases that match an incoming customer problem.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from elasticsearch import Elasticsearch
from src.rag.embeddings import ElasticNativeEmbeddingService


@dataclass
class RetrievedCase:
    case_id: str
    score: float
    intent: str
    customer_problem: str
    resolution: str
    conversation: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "score": round(self.score, 4),
            "intent": self.intent,
            "customer_problem": self.customer_problem,
            "resolution": self.resolution,
            "conversation": self.conversation,
            "metadata": self.metadata,
        }


class CaseRetriever:
    def __init__(
        self,
        index_name: str = "spotify_support_cases",
        embedding_service: Optional[ElasticNativeEmbeddingService] = None,
    ):
        self.index_name = index_name
        self.embedding_service = embedding_service or ElasticNativeEmbeddingService()
        self.es = self.embedding_service.es

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        intent_filter: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[RetrievedCase]:
        """
        Retrieves top-k historical cases that best match the customer query.
        Uses asymmetric problem-to-problem dense vector matching + BM25 hybrid search.
        """
        if not query or not query.strip():
            return []

        # 1. Generate dense query embedding via native ES inference
        query_vector = self.embedding_service.embed_query(query)

        # 2. Build kNN search clause
        knn_clause: Dict[str, Any] = {
            "field": "problem_vector",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": max(50, top_k * 10),
            "boost": 0.8,
        }

        if intent_filter and intent_filter != "general_inquiry":
            knn_clause["filter"] = {"term": {"intent": intent_filter}}

        # 3. Build BM25 keyword query clause
        bm25_clause: Dict[str, Any] = {
            "multi_match": {
                "query": query,
                "fields": ["customer_message^2", "resolution", "conversation"],
                "fuzziness": "AUTO",
            }
        }

        # 4. Execute hybrid search
        search_body: Dict[str, Any] = {
            "size": top_k,
            "knn": knn_clause,
            "query": bm25_clause,
            "_source": [
                "case_id",
                "intent",
                "customer_message",
                "resolution",
                "conversation",
                "metadata",
            ],
        }

        try:
            response = self.es.search(index=self.index_name, body=search_body)
            hits = response.get("hits", {}).get("hits", [])
        except Exception as e:
            # Fallback to pure kNN if serverless hybrid syntax difference occurs
            search_body.pop("query", None)
            response = self.es.search(index=self.index_name, body=search_body)
            hits = response.get("hits", {}).get("hits", [])

        results: List[RetrievedCase] = []
        for hit in hits:
            score = float(hit.get("_score", 0.0))
            if score < min_score:
                continue

            src = hit.get("_source", {})
            case = RetrievedCase(
                case_id=src.get("case_id", hit.get("_id", "")),
                score=score,
                intent=src.get("intent", "general_inquiry"),
                customer_problem=src.get("customer_message", ""),
                resolution=src.get("resolution", ""),
                conversation=src.get("conversation", ""),
                metadata=src.get("metadata", {}),
            )
            results.append(case)

        return results


if __name__ == "__main__":
    retriever = CaseRetriever()
    test_queries = [
        "Spotify keeps skipping songs on my bluetooth speaker",
        "Songs are grayed out and won't download offline",
        "Can't log into my account, says wrong password",
    ]

    for q in test_queries:
        print(f"\n[Query]: {q}")
        matches = retriever.retrieve(q, top_k=2)
        for i, m in enumerate(matches, 1):
            print(f"  Match #{i} (Score: {m.score:.4f}, Intent: {m.intent}):")
            print(f"    Problem:    {m.customer_problem[:80]}...")
            print(f"    Resolution: {m.resolution[:100]}...")
