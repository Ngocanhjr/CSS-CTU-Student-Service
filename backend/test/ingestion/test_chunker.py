from app.ingestion.chunking.chunker import chunk_markdown_body


def test_chunk_markdown_body_preserves_document_order_and_parent_links():
    body = """\
<!-- page: 3 -->
## Chương I

## NHỮNG VẤN ĐỀ CHUNG

#### Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng

1. Quy định này quy định về công tác học vụ dành cho sinh viên.

2. Quy định này áp dụng đối với sinh viên chính quy.

<!-- page: 4 -->
#### Điều 2. Sinh viên

Sinh viên hình thức chính quy của Trường Đại học Cần Thơ là những người đã trúng tuyển.
"""

    result = chunk_markdown_body(
        body=body,
        document_key="QD3266",
        version_key="QD3266-v1",
        child_chunk_size=1200,
        child_chunk_overlap=100,
    )

    assert len(result.parent_chunks) == 4
    assert len(result.child_chunks) == 3
    assert [report.code for report in result.warnings] == [
        "context_only_parent",
        "context_only_parent",
    ]
    assert result.errors == []

    all_chunks = sorted(
        [*result.parent_chunks, *result.child_chunks],
        key=lambda chunk: chunk.chunk_index,
    )
    assert [chunk.chunk_index for chunk in all_chunks] == list(range(7))
    assert [chunk.chunk_type for chunk in all_chunks] == [
        "parent",
        "parent",
        "parent",
        "child",
        "child",
        "parent",
        "child",
    ]
    assert result.child_chunks[0].parent_chunk_key == result.parent_chunks[2].chunk_key
    assert result.child_chunks[-1].parent_chunk_key == result.parent_chunks[-1].chunk_key
