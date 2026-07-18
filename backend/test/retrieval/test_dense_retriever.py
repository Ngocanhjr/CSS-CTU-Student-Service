from app.retrieval import s4_dense_retriever
from app.vectorstore.models import QdrantSearchResult


def test_retrieve_child_chunks_embeds_and_maps_qdrant_points(monkeypatch) -> None:
    client = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(s4_dense_retriever, "embed_query", lambda query: [0.1, 0.2])
    monkeypatch.setattr(s4_dense_retriever, "get_qdrant_client", lambda: client)

    def fake_search_points(qdrant_client, **kwargs):
        captured["client"] = qdrant_client
        captured.update(kwargs)
        return [
            QdrantSearchResult(
                point_id="qdrant-point-42",
                score=0.91,
                payload={
                    "chunk_key": "test-v1::c::0001",
                    "chunk_type": "child",
                    "content": "Child content",
                    "postgres_chunk_id": 42,
                },
            )
        ]

    monkeypatch.setattr(s4_dense_retriever, "search_points", fake_search_points)

    documents = s4_dense_retriever.retrieve_child_chunks("test query", top_k=3)

    assert captured["client"] is client
    assert captured["query_vector"] == [0.1, 0.2]
    assert captured["top_k"] == 3
    condition_values = {
        condition.key: condition.match.value
        for condition in captured["query_filter"].must
    }
    assert condition_values == {
        "review_status": "approved",
        "rag_status": "published",
        "chunk_type": "child",
        "audience": "sinh_vien",
    }
    assert [condition.is_null.key for condition in captured["query_filter"].must_not if hasattr(condition, "is_null")] == [
        "postgres_chunk_id"
    ]
    assert [condition.is_empty.key for condition in captured["query_filter"].must_not if hasattr(condition, "is_empty")] == [
        "postgres_chunk_id"
    ]
    assert documents[0].page_content == "Child content"
    assert documents[0].metadata["postgres_chunk_id"] == 42
    assert documents[0].metadata["qdrant_point_id"] == "qdrant-point-42"
    assert documents[0].metadata["_score"] == 0.91
