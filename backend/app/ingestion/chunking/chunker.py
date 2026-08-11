from dataclasses import dataclass

from app.ingestion.chunking.child_chunker import (
    build_child_units,
    make_child_chunks,
)
from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)
from app.ingestion.markdown_reader import MarkdownDocument
from app.ingestion.parsing.page_markers import split_body_by_page_markers
from app.ingestion.parsing.structural_parser import (
    ValidationReport,
    parse_page_blocks,
)
from app.schemas.chunks import Chunk


@dataclass(frozen=True)
class ChunkingResult:
    parent_chunks: list[Chunk]
    child_chunks: list[Chunk]
    warnings: list[ValidationReport]
    errors: list[ValidationReport]


def validate_chunking_parameters(
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> None:
    if child_chunk_size <= 0:
        raise ValueError("child_chunk_size must be greater than zero")

    if child_chunk_overlap < 0:
        raise ValueError("child_chunk_overlap must not be negative")

    if child_chunk_overlap >= child_chunk_size:
        raise ValueError(
            "child_chunk_overlap must be smaller than child_chunk_size"
        )


def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> ChunkingResult:
    if not body.strip():
        raise ValueError("Markdown body is empty")

    if not document_key.strip():
        raise ValueError("document_key is required")

    if not version_key.strip():
        raise ValueError("version_key is required")

    validate_chunking_parameters(
        child_chunk_size=child_chunk_size,
        child_chunk_overlap=child_chunk_overlap,
    )

    page_blocks = split_body_by_page_markers(body)
    parse_result = parse_page_blocks(page_blocks)
    sections = build_parent_sections(parse_result.blocks)

    parent_chunks: list[Chunk] = []
    child_chunks: list[Chunk] = []
    reports = list(parse_result.reports)

    child_counter = 1
    chunk_index = 0

    for parent_counter, section in enumerate(
        sections,
        start=1,
    ):
        parent_chunk = make_parent_chunk(
            section=section,
            document_key=document_key,
            version_key=version_key,
            parent_index=parent_counter,
            chunk_index=chunk_index,
        )
        parent_chunks.append(parent_chunk)
        chunk_index += 1

        child_units, section_reports = build_child_units(
            section,
            child_chunk_size=child_chunk_size,
            child_chunk_overlap=child_chunk_overlap,
        )
        reports.extend(section_reports)

        section_child_chunks = make_child_chunks(
            child_units=child_units,
            parent_chunk=parent_chunk,
            child_start_index=child_counter,
            chunk_start_index=chunk_index,
        )
        child_chunks.extend(section_child_chunks)

        child_counter += len(section_child_chunks)
        chunk_index += len(section_child_chunks)

    return ChunkingResult(
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
        warnings=[
            report
            for report in reports
            if report.severity == "warning"
        ],
        errors=[
            report
            for report in reports
            if report.severity == "error"
        ],
    )


def chunk_markdown_document(
    document: MarkdownDocument,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> ChunkingResult:
    return chunk_markdown_body(
        body=document.body,
        document_key=document.metadata.document_key,
        version_key=document.metadata.version_key,
        child_chunk_size=child_chunk_size,
        child_chunk_overlap=child_chunk_overlap,
    )