from datetime import date

from pydantic import Field

from app.schemas.base import StrictSchema


class AnswerRequest(StrictSchema):
    question: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)
    recent_topic: str | None = Field(default=None, max_length=2_000)


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


class AnswerResponse(StrictSchema):
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    should_search: bool
    recent_topic: str | None = None
