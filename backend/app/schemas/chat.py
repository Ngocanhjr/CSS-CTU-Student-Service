from __future__ import annotations

from pydantic import Field

from app.schemas.base import StrictSchema


class ChatFilters(StrictSchema):
    """Optional filters for chat retrieval."""

    document_type: str | None = None
    domain: str | None = None


class ChatRequest(StrictSchema):
    """Request schema for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    filters: ChatFilters | None = None


class SourceDocument(StrictSchema):
    """Source document information returned with chat response."""

    document_key: str
    version_key: str
    title: str
    chunk_key: str
    relevance_score: float
    snippet: str
    heading_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None


class ChatMetadata(StrictSchema):
    """Metadata about the chat processing."""

    retrieval_time_ms: int
    generation_time_ms: int
    chunks_retrieved: int
    model: str


class ChatResponse(StrictSchema):
    """Response schema for chat endpoint."""

    answer: str
    conversation_id: str
    sources: list[SourceDocument]
    metadata: ChatMetadata
