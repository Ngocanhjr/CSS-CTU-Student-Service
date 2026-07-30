from __future__ import annotations

from datetime import date, datetime

from app.schemas.base import StrictSchema
from app.schemas.assets import AssetWrite, LinkedAssetResponse
from pydantic import Field


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
    document_type_code: str
    canonical_markdown: str
    canonical_markdown_path: str
    source_path: str
    source_url: str
    checksum: str
    responsible_department: list[str] = Field(default_factory=list)
    assets: list[LinkedAssetResponse] = Field(default_factory=list)
    last_job_id: int | None = None
    last_job_status: str | None = None
    last_job_step: str | None = None
    last_job_error: str | None = None
    last_job_processed_chunks: int | None = None
    last_job_total_chunks: int | None = None


class DocumentVersionUpdateMetadata(StrictSchema):
    """Editable fields exposed by the admin document editor."""

    title: str
    document_type_id: int | None = None
    department_id: int | None = None
    domain: str = ""
    audience: list[str] = Field(default_factory=list)
    code: str | None = None
    version_label: str | None = None
    issued_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    validity_status: str = "unknown"


class DocumentVersionUpdateRequest(StrictSchema):
    metadata: DocumentVersionUpdateMetadata
    canonical_markdown: str


class DocumentVersionUpdateResponse(StrictSchema):
    updated: bool
    document: DocumentVersionDetail


class DocumentAssetsUpdateRequest(StrictSchema):
    assets: list[AssetWrite] = Field(default_factory=list)


class DeindexResponse(StrictSchema):
    document_version_id: int
    chunks_deleted: int
    vectors_deleted: int
    new_rag_status: str


class PublishResponse(StrictSchema):
    document_version_id: int
    rag_status: str
    published_at: datetime


class UnpublishResponse(StrictSchema):
    document_version_id: int
    rag_status: str
    unpublished_at: datetime
