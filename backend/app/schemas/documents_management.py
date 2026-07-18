from __future__ import annotations

from app.schemas.base import StrictSchema


class DocumentVersionSummary(StrictSchema):
    id: int
    document_id: int
    document_key: str
    title: str
    version_key: str
    version_label: str
    document_type_id: int | None = None
    department_id: int | None = None
    domain: str
    audience: list[str]
    code: str | None = None
    issued_date: str | None = None
    effective_date: str | None = None
    expiry_date: str | None = None
    review_status: str
    validity_status: str
    ocr_status: str
    rag_status: str
    updated_at: str | None = None


class DocumentVersionDetail(DocumentVersionSummary):
    canonical_markdown: str
    canonical_markdown_path: str
    source_path: str
    source_url: str
    checksum: str
