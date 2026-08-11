from __future__ import annotations

from pydantic import Field

from app.schemas.base import StrictSchema


class ChunkPreviewItem(StrictSchema):
    chunk_key: str
    parent_chunk_key: str | None = None
    chunk_index: int
    chunk_type: str
    content_preview: str
    heading_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    token_count: int | None = None
    item_marker: str | None = None
    item_level: int | None = None
    item_path: list[str] = Field(default_factory=list)
    logical_item_key: str | None = None
    parent_item_key: str | None = None


class ChunkPreviewResponse(StrictSchema):
    document_version_id: int
    parent_chunks: int
    child_chunks: int
    total_chunks: int
    chunks: list[ChunkPreviewItem]
    warnings: list[dict]
    errors: list[dict]


class IndexingResponse(StrictSchema):
    document_version_id: int
    ingestion_job_id: int
    job_status: str
    current_step: str
    parent_chunks: int
    child_chunks: int
    total_chunks: int
    indexed_chunks: int
    qdrant_points: int
    rag_status: str
    warnings: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)


class IndexingJobProgress(StrictSchema):
    ingestion_job_id: int
    document_version_id: int
    job_status: str
    current_step: str
    total_chunks: int
    processed_chunks: int
    remaining_chunks: int
    rag_status: str
    error_message: str | None = None
