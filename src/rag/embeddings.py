"""
Pinecone Inference Embedding Service

Uses the Pinecone Inference API with `multilingual-e5-large`
to generate 1024-dimensional dense vectors with asymmetric query / passage encoding.
"""

import os
from pathlib import Path
from typing import List, Optional
import dotenv
from pinecone import Pinecone

env_file = Path(__file__).resolve().parents[2] / ".env"
dotenv.load_dotenv(env_file)


class PineconeEmbeddingService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = 1024,
    ):
        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.model = model or os.getenv("PINECONE_EMBED_MODEL", "multilingual-e5-large")
        self.dimension = dimension

        if not self.api_key:
            raise ValueError(
                "PINECONE_API_KEY missing. Please check your .env file."
            )

        self.pc = Pinecone(api_key=self.api_key)

    def embed_texts(self, texts: List[str], batch_size: int = 96) -> List[List[float]]:
        """
        Embed a list of passage text strings into dense vector representations.
        Uses input_type="passage" for asymmetric indexing.
        """
        if not texts:
            return []

        effective_batch_size = min(batch_size, 96)
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), effective_batch_size):
            batch = texts[i : i + effective_batch_size]
            sanitized_batch = [t if t and t.strip() else " " for t in batch]

            response = self.pc.inference.embed(
                model=self.model,
                inputs=sanitized_batch,
                parameters={"input_type": "passage", "truncate": "END"},
            )

            for item in response.data:
                all_embeddings.append(item.values)

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single search query text using input_type="query".
        """
        query_text = text if text and text.strip() else " "
        response = self.pc.inference.embed(
            model=self.model,
            inputs=[query_text],
            parameters={"input_type": "query", "truncate": "END"},
        )
        if not response.data:
            raise RuntimeError("Failed to compute embedding for query")
        return response.data[0].values



if __name__ == "__main__":
    service = PineconeEmbeddingService()
    test_query = "Music keeps skipping on bluetooth speaker"
    vec = service.embed_query(test_query)
    print(f"Embedding successful! Vector length: {len(vec)}, preview: {vec[:4]}")
