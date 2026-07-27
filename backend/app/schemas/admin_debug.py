from __future__ import annotations

from app.schemas.base import StrictSchema


class ChunkDebugItem(StrictSchema):
    id: int
    chunk_key: str
    chunk_type: str
    parent_chunk_key: str | None
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    token_count: int | None
    content_preview: str
    has_embedding: bool


class ChunksDebugResponse(StrictSchema):
    document_version_id: int
    total_chunks: int
    parent_chunks: int
    child_chunks: int
    chunks: list[ChunkDebugItem]


class VectorDebugItem(StrictSchema):
    point_id: str
    chunk_key: str
    score: float | None
    payload: dict


class VectorsDebugResponse(StrictSchema):
    document_version_id: int
    collection: str
    total_vectors: int
    vectors: list[VectorDebugItem]


class SearchTestResult(StrictSchema):
    chunk_key: str
    document_version_id: int | None
    title: str
    score: float
    content_preview: str


class SearchTestResponse(StrictSchema):
    query: str
    embedding_time_ms: int
    search_time_ms: int
    results: list[SearchTestResult]
