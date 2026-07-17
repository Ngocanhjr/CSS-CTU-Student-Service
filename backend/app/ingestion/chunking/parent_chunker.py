from dataclasses import dataclass

from app.ingestion.chunking.text_stats import count_units
from app.ingestion.parsing.structural_parser import StructuralBlock
from app.schemas.chunks import Chunk


@dataclass(frozen=True)
class ParentSection:
    content: str
    blocks: list[StructuralBlock]
    heading_path: list[str]
    page_start: int
    page_end: int


def make_parent_section(
    *,
    blocks: list[StructuralBlock],
    heading_path: list[str],
) -> ParentSection:
    if not blocks:
        raise ValueError("Parent section requires at least one structural block")

    content = "\n\n".join(
        block.raw_content.strip()
        for block in blocks
        if block.raw_content.strip()
    )

    if not content:
        raise ValueError("Parent section content is empty")

    return ParentSection(
        content=content,
        blocks=list(blocks),
        heading_path=list(heading_path),
        page_start=min(block.page_start for block in blocks),
        page_end=max(block.page_end for block in blocks),
    )


def build_parent_sections(
    blocks: list[StructuralBlock],
) -> list[ParentSection]:
    sections: list[ParentSection] = []
    current_blocks: list[StructuralBlock] = []
    current_heading_path = ["document-root"]

    def flush_current_section() -> None:
        if not current_blocks:
            return

        sections.append(
            make_parent_section(
                blocks=current_blocks,
                heading_path=current_heading_path,
            )
        )
        current_blocks.clear()

    for block in blocks:
        if block.block_type == "heading":
            flush_current_section()

            current_heading_path = (
                list(block.heading_path)
                or [block.heading_text or block.raw_content.lstrip("#").strip()]
            )

        current_blocks.append(block)

    flush_current_section()
    return sections


def make_parent_chunk(
    *,
    section: ParentSection,
    document_key: str,
    version_key: str,
    parent_index: int,
    chunk_index: int,
) -> Chunk:
    return Chunk(
        document_key=document_key,
        version_key=version_key,
        chunk_key=f"{version_key}::p::{parent_index:04d}",
        chunk_type="parent",
        content=section.content,
        heading_path=section.heading_path,
        page_start=section.page_start,
        page_end=section.page_end,
        chunk_index=chunk_index,
        token_count=count_units(section.content),
    )