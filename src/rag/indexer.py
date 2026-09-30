"""
Pinecone Indexer for Spotify Troubleshooting Cases

Creates the `spotify-support-cases` Pinecone Serverless index with 1024-dim dense vectors,
embeds customer problem statements using Pinecone Inference API (multilingual-e5-large),
and bulk-upserts documents.
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
from pinecone import Pinecone, ServerlessSpec
from rich.console import Console

from src.rag.embeddings import PineconeEmbeddingService

console = Console()
dotenv.load_dotenv(REPO_ROOT / ".env")

DEFAULT_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "spotify-support-cases")


class CaseIndexer:
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

    def setup_index(self, recreate: bool = False):
        """
        Creates the Pinecone Serverless index if it doesn't exist, or recreates if specified.
        """
        cloud = os.getenv("PINECONE_CLOUD", "aws")
        region = os.getenv("PINECONE_REGION", "us-east-1")

        exists = self.pc.has_index(self.index_name)
        if exists and recreate:
            console.print(f"[bold yellow]Deleting existing index:[/bold yellow] {self.index_name}")
            self.pc.delete_index(self.index_name)
            # Brief pause to allow deletion to register
            time.sleep(2)
            exists = False

        if not exists:
            console.print(
                f"[bold cyan]Creating Pinecone index ({self.embedding_service.dimension}d, {cloud}/{region}):[/bold cyan] {self.index_name}"
            )
            self.pc.create_index(
                name=self.index_name,
                dimension=self.embedding_service.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=cloud, region=region),
            )
            # Wait until ready
            while not self.pc.describe_index(self.index_name).status["ready"]:
                time.sleep(1)
            console.print("[bold green]Pinecone index created successfully and ready.[/bold green]")
        else:
            console.print(f"[bold green]Index '{self.index_name}' already exists and ready.[/bold green]")

    def index_cases(
        self,
        cases_file: str,
        limit: Optional[int] = None,
        batch_size: int = 64,
    ):
        """
        Reads cases from JSONL file, computes embeddings for customer_message via Pinecone Inference,
        and streams them into Pinecone index in batches.
        """
        if not os.path.exists(cases_file):
            raise FileNotFoundError(f"Cases file not found: {cases_file}")

        self.setup_index(recreate=False)

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
        actual_batch = min(batch_size, 96)
        console.print(f"Indexing cases in batches of {actual_batch}...")

        for i in range(0, total_cases, actual_batch):
            batch = cases[i : i + actual_batch]
            messages = [c.get("customer_message", "") for c in batch]

            embeddings = self.embedding_service.embed_texts(messages, batch_size=actual_batch)

            vectors = []
            for case, emb in zip(batch, embeddings):
                case_id = case.get("case_id") or f"case_{int(time.time()*1000)}"
                raw_conv = case.get("conversation", [])
                conv_str = (
                    "\n".join(raw_conv) if isinstance(raw_conv, list) else str(raw_conv)
                )

                meta = {
                    "case_id": case_id,
                    "intent": case.get("intent", "general_inquiry"),
                    "customer_message": case.get("customer_message", "")[:2000],
                    "resolution": case.get("resolution", "")[:3000],
                    "conversation": conv_str[:3000],
                    "brand": case.get("metadata", {}).get("brand", "SpotifyCares"),
                    "turn_count": case.get("metadata", {}).get("turn_count", 0),
                    "has_resolution": case.get("metadata", {}).get("has_resolution", True),
                }

                vectors.append({
                    "id": case_id,
                    "values": emb,
                    "metadata": meta,
                })

            self.index.upsert(vectors=vectors)
            indexed_count += len(vectors)

            elapsed = time.time() - start_time
            pct = (indexed_count / total_cases) * 100
            rate = indexed_count / elapsed if elapsed > 0 else 0.0
            console.print(
                f"  [{pct:5.1f}%] Upserted {indexed_count:,}/{total_cases:,} cases "
                f"({rate:.1f} cases/s, {elapsed:.1f}s elapsed)"
            )

        total_elapsed = time.time() - start_time
        console.print(
            f"\n[bold green]Indexing Complete![/bold green] "
            f"Successfully upserted {indexed_count:,} cases into '{self.index_name}' in {total_elapsed:.2f}s."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index Spotify cases into Pinecone Serverless")
    parser.add_argument(
        "--file",
        default=str(REPO_ROOT / "data" / "processed" / "spotify_troubleshooting_cases.jsonl"),
        help="Path to JSONL cases file",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to index")
    parser.add_argument("--recreate", action="store_true", help="Recreate Pinecone index if exists")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding & upsert batch size")
    args = parser.parse_args()

    indexer = CaseIndexer()
    if args.recreate:
        indexer.setup_index(recreate=True)
    indexer.index_cases(args.file, limit=args.limit, batch_size=args.batch_size)
