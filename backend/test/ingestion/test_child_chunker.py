from app.ingestion.chunking.child_chunker import (
    ChildUnit,
    build_child_units,
    build_structural_child_units,
    group_short_bullet_units,
    make_child_chunks,
    split_long_child_unit,
)
from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)
from app.ingestion.parsing.page_markers import PageBlock
from app.ingestion.parsing.structural_parser import parse_page_blocks
from app.ingestion.parsing.structural_parser import StructuralBlock


def test_build_structural_child_units_keeps_legal_items_separate():
    parsed = parse_page_blocks(
        [
            PageBlock(
                page_number=3,
                content=(
                    "## Chương I\n\n"
                    "## NHỮNG VẤN ĐỀ CHUNG\n\n"
                    "#### Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng\n\n"
                    "1. Quy định này quy định về công tác học vụ.\n\n"
                    "Đoạn này tiếp tục giải thích khoản thứ nhất.\n\n"
                    "2. Quy định này áp dụng đối với sinh viên chính quy."
                ),
            )
        ]
    )
    sections = build_parent_sections(parsed.blocks)

    chapter_units, chapter_reports = build_structural_child_units(sections[0])
    article_units, article_reports = build_structural_child_units(sections[-1])

    assert chapter_units == []
    assert [report.code for report in chapter_reports] == ["context_only_parent"]

    assert article_reports == []
    assert [unit.item_marker for unit in article_units] == ["1.", "2."]
    assert article_units[0].legal_unit_type == "clause"
    assert "Đoạn này tiếp tục giải thích khoản thứ nhất." in article_units[0].content
    assert "2. Quy định này áp dụng" not in article_units[0].content
    assert article_units[1].parent_item_key is None

    parent_chunk = make_parent_chunk(
        section=sections[-1],
        document_key="QD3266",
        version_key="QD3266-v1",
        parent_index=3,
        chunk_index=2,
    )
    child_chunks = make_child_chunks(
        child_units=article_units,
        parent_chunk=parent_chunk,
        child_start_index=1,
        chunk_start_index=3,
    )

    assert [chunk.chunk_key for chunk in child_chunks] == [
        "QD3266-v1::c::0001",
        "QD3266-v1::c::0002",
    ]
    assert [chunk.chunk_index for chunk in child_chunks] == [3, 4]
    assert all(chunk.parent_chunk_key == parent_chunk.chunk_key for chunk in child_chunks)
    assert child_chunks[0].metadata["logical_item_keys"] == [
        article_units[0].logical_item_key
    ]


def test_split_long_unit_and_group_only_sibling_bullets():
    long_unit = ChildUnit(
        content=" ".join(f"word{index:03d}" for index in range(40)),
        block_type="paragraph",
        page_start=3,
        page_end=3,
        item_marker=None,
        item_level=None,
        item_path=[],
        logical_item_key=None,
        parent_item_key=None,
        legal_unit_type="none",
    )

    parts = split_long_child_unit(
        long_unit,
        child_chunk_size=100,
        child_chunk_overlap=20,
    )

    assert len(parts) > 1
    assert [part.split_index for part in parts] == list(range(len(parts)))
    assert {part.split_count for part in parts} == {len(parts)}
    assert all(len(part.content) <= 100 for part in parts)
    assert set(parts[0].content.split()) & set(parts[1].content.split())

    bullets = [
        ChildUnit(
            content=f"- Bullet {index}",
            block_type="bullet_item",
            page_start=3,
            page_end=3,
            item_marker="-",
            item_level=2,
            item_path=["1. Khoản cha", f"- Bullet {index}"],
            logical_item_key=f"item:{index}",
            parent_item_key=parent_key,
            legal_unit_type="bullet",
        )
        for index, parent_key in [(1, "item:parent-a"), (2, "item:parent-a"), (3, "item:parent-b")]
    ]

    grouped = group_short_bullet_units(bullets, child_chunk_size=100)

    assert [unit.block_type for unit in grouped] == ["bullet_group", "bullet_item"]
    assert grouped[0].logical_item_keys == ["item:1", "item:2"]
    assert grouped[1].parent_item_key == "item:parent-b"


def test_table_and_code_splits_stay_at_their_source_position():
    blocks = [
        StructuralBlock("paragraph", "before", 4, 4, 0),
        StructuralBlock(
            "table",
            "| Col | Value |\n| --- | --- |\n| A | one |\n| B | two |",
            4,
            4,
            1,
            logical_table_key="table:000001",
        ),
        StructuralBlock("paragraph", "between", 4, 4, 2),
        StructuralBlock(
            "code",
            "```python\nvalue = 1\nvalue += 2\nprint(value)\n```",
            4,
            4,
            3,
            logical_code_key="code:000003",
        ),
        StructuralBlock("paragraph", "after", 4, 4, 4),
    ]
    section = build_parent_sections(blocks)[0]

    units, reports = build_child_units(
        section,
        child_chunk_size=45,
        child_chunk_overlap=5,
    )

    assert reports == []
    assert [unit.block_type for unit in units] == [
        "paragraph",
        "table",
        "table",
        "paragraph",
        "code",
        "code",
        "paragraph",
    ]
    assert units[0].content == "before"
    assert units[3].content == "between"
    assert units[-1].content == "after"
    assert [unit.split_index for unit in units[1:3]] == [0, 1]
    assert {unit.logical_table_key for unit in units[1:3]} == {"table:000001"}
    assert [unit.split_index for unit in units[4:6]] == [0, 1]
    assert {unit.logical_code_key for unit in units[4:6]} == {"code:000003"}
    assert all(unit.content.startswith("```python\n") for unit in units[4:6])
    assert all(unit.content.endswith("\n```") for unit in units[4:6])
