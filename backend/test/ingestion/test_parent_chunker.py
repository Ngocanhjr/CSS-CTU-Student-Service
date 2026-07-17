from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)
from app.ingestion.parsing.page_markers import PageBlock
from app.ingestion.parsing.structural_parser import parse_page_blocks


def test_build_parent_sections_preserves_heading_and_page_range():
    parsed = parse_page_blocks(
        [
            PageBlock(
                page_number=3,
                content=(
                    "Lời mở đầu.\n\n"
                    "## Chương I\n\n"
                    "## NHỮNG VẤN ĐỀ CHUNG\n\n"
                    "#### Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng\n\n"
                    "1. Quy định này quy định về công tác học vụ dành cho sinh viên."
                ),
            ),
            PageBlock(
                page_number=4,
                content=(
                    "2. Quy định này áp dụng đối với sinh viên các ngành, "
                    "khóa đào tạo trình độ đại học hình thức chính quy."
                ),
            ),
        ]
    )

    sections = build_parent_sections(parsed.blocks)

    assert [section.heading_path for section in sections] == [
        ["document-root"],
        ["Chương I"],
        ["NHỮNG VẤN ĐỀ CHUNG"],
        ["NHỮNG VẤN ĐỀ CHUNG", "Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng"],
    ]

    article = sections[-1]
    assert (article.page_start, article.page_end) == (3, 4)
    assert "1. Quy định này quy định" in article.content
    assert "2. Quy định này áp dụng" in article.content

    chunk = make_parent_chunk(
        section=article,
        document_key="QD3266",
        version_key="QD3266-v1",
        parent_index=4,
        chunk_index=3,
    )

    assert chunk.chunk_key == "QD3266-v1::p::0004"
    assert chunk.parent_chunk_key is None
    assert chunk.chunk_type == "parent"
    assert chunk.page_start == 3
    assert chunk.page_end == 4
    assert chunk.token_count == len(chunk.content.split())
