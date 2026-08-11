from dataclasses import dataclass, replace

from app.ingestion.chunking.parent_chunker import ParentSection
from app.ingestion.parsing.structural_parser import (
    StructuralBlock,
    ValidationReport,
)

from langchain_text_splitters import RecursiveCharacterTextSplitter
import re

from app.ingestion.chunking.table_blocks import split_large_table_block
from app.ingestion.chunking.text_stats import count_units
from app.schemas.chunks import Chunk

@dataclass(frozen=True)
class ChildUnit:
    content: str
    block_type: str
    page_start: int
    page_end: int

    item_marker: str | None
    item_level: int | None
    item_path: list[str]

    logical_item_key: str | None
    parent_item_key: str | None
    legal_unit_type: str

    logical_item_keys: list[str] | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None

    split_index: int = 0
    split_count: int = 1


def child_unit_from_item(block: StructuralBlock) -> ChildUnit:
    return ChildUnit(
        content=block.raw_content.strip(),
        block_type=block.block_type,
        page_start=block.page_start,
        page_end=block.page_end,
        item_marker=block.item_marker,
        item_level=block.item_level,
        item_path=list(block.item_path),
        logical_item_key=block.logical_item_key,
        parent_item_key=block.parent_item_key,
        legal_unit_type=block.legal_unit_type,
    )


def child_unit_from_block(block: StructuralBlock) -> ChildUnit:
    if block.block_type not in {"paragraph", "table", "code"}:
        raise ValueError(
            f"Cannot create standalone child unit from {block.block_type!r}"
        )

    return ChildUnit(
        content=block.raw_content.strip(),
        block_type=block.block_type,
        page_start=block.page_start,
        page_end=block.page_end,
        item_marker=None,
        item_level=None,
        item_path=list(block.item_path),
        logical_item_key=None,
        parent_item_key=block.parent_item_key,
        legal_unit_type=block.legal_unit_type,
        logical_table_key=block.logical_table_key,
        logical_code_key=block.logical_code_key,
    )


def append_block_to_unit(
    unit: ChildUnit,
    block: StructuralBlock,
) -> ChildUnit:
    block_content = block.raw_content.strip()
    if not block_content:
        return unit

    return replace(
        unit,
        content=f"{unit.content}\n\n{block_content}",
        page_start=min(unit.page_start, block.page_start),
        page_end=max(unit.page_end, block.page_end),
    )


def make_heading_content_unit(
    heading: StructuralBlock,
) -> ChildUnit:
    return ChildUnit(
        content=heading.raw_content.strip(),
        block_type="heading",
        page_start=heading.page_start,
        page_end=heading.page_end,
        item_marker=None,
        item_level=None,
        item_path=[],
        logical_item_key=None,
        parent_item_key=None,
        legal_unit_type=heading.legal_unit_type,
    )


def build_structural_child_units(
    section: ParentSection,
) -> tuple[list[ChildUnit], list[ValidationReport]]:
    units: list[ChildUnit] = []
    reports: list[ValidationReport] = []
    current_item: ChildUnit | None = None
    heading: StructuralBlock | None = None

    def flush_current_item() -> None:
        nonlocal current_item

        if current_item is not None:
            units.append(current_item)
            current_item = None

    for block in section.blocks:
        if block.block_type == "heading":
            flush_current_item()
            heading = block
            continue

        if block.block_type in {
            "numbered_item",
            "lettered_item",
            "bullet_item",
        }:
            flush_current_item()
            current_item = child_unit_from_item(block)
            continue

        if block.block_type in {"table", "code"}:
            flush_current_item()
            units.append(child_unit_from_block(block))
            continue

        if block.block_type == "paragraph":
            if current_item is not None:
                current_item = append_block_to_unit(current_item, block)
            else:
                units.append(child_unit_from_block(block))

    flush_current_item()

    if units:
        return units, reports

    if heading is not None and heading.legal_unit_type == "article":
        units.append(make_heading_content_unit(heading))
        return units, reports

    reports.append(
        ValidationReport(
            severity="warning",
            code="context_only_parent",
            reason="Parent has no child content; heading is context-only",
            page=section.page_start,
            raw_content=heading.raw_content if heading else "",
            current_heading_path=section.heading_path,
            current_item_path=[],
            selected_owner=section.heading_path,
            candidate_owners=[section.heading_path],
            candidate_types=["context_only"],
            selected_type="context_only",
            confidence=1.0,
        )
    )

    return units, reports

def build_child_splitter(
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )


def split_long_child_unit(
    unit: ChildUnit,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> list[ChildUnit]:
    if len(unit.content) <= child_chunk_size:
        return [unit]

    splitter = build_child_splitter(
        child_chunk_size=child_chunk_size,
        child_chunk_overlap=child_chunk_overlap,
    )
    contents = [
        content.strip()
        for content in splitter.split_text(unit.content)
        if content.strip()
    ]
    split_count = len(contents)

    return [
        replace(
            unit,
            content=content,
            split_index=index,
            split_count=split_count,
        )
        for index, content in enumerate(contents)
    ]


def group_short_bullet_units(
    units: list[ChildUnit],
    *,
    child_chunk_size: int,
) -> list[ChildUnit]:
    result: list[ChildUnit] = []
    group: list[ChildUnit] = []

    def flush_group() -> None:
        if not group:
            return

        if len(group) == 1:
            result.append(group[0])
            group.clear()
            return

        first = group[0]
        logical_item_keys = [
            key
            for unit in group
            for key in (
                unit.logical_item_keys
                or ([unit.logical_item_key] if unit.logical_item_key else [])
            )
        ]

        result.append(
            replace(
                first,
                content="\n".join(unit.content for unit in group),
                block_type="bullet_group",
                page_start=min(unit.page_start for unit in group),
                page_end=max(unit.page_end for unit in group),
                item_marker=None,
                item_level=None,
                item_path=first.item_path[:-1],
                logical_item_key=None,
                logical_item_keys=logical_item_keys,
            )
        )
        group.clear()

    for unit in units:
        if unit.block_type != "bullet_item":
            flush_group()
            result.append(unit)
            continue

        merged_size = (
            sum(len(member.content) for member in group)
            + len(group)
            + len(unit.content)
        )
        same_parent = (
            not group
            or unit.parent_item_key == group[0].parent_item_key
        )

        if same_parent and merged_size <= child_chunk_size:
            group.append(unit)
            continue

        flush_group()
        group.append(unit)

    flush_group()
    return result
FENCED_CODE_START_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def split_table_child_unit(
    unit: ChildUnit,
    *,
    child_chunk_size: int,
) -> list[ChildUnit]:
    contents = split_large_table_block(
        unit.content,
        max_size=child_chunk_size,
    )

    if len(contents) == 1:
        return [unit]

    split_count = len(contents)

    return [
        replace(
            unit,
            content=content,
            split_index=index,
            split_count=split_count,
        )
        for index, content in enumerate(contents)
    ]


def parse_fenced_code(
    content: str,
) -> tuple[str, str, list[str], str]:
    lines = content.strip().splitlines()

    if len(lines) < 2:
        raise ValueError("Fenced code block is incomplete")

    opening_line = lines[0].strip()
    match = FENCED_CODE_START_RE.fullmatch(opening_line)

    if match is None:
        raise ValueError("Code block requires an opening fence")

    opening_fence = match.group(1)
    language = match.group(2).strip()
    closing_fence = lines[-1].strip()

    if (
        len(closing_fence) < len(opening_fence)
        or set(closing_fence) != {opening_fence[0]}
    ):
        raise ValueError("Code block requires a matching closing fence")

    return (
        opening_fence,
        language,
        lines[1:-1],
        closing_fence,
    )


def group_complete_lines(
    lines: list[str],
    *,
    max_size: int,
) -> list[list[str]]:
    if max_size <= 0:
        return [lines]

    groups: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        candidate = "\n".join([*current, line])

        if current and len(candidate) > max_size:
            groups.append(current)
            current = [line]
            continue

        current.append(line)

    if current:
        groups.append(current)

    # ponytail: một code line quá dài vẫn giữ nguyên để không phá cú pháp.
    return groups


def split_code_child_unit(
    unit: ChildUnit,
    *,
    child_chunk_size: int,
) -> list[ChildUnit]:
    if len(unit.content) <= child_chunk_size:
        return [unit]

    (
        opening_fence,
        language,
        body_lines,
        closing_fence,
    ) = parse_fenced_code(unit.content)

    opening_line = f"{opening_fence}{language}"
    body_size = (
        child_chunk_size
        - len(opening_line)
        - len(closing_fence)
        - 2
    )

    groups = group_complete_lines(
        body_lines,
        max_size=body_size,
    )

    if len(groups) <= 1:
        return [unit]

    split_count = len(groups)

    return [
        replace(
            unit,
            content="\n".join(
                [
                    opening_line,
                    *group,
                    closing_fence,
                ]
            ),
            split_index=index,
            split_count=split_count,
        )
        for index, group in enumerate(groups)
    ]


def build_child_units(
    section: ParentSection,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> tuple[list[ChildUnit], list[ValidationReport]]:
    units, reports = build_structural_child_units(section)

    units = group_short_bullet_units(
        units,
        child_chunk_size=child_chunk_size,
    )

    result: list[ChildUnit] = []

    for unit in units:
        if unit.block_type == "table":
            result.extend(
                split_table_child_unit(
                    unit,
                    child_chunk_size=child_chunk_size,
                )
            )
            continue

        if unit.block_type == "code":
            result.extend(
                split_code_child_unit(
                    unit,
                    child_chunk_size=child_chunk_size,
                )
            )
            continue

        if len(unit.content) > child_chunk_size:
            result.extend(
                split_long_child_unit(
                    unit,
                    child_chunk_size=child_chunk_size,
                    child_chunk_overlap=child_chunk_overlap,
                )
            )
            continue

        result.append(unit)

    return result, reports

def make_child_chunks(
    *,
    child_units: list[ChildUnit],
    parent_chunk: Chunk,
    child_start_index: int,
    chunk_start_index: int,
) -> list[Chunk]:
    if parent_chunk.chunk_type != "parent":
        raise ValueError("Child chunks require a parent chunk")

    chunks: list[Chunk] = []

    for offset, unit in enumerate(child_units):
        child_number = child_start_index + offset

        logical_item_keys = (
            unit.logical_item_keys
            or (
                [unit.logical_item_key]
                if unit.logical_item_key
                else []
            )
        )

        chunks.append(
            Chunk(
                document_key=parent_chunk.document_key,
                version_key=parent_chunk.version_key,
                chunk_key=(
                    f"{parent_chunk.version_key}"
                    f"::c::{child_number:04d}"
                ),
                parent_chunk_key=parent_chunk.chunk_key,
                chunk_type="child",
                content=unit.content,
                heading_path=parent_chunk.heading_path,
                page_start=unit.page_start,
                page_end=unit.page_end,
                chunk_index=chunk_start_index + offset,
                token_count=count_units(unit.content),
                metadata={
                    "block_type": unit.block_type,
                    "item_marker": unit.item_marker,
                    "item_level": unit.item_level,
                    "item_path": unit.item_path,
                    "logical_item_key": unit.logical_item_key,
                    "logical_item_keys": logical_item_keys,
                    "parent_item_key": unit.parent_item_key,
                    "logical_table_key": unit.logical_table_key,
                    "logical_code_key": unit.logical_code_key,
                    "legal_unit_type": unit.legal_unit_type,
                    "split_index": unit.split_index,
                    "split_count": unit.split_count,
                },
            )
        )

    return chunks