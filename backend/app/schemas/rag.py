from pydantic import Field

from app.schemas.base import StrictSchema


class AnswerRequest(StrictSchema):
    question: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)


class CitationResponse(StrictSchema):
    document_key: str
    version_key: str
    chunk_key: str
    title: str
    page_start: int | None = None
    page_end: int | None = None
    citation: str


class AnswerResponse(StrictSchema):
    answer: str
    citations: list[CitationResponse] = Field(default_factory=list)
    should_search: bool
