from backend.app.retrieval.S11_context_builder import build_retrieval_context
from app.retrieval.models import RetrievalResult


def make_result(*, chunk_key: str, content: str, parent_content: str | None) -> RetrievalResult:
    return RetrievalResult(
        postgres_chunk_id=1,
        postgres_parent_chunk_id=2,
        document_key="test-doc",
        version_key="test-doc-v1",
        chunk_key=chunk_key,
        parent_chunk_key="test-doc-v1::p::0001",
        score=1.0,
        content=content,
        title="Test document",
        page_start=1,
        page_end=1,
        source_file="test.md",
        source_url="",
        citation="test.md, trang 1",
        heading_path=[],
        item_path=[],
        legal_unit_type="none",
        parent_content=parent_content,
    )


def test_build_retrieval_context_includes_parent_once() -> None:
    context = build_retrieval_context(
        [
            make_result(
                chunk_key="test-doc-v1::c::0001",
                content="First child",
                parent_content="Shared parent",
            ),
            make_result(
                chunk_key="test-doc-v1::c::0002",
                content="Second child",
                parent_content="Shared parent",
            ),
        ]
    )

    assert context.count("Shared parent") == 1
    assert "First child" in context
    assert "Second child" in context
