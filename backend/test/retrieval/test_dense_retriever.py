from app.retrieval import dense_retriever
from app.vectorstore.models import QdrantSearchResult


def test_retrieve_child_chunks_embeds_and_maps_qdrant_points(monkeypatch) -> None:
    client = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(dense_retriever, "embed_query", lambda query: [0.1, 0.2])
    monkeypatch.setattr(dense_retriever, "get_qdrant_client", lambda: client)

    def fake_search_points(qdrant_client, **kwargs):
        captured["client"] = qdrant_client
        captured.update(kwargs)
        return [
            QdrantSearchResult(
                score=0.91,
                payload={
                    "chunk_key": "test-v1::c::0001",
                    "chunk_type": "child",
                    "content": "Child content",
                },
            )
        ]

    monkeypatch.setattr(dense_retriever, "search_points", fake_search_points)

    documents = dense_retriever.retrieve_child_chunks("test query", top_k=3)

    assert captured["client"] is client
    assert captured["query_vector"] == [0.1, 0.2]
    assert captured["top_k"] == 3
    assert captured["filters"].chunk_type == "child"
    assert documents[0].page_content == "Child content"
    assert documents[0].metadata["_score"] == 0.91
