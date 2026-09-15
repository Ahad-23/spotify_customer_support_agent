"""
Elasticsearch Indexer for Spotify Troubleshooting Cases

Creates the `spotify_support_cases` index with 768-dim dense vectors (cosine similarity),
embeds customer problem statements using native ES inference, and bulk-indexes documents.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import dotenv
from elasticsearch import Elasticsearch, helpers
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn

from src.rag.embeddings import ElasticNativeEmbeddingService


console = Console()

INDEX_NAME = "spotify_support_cases"

INDEX_MAPPINGS = {
    "mappings": {
        "properties": {
            "case_id": {"type": "keyword"},
            "intent": {"type": "keyword"},
            "customer_message": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "problem_vector": {
                "type": "dense_vector",
                "dims": 768,
                "index": True,
                "similarity": "cosine",
            },
            "resolution": {"type": "text"},
            "conversation": {"type": "text"},
            "metadata": {
                "properties": {
                    "brand": {"type": "keyword"},
                    "root_tweet_id": {"type": "long"},
                    "turn_count": {"type": "integer"},
                    "has_resolution": {"type": "boolean"},
                    "has_troubleshooting": {"type": "boolean"},
                    "is_deflection": {"type": "boolean"},
                    "resolved_in_public": {"type": "boolean"},
                    "created_at": {"type": "keyword"},
                }
            },
        }
    }
}


class CaseIndexer:
    def __init__(
        self,
        index_name: str = INDEX_NAME,
        embedding_service: Optional[ElasticNativeEmbeddingService] = None,
    ):
        self.index_name = index_name
        self.embedding_service = embedding_service or ElasticNativeEmbeddingService()
        self.es = self.embedding_service.es

    def setup_index(self, recreate: bool = False):
        """
        Creates the Elasticsearch index if it doesn't exist, or recreates if specified.
        """
        exists = self.es.indices.exists(index=self.index_name)
        if exists and recreate:
            console.print(f"[bold yellow]Deleting existing index:[/bold yellow] {self.index_name}")
            self.es.indices.delete(index=self.index_name)
            exists = False

        if not exists:
            console.print(f"[bold cyan]Creating index with 768-dim vector mappings:[/bold cyan] {self.index_name}")
            self.es.indices.create(index=self.index_name, body=INDEX_MAPPINGS)
            console.print("[bold green]Index created successfully.[/bold green]")
        else:
            console.print(f"[bold green]Index '{self.index_name}' already exists.[/bold green]")

    def index_cases(
        self,
        cases_file: str,
        limit: Optional[int] = None,
        batch_size: int = 32,
    ):
        """
        Reads cases from JSONL file, computes native embeddings for customer_message,
        and streams them into Elasticsearch in batches.
        """
        if not os.path.exists(cases_file):
            raise FileNotFoundError(f"Cases file not found: {cases_file}")

        console.print(f"[bold cyan]Reading cases from:[/bold cyan] {cases_file}")
        cases: List[Dict[str, Any]] = []
        with open(cases_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    cases.append(json.loads(line))
                if limit and len(cases) >= limit:
                    break

        total_cases = len(cases)
        console.print(f"Loaded [bold green]{total_cases:,}[/bold green] cases to index.")

        start_time = time.time()
        indexed_count = 0

        # Process in batches of 16 (strict ES inference API limit)
        actual_batch = min(batch_size, 16)
        console.print(f"Indexing cases in batches of {actual_batch}...")

        for i in range(0, total_cases, actual_batch):
            batch = cases[i : i + actual_batch]
            messages = [c.get("customer_message", "") for c in batch]

            # Compute dense embeddings natively
            embeddings = self.embedding_service.embed_texts(messages, batch_size=actual_batch)

            # Prepare bulk actions
            actions = []
            for case, emb in zip(batch, embeddings):
                doc = {
                    "_index": self.index_name,
                    "_id": case.get("case_id"),
                    "_source": {
                        "case_id": case.get("case_id"),
                        "intent": case.get("intent", "general_inquiry"),
                        "customer_message": case.get("customer_message", ""),
                        "problem_vector": emb,
                        "resolution": case.get("resolution", ""),
                        "conversation": "\n".join(case.get("conversation", []))
                        if isinstance(case.get("conversation"), list)
                        else str(case.get("conversation", "")),
                        "metadata": case.get("metadata", {}),
                    },
                }
                actions.append(doc)

            success_count, _ = helpers.bulk(self.es, actions, refresh=False)
            indexed_count += success_count

            if (i // actual_batch) % 10 == 0 or indexed_count >= total_cases:
                elapsed = time.time() - start_time
                pct = (indexed_count / total_cases) * 100
                rate = indexed_count / elapsed if elapsed > 0 else 0.0
                console.print(
                    f"  Indexed [bold green]{indexed_count:,}/{total_cases:,}[/bold green] "
                    f"({pct:.1f}%) | {rate:.1f} cases/s | Elapsed: {elapsed:.1f}s"
                )

        # Refresh index so documents are immediately searchable
        self.es.indices.refresh(index=self.index_name)
        total_time = time.time() - start_time
        console.print(
            f"\n[bold green]Successfully indexed {indexed_count:,} cases in {total_time:.2f}s "
            f"({indexed_count / total_time:.1f} cases/sec)![/bold green]"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index Spotify cases into Elasticsearch with native embeddings")
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/spotify_troubleshooting_cases.jsonl",
        help="Path to processed JSONL cases",
    )
    parser.add_argument("--recreate", action="store_true", help="Recreate index if it exists")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to index (for testing)")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for embedding and bulk indexing")
    args = parser.parse_args()

    indexer = CaseIndexer()
    indexer.setup_index(recreate=args.recreate)
    indexer.index_cases(args.input, limit=args.limit, batch_size=args.batch_size)

