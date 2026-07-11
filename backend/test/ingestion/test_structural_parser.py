from app.ingestion.parsing.page_markers import PageBlock
from app.ingestion.parsing.structural_parser import parse_page_blocks


def test_parse_page_blocks_preserves_structure_and_atomic_blocks() -> None:
    result = parse_page_blocks(
        [
            PageBlock(
                page_number=1,
                content="""# Hồ sơ
1. Thành phần gồm:
a) Đơn đề nghị
- Bản sao CCCD
<!-- ignored
across lines -->
| Cột A | Cột B |
| --- | --- |
| 1 | 2 |
```text
1. không phải item
```""",
            )
        ]
    )

    assert [block.block_type for block in result.blocks] == [
        "heading",
        "numbered_item",
        "lettered_item",
        "bullet_item",
        "table",
        "code",
    ]
    assert result.blocks[2].parent_item_key == result.blocks[1].logical_item_key
    assert result.blocks[3].parent_item_key == result.blocks[2].logical_item_key
    assert result.blocks[4].logical_table_key == "table:000004"
    assert result.blocks[5].logical_code_key == "code:000005"
    assert result.reports == []
