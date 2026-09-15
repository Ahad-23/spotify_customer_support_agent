"""
Elasticsearch Native Embedding Service

Uses the in-cluster inference endpoint (.jina-embeddings-v5-text-nano)
to generate 768-dimensional dense vectors natively on Elastic Cloud Serverless.
"""

import os
from pathlib import Path
from typing import List, Optional
import dotenv
from elasticsearch import Elasticsearch

# Ensure environment variables are loaded
env_file = Path(__file__).resolve().parents[2] / ".env"
dotenv.load_dotenv(env_file)


class ElasticNativeEmbeddingService:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        inference_id: str = ".jina-embeddings-v5-text-nano",
        dimension: int = 768,
    ):
        self.endpoint = endpoint or os.getenv("ELASTICSEARCH_ENDPOINT")
        self.api_key = api_key or os.getenv("ELASTICSEARCH_API_KEY")
        self.inference_id = inference_id
        self.dimension = dimension

        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Elasticsearch endpoint or API key missing. Please check your .env file."
            )

        self.es = Elasticsearch(hosts=[self.endpoint], api_key=self.api_key)

    def embed_texts(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        """
        Embed a list of text strings into dense vector representations.
        Note: Elasticsearch native inference endpoint limits input to at most 16 items per call.
        """
        if not texts:
            return []

        # Enforce max 16 items per inference request
        effective_batch_size = min(batch_size, 16)
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), effective_batch_size):
            batch = texts[i : i + effective_batch_size]
            # Replace empty strings with single space to avoid inference errors
            sanitized_batch = [t if t and t.strip() else " " for t in batch]


            response = self.es.inference.inference(
                inference_id=self.inference_id,
                input=sanitized_batch,
            )
            body = response.body

            # Format in ES: body is {"text_embedding": [{"embedding": [...]}, ...]}
            if isinstance(body, dict) and "text_embedding" in body:
                for item in body["text_embedding"]:
                    all_embeddings.append(item["embedding"])
            elif isinstance(body, list):
                for item in body:
                    if isinstance(item, dict) and "embedding" in item:
                        all_embeddings.append(item["embedding"])
                    else:
                        all_embeddings.append(item)
            else:
                raise RuntimeError(f"Unexpected inference response format: {type(body)}")

        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single search query text.
        """
        embeddings = self.embed_texts([text], batch_size=1)
        if not embeddings:
            raise RuntimeError("Failed to compute embedding for query")
        return embeddings[0]


if __name__ == "__main__":
    service = ElasticNativeEmbeddingService()
    test_query = "Music keeps skipping on bluetooth speaker"
    vec = service.embed_query(test_query)
    print(f"Embedding successful! Vector length: {len(vec)}, preview: {vec[:4]}")
