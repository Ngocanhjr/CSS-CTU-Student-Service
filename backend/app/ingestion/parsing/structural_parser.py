from dataclasses import dataclass, field
import re

from app.ingestion.parsing.page_markers import PageBlock
from app.schemas.enums import BlockType, Severity


MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
NUMBERED_ITEM_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[.)/])\s+(.+)$")
LETTERED_ITEM_RE = re.compile(r"^([A-Za-zĐđ][.)/])\s+(.+)$")
BULLET_ITEM_RE = re.compile(r"^([-+*])\s+(.+)$")
FENCE_START_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
ITEM_BLOCK_TYPES: set[BlockType] = {
    "numbered_item",
    "lettered_item",
    "bullet_item",
}


@dataclass(frozen=True)
class StructuralBlock:
    block_type: BlockType  # heading | numbered_item | lettered_item | bullet_item | paragraph | table | code
    raw_content: str
    page_start: int
    page_end: int
    source_order: int
    heading_path: list[str] = field(default_factory=list)
    heading_level: int | None = None
    heading_text: str | None = None
    item_marker: str | None = None
    item_level: int | None = None
    item_path: list[str] = field(default_factory=list)
    logical_item_key: str | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    legal_unit_type: str = "none"  # article | clause | point | bullet | none
    confidence: float = 1.0


@dataclass(frozen=True)
class ValidationReport:
    severity: Severity  # warning | error
    code: str
    reason: str
    page: int
    raw_content: str
    current_heading_path: list[str]
    current_item_path: list[str]
    selected_owner: list[str] | None
    candidate_owners: list[list[str]]
    candidate_types: list[str]
    selected_type: str | None
    confidence: float
    file: str | None = None
    
@dataclass(frozen=True)
class StructuralParseResult:
    blocks: list[StructuralBlock]
    reports: list[ValidationReport] = field(default_factory=list)

def parse_page_blocks(page_blocks: list[PageBlock]) -> StructuralParseResult:
    blocks: list[StructuralBlock] = []
    reports: list[ValidationReport] = []
    heading_stack: list[tuple[int, str]] = []
    item_stack: list[StructuralBlock] = []
    source_order = 0
    
    #Tách thành danh sách dòng liên tục
    lines = [
        (page_block.page_number, line)
        for page_block in page_blocks
        for line in page_block.content.splitlines()
    ]
    
    index = 0
    while index < len(lines):
        page_number, line = lines[index]
        stripped_line = line.strip()
        if not stripped_line:
            index += 1
            continue

        if stripped_line.startswith("<!--"):
            index = _consume_html_comment(lines, index)
            continue
        
        # 1. fenced code block
        if FENCE_START_RE.match(stripped_line):
            raw_content, page_start, page_end, index, report = _consume_fenced_code(
                lines, index, heading_stack, item_stack
            )
            blocks.append(_make_code_block(raw_content, page_start, page_end, source_order, heading_stack, item_stack))
            if report is not None:
                reports.append(report)
            source_order += 1
            continue

        # 2. Markdown table
        if _looks_like_table_start(lines, index):
            raw_content, page_start, page_end, index = _consume_table(lines, index)
            blocks.append(_make_table_block(raw_content, page_start, page_end, source_order, heading_stack, item_stack))
            source_order += 1
            continue

        # A paragraph is adjacent nonblank text, not one block per OCR line.
        if not _starts_structural_block(lines, index):
            raw_content, page_start, page_end, index = _consume_paragraph(lines, index)
            blocks.append(
                _make_paragraph_block(
                    raw_content,
                    page_start,
                    page_end,
                    source_order,
                    heading_stack,
                    item_stack,
                )
            )
            source_order += 1
            continue

        # 3-6. Heading/item line-level classification.
        block, report = _classify_line(
            line,
            page_number,
            source_order,
            heading_stack,
            item_stack,
        )
        blocks.append(block)
        if report is not None:
            reports.append(report)

        _update_state(block, heading_stack, item_stack)
        source_order += 1
        index += 1

    return StructuralParseResult(blocks=blocks, reports=reports)
            
LineWithPage = tuple[int, str]


def _consume_html_comment(lines: list[LineWithPage], index: int) -> int:
    """Return index ngay sau closing comment, hoặc EOF nếu comment không đóng."""
    while index < len(lines):
        _, line = lines[index]
        index += 1
        if "-->" in line:
            break
    return index


def _is_closing_fence(line: str, opening_fence: str) -> bool:
    candidate = line.strip()
    return (
        len(candidate) >= len(opening_fence)
        and set(candidate) == {opening_fence[0]}
    )


def _consume_fenced_code(
    lines: list[LineWithPage],
    index: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> tuple[str, int, int, int, ValidationReport | None]:
    start_page, opening_line = lines[index]
    opening_match = FENCE_START_RE.match(opening_line.strip())
    if opening_match is None:
        raise ValueError("Expected fenced code opening")

    opening_fence = opening_match.group(1)
    consumed: list[str] = []
    pages: list[int] = []

    while index < len(lines):
        page_number, line = lines[index]
        consumed.append(line)
        pages.append(page_number)
        index += 1

        if len(consumed) > 1 and _is_closing_fence(line, opening_fence):
            return "\n".join(consumed), min(pages), max(pages), index, None

    heading_path = [text for _, text in heading_stack]
    item_path = item_stack[-1].item_path if item_stack else []
    owner = [*heading_path, *item_path]
    raw_content = "\n".join(consumed)
    report = ValidationReport(
        severity="error",
        code="unclosed_code_fence",
        reason="Fenced code block has no closing fence",
        page=start_page,
        raw_content=raw_content,
        current_heading_path=heading_path,
        current_item_path=item_path,
        selected_owner=owner or None,
        candidate_owners=[owner] if owner else [],
        candidate_types=["code"],
        selected_type="code",
        confidence=1.0,
    )
    return raw_content, min(pages), max(pages), index, report


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return len(cells) >= 2 and all(
        TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells
    )


def _is_table_row(line: str, expected_columns: int) -> bool:
    return "|" in line and len(_table_cells(line)) == expected_columns


def _looks_like_table_start(lines: list[LineWithPage], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    _, header = lines[index]
    _, separator = lines[index + 1]
    header_cells = _table_cells(header)
    return (
        "|" in header
        and len(header_cells) >= 2
        and _is_table_separator(separator)
        and len(_table_cells(separator)) == len(header_cells)
    )


def _consume_table(
    lines: list[LineWithPage],
    index: int,
) -> tuple[str, int, int, int]:
    expected_columns = len(_table_cells(lines[index][1]))
    consumed: list[str] = []
    pages: list[int] = []

    # Header và separator đã được xác nhận bởi _looks_like_table_start().
    for _ in range(2):
        page_number, line = lines[index]
        consumed.append(line)
        pages.append(page_number)
        index += 1

    while index < len(lines):
        page_number, line = lines[index]
        if not line.strip() or not _is_table_row(line, expected_columns):
            break
        consumed.append(line)
        pages.append(page_number)
        index += 1

    return "\n".join(consumed), min(pages), max(pages), index


def _starts_structural_block(lines: list[LineWithPage], index: int) -> bool:
    _, line = lines[index]
    stripped = line.strip()
    return bool(
        stripped.startswith("<!--")
        or FENCE_START_RE.match(stripped)
        or _looks_like_table_start(lines, index)
        or MARKDOWN_HEADING_RE.match(stripped)
        or NUMBERED_ITEM_RE.match(stripped)
        or LETTERED_ITEM_RE.match(stripped)
        or BULLET_ITEM_RE.match(stripped)
    )


def _consume_paragraph(
    lines: list[LineWithPage],
    index: int,
) -> tuple[str, int, int, int]:
    consumed: list[str] = []
    pages: list[int] = []

    while index < len(lines):
        page_number, line = lines[index]
        if not line.strip() or _starts_structural_block(lines, index):
            break
        consumed.append(line)
        pages.append(page_number)
        index += 1

    if not consumed:
        raise ValueError("Expected paragraph content")
    return "\n".join(consumed), min(pages), max(pages), index

def _current_paths(
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> tuple[list[str], list[str]]:
    heading_path = [text for _, text in heading_stack]
    item_path = list(item_stack[-1].item_path) if item_stack else []
    return heading_path, item_path


def _make_code_block(
    raw_content: str,
    page_start: int,
    page_end: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> StructuralBlock:
    heading_path, item_path = _current_paths(heading_stack, item_stack)
    return StructuralBlock(
        block_type="code",
        raw_content=raw_content,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order,
        heading_path=heading_path,
        item_path=item_path,
        logical_code_key=f"code:{source_order:06d}",
    )


def _make_table_block(
    raw_content: str,
    page_start: int,
    page_end: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> StructuralBlock:
    heading_path, item_path = _current_paths(heading_stack, item_stack)
    return StructuralBlock(
        block_type="table",
        raw_content=raw_content,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order,
        heading_path=heading_path,
        item_path=item_path,
        logical_table_key=f"table:{source_order:06d}",
    )


def _make_paragraph_block(
    raw_content: str,
    page_start: int,
    page_end: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> StructuralBlock:
    heading_path, item_path = _current_paths(heading_stack, item_stack)
    return StructuralBlock(
        block_type="paragraph",
        raw_content=raw_content,
        page_start=page_start,
        page_end=page_end,
        source_order=source_order,
        heading_path=heading_path,
        item_path=item_path,
    )


def _numbered_depth(marker: str) -> int:
    normalized = marker.strip().lstrip("(").rstrip(".)/")
    return max(1, len([part for part in normalized.split(".") if part]))


def _resolve_item_level(
    block_type: str,
    marker: str,
    item_stack: list[StructuralBlock],
) -> int:
    if block_type == "numbered_item":
        return _numbered_depth(marker)

    # Marker cùng loại gần nhất là sibling, nên dùng lại level của nó.
    for previous in reversed(item_stack):
        if previous.block_type == block_type and previous.item_level is not None:
            return previous.item_level

    if block_type == "lettered_item":
        for previous in reversed(item_stack):
            if previous.block_type == "numbered_item" and previous.item_level is not None:
                return previous.item_level + 1
        return 1

    # Bullet đầu tiên thuộc item đang mở; nếu không có item cha thì là level 1.
    if item_stack and item_stack[-1].item_level is not None:
        return item_stack[-1].item_level + 1
    return 1


def _has_legal_context(
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> bool:
    return any(
        text.casefold().startswith("điều ") for _, text in heading_stack
    ) or any(
        item.legal_unit_type in {"article", "clause", "point"}
        for item in item_stack
    )


def _classify_line(
    line: str,
    page_number: int,
    source_order: int,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> tuple[StructuralBlock, ValidationReport | None]:
    candidate = line.strip()

    heading_match = MARKDOWN_HEADING_RE.match(candidate)
    if heading_match:
        heading_level = len(heading_match.group(1))
        heading_text = heading_match.group(2).strip()
        heading_path = [
            text for level, text in heading_stack if level < heading_level
        ]
        heading_path.append(heading_text)
        return StructuralBlock(
            block_type="heading",
            raw_content=line,
            page_start=page_number,
            page_end=page_number,
            source_order=source_order,
            heading_path=heading_path,
            heading_level=heading_level,
            heading_text=heading_text,
            legal_unit_type=(
                "article"
                if heading_text.casefold().startswith("điều ")
                else "none"
            ),
        ), None

    match: re.Match[str] | None
    block_type: str
    match = NUMBERED_ITEM_RE.match(candidate)
    if match:
        block_type = "numbered_item"
    else:
        match = LETTERED_ITEM_RE.match(candidate)
        if match:
            block_type = "lettered_item"
        else:
            match = BULLET_ITEM_RE.match(candidate)
            if match:
                block_type = "bullet_item"
            else:
                raise ValueError("Expected heading or item line")

    marker = match.group(1)
    item_level = _resolve_item_level(block_type, marker, item_stack)
    parent = next(
        (
            item
            for item in reversed(item_stack)
            if item.item_level is not None and item.item_level < item_level
        ),
        None,
    )
    item_path = [*(parent.item_path if parent else []), candidate]
    legal_unit_type = "none"
    if _has_legal_context(heading_stack, item_stack):
        legal_unit_type = {
            "numbered_item": "clause",
            "lettered_item": "point",
            "bullet_item": "bullet",
        }[block_type]

    block = StructuralBlock(
        block_type=block_type,
        raw_content=line,
        page_start=page_number,
        page_end=page_number,
        source_order=source_order,
        heading_path=[text for _, text in heading_stack],
        item_marker=marker,
        item_level=item_level,
        item_path=item_path,
        logical_item_key=f"item:{source_order:06d}",
        parent_item_key=parent.logical_item_key if parent else None,
        legal_unit_type=legal_unit_type,
    )

    if item_level <= 1 or parent is not None:
        return block, None

    heading_path = [text for _, text in heading_stack]
    return block, ValidationReport(
        severity="warning",
        code="item_level_jump",
        reason=f"Item starts at level {item_level} without a parent item",
        page=page_number,
        raw_content=line,
        current_heading_path=heading_path,
        current_item_path=item_path,
        selected_owner=heading_path or None,
        candidate_owners=[heading_path] if heading_path else [],
        candidate_types=[block_type],
        selected_type=block_type,
        confidence=0.6,
    )


def _update_state(
    block: StructuralBlock,
    heading_stack: list[tuple[int, str]],
    item_stack: list[StructuralBlock],
) -> None:
    if block.block_type == "heading":
        if block.heading_level is None or block.heading_text is None:
            raise ValueError("Heading block is missing heading metadata")
        while heading_stack and heading_stack[-1][0] >= block.heading_level:
            heading_stack.pop()
        heading_stack.append((block.heading_level, block.heading_text))
        item_stack.clear()
        return

    if block.block_type not in ITEM_BLOCK_TYPES:
        return
    if block.item_level is None:
        raise ValueError("Item block is missing item_level")

    while item_stack:
        current_level = item_stack[-1].item_level
        if current_level is None:
            raise ValueError("Item stack contains an item without item_level")
        if current_level < block.item_level:
            break
        item_stack.pop()
    item_stack.append(block)
