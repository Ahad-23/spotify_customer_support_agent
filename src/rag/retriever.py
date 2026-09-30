"""
Pinecone Case Retriever for Spotify Support

Performs dense semantic search on problem vectors (1024d multilingual-e5-large)
with metadata filtering to retrieve historical solved customer support cases
that match an incoming customer problem.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dotenv
from pinecone import Pinecone

from src.rag.embeddings import PineconeEmbeddingService

dotenv.load_dotenv(REPO_ROOT / ".env")

DEFAULT_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "spotify-support-cases")


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
        index_name: str = DEFAULT_INDEX_NAME,
        embedding_service: Optional[PineconeEmbeddingService] = None,
    ):
        self.index_name = index_name
        self.embedding_service = embedding_service or PineconeEmbeddingService()
        self.pc = self.embedding_service.pc
        self._index = None

    @property
    def index(self):
        if self._index is None:
            self._index = self.pc.Index(self.index_name)
        return self._index

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        intent_filter: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[RetrievedCase]:
        """
        Retrieves top-k historical cases that best match the customer query.
        Uses asymmetric problem-to-problem dense vector matching on Pinecone Serverless.
        """
        if not query or not query.strip():
            return []

        # 1. Generate dense query embedding via Pinecone Inference
        try:
            query_vector = self.embedding_service.embed_query(query)
        except Exception as e:
            print(f"Warning: Failed to embed query: {e}")
            return []

        # 2. Build metadata filter clause if intent filter specified
        filter_clause = None
        if intent_filter and intent_filter != "general_inquiry":
            filter_clause = {"intent": {"$eq": intent_filter}}

        # 3. Query Pinecone
        matches = []
        try:
            response = self.index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter_clause,
                include_metadata=True,
            )
            matches = response.matches or []
        except Exception:
            # Fallback without filter if error occurred or index schema difference
            try:
                response = self.index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                )
                matches = response.matches or []
            except Exception as e2:
                print(f"Warning: Pinecone query failed: {e2}")
                return []

        results: List[RetrievedCase] = []
        for match in matches:
            score = float(match.score if match.score is not None else 0.0)
            if score < min_score:
                continue

            src = match.metadata or {}
            case = RetrievedCase(
                case_id=src.get("case_id", match.id),
                score=score,
                intent=src.get("intent", "general_inquiry"),
                customer_problem=src.get("customer_message", ""),
                resolution=src.get("resolution", ""),
                conversation=src.get("conversation", ""),
                metadata=src,
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
