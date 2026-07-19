from app.ingestion.markdown_reader import read_markdown_document
from app.vectorstore.repository import build_payload


def test_build_payload_includes_hydration_and_eligibility_fields() -> None:
    document = read_markdown_document("app/ingestion/test/test_doc.md")
    chunk = document.body

    payload = build_payload(
        document,
        __import__("app.ingestion.chunking.chunker", fromlist=["chunk_markdown_document"])
        .chunk_markdown_document(document)[1],
        postgres_chunk_id=42,
        review_status="approved",
        rag_status="published",
        is_latest=True,
        audience=["sinh_vien"],
    )

    assert chunk
    assert payload["postgres_chunk_id"] == 42
    assert payload["review_status"] == "approved"
    assert payload["rag_status"] == "published"
    assert payload["is_latest"] is True
    assert payload["audience"] == ["sinh_vien"]
