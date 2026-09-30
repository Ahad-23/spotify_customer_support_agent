"""
Comprehensive unit and contract tests for Pinecone vector embeddings and retriever.
"""

import pytest
from src.rag.embeddings import PineconeEmbeddingService
from src.rag.retriever import CaseRetriever, RetrievedCase


@pytest.fixture(scope="module")
def embedding_service():
    return PineconeEmbeddingService()


@pytest.fixture(scope="module")
def retriever(embedding_service):
    return CaseRetriever(embedding_service=embedding_service)


def test_embedding_service_dimension(embedding_service):
    assert embedding_service.dimension == 1024


def test_embedding_single_query(embedding_service):
    query = "Songs skipping on bluetooth speaker"
    vector = embedding_service.embed_query(query)
    assert isinstance(vector, list)
    assert len(vector) == 1024
    assert all(isinstance(x, (float, int)) for x in vector)


def test_embedding_large_batch_chunking(embedding_service):
    texts = [f"Customer issue test #{i}" for i in range(25)]
    embeddings = embedding_service.embed_texts(texts, batch_size=16)

    assert len(embeddings) == 25
    assert all(len(emb) == 1024 for emb in embeddings)


def test_embedding_empty_and_sanitization(embedding_service):
    assert embedding_service.embed_texts([]) == []
    emb = embedding_service.embed_texts(["   ", ""])
    assert len(emb) == 2
    assert len(emb[0]) == 1024


def test_retriever_hybrid_search(retriever):
    query = "Why do songs keep skipping on my bluetooth speaker?"
    results = retriever.retrieve(query, top_k=3)

    assert len(results) > 0
    top = results[0]
    assert isinstance(top, RetrievedCase)
    assert top.case_id.startswith("spotify_case_")
    assert top.score > 0.0
    assert len(top.customer_problem) > 0
    assert len(top.resolution) > 0

    # Test dictionary serialization
    d = top.to_dict()
    assert "case_id" in d
    assert "score" in d
    assert "resolution" in d
    assert "customer_problem" in d


def test_retriever_intent_filter(retriever):
    query = "Why do songs keep skipping on my bluetooth speaker?"
    results = retriever.retrieve(query, top_k=2, intent_filter="playback_audio")

    for r in results:
        assert r.intent == "playback_audio"


def test_retriever_fallback_on_empty_filter(retriever):
    results = retriever.retrieve("bluetooth audio skipping", top_k=2, intent_filter="non_existent_intent")
    assert isinstance(results, list)


def test_retriever_min_score_filter(retriever):
    query = "Spotify tracks pause"
    results = retriever.retrieve(query, top_k=5, min_score=9999.0)
    assert results == []


def test_retriever_special_characters(retriever):
    query = "Spotify! @#$%^&*() -- crashed? [error 404] /_\\"
    results = retriever.retrieve(query, top_k=2)
    assert isinstance(results, list)


def test_retriever_empty_query(retriever):
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []
