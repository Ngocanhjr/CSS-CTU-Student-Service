from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.base import StrictSchema


class ConversationContext(StrictSchema):
    """Client-held context used to scope a follow-up RAG request.

    This contains identifiers and a short topic only.  It never contains
    document content, and the retrieval layer remains responsible for
    validating the supplied document/version against its eligibility rules.
    """

    recent_topic: str | None = Field(default=None, max_length=2_000)
    document_key: str | None = Field(default=None, max_length=255)
    version_key: str | None = Field(default=None, max_length=255)
    used_chunk_keys: list[str] = Field(default_factory=list, max_length=100)


class AnswerRequest(StrictSchema):
    question: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)
    # ``recent_topic`` is retained temporarily for clients released before
    # the structured ``conversation_context`` contract.
    recent_topic: str | None = Field(default=None, max_length=2_000)
    conversation_context: ConversationContext | None = None


class CitationResponse(StrictSchema):
    document_key: str
    version_key: str
    chunk_key: str

    title: str
    page_start: int | None = None
    page_end: int | None = None
    citation: str

    # Metadata phục vụ màn Chi tiết tài liệu.
    source_file: str
    issued_date: date | None = None
    issuing_authority: str | None = None
    document_type: str | None = None

    # Link trang web nguồn.
    source_url: str | None = None

    # Object key của file PDF gốc trên Cloudflare R2.
    source_path: str | None = None

    # Object key của file Markdown OCR trên Cloudflare R2.
    canonical_markdown_path: str | None = None


class RagAnswer(StrictSchema):
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    answer_status: Literal["answered", "insufficient_evidence"]


class AnswerResponse(StrictSchema):
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    should_search: bool
    answer_status: Literal["answered", "insufficient_evidence"]
    recent_topic: str | None = None
    conversation_context: ConversationContext | None = None
