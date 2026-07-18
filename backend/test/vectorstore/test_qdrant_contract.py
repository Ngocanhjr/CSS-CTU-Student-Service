from app.vectorstore.models import QdrantChunkPayload


def test_qdrant_payload_is_structural_only():
    payload = QdrantChunkPayload(
        document_key="doc",
        version_key="doc-v1",
        title="Test",
        source_file="storage/canonical/doc-v1.md",
        document_type="quyet_dinh",
        domain="dao_tao",
        audience=["sinh_vien"],
        audience_student=True,
        review_status="approved",
        rag_status="indexed",
        is_latest=True,
        chunk_key="doc-v1::c::0001",
        parent_chunk_key="doc-v1::p::0001",
        chunk_type="child",
        heading_path=["Chương I"],
        item_path=[],
        postgres_chunk_id=101,
        chunk_index=1,
    )

    data = payload.model_dump()
    assert "content" not in data
    assert data["postgres_chunk_id"] == 101
    assert data["audience_student"] is True
