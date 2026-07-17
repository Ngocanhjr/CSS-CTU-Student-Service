from pydantic import Field

from app.schemas.base import StrictSchema


class ReviewCanonicalRequest(StrictSchema):
    canonical_markdown: str = Field(min_length=1)