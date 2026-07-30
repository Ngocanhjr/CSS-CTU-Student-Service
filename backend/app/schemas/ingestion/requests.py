from datetime import date

from pydantic import Field

from app.schemas.assets import AssetWrite
from app.schemas.base import StrictSchema
from app.schemas.enums import (
    Audience,
    DocumentType,
    Domain,
)

class ReviewCanonicalRequest(StrictSchema):
    canonical_markdown: str = Field(min_length=1)
    assets: list[AssetWrite] = Field(default_factory=list)


class RawMarkdownUploadMetadata(StrictSchema):
    title: str = Field(min_length=1)
    document_key: str = Field(min_length=1)
    version_key: str = Field(min_length=1)
    document_type: DocumentType
    domain: Domain = "unknown"
    audience: list[Audience] = Field(default_factory=list)
    responsible_department: list[str] = Field(min_length=1)
    code: str | None = None
    issuing_authority: str | None = None
    signer_name: str | None = None
    issued_date: date | None = None
    effective_date: date | None = None
    is_latest: bool = False
    source_url: str = ""
    language: str = "vi"
    notes: str = ""
