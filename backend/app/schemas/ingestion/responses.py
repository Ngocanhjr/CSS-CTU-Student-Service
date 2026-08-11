from app.schemas.base import StrictSchema
from app.schemas.documents import DocumentMetadata
from app.schemas.enums import RagStatus, ReviewStatus
from typing import Any

class CanonicalUploadResponse(StrictSchema):
    document_id: int
    document_version_id: int
    ingestion_job_id: int
    markdown: str
    metadata: DocumentMetadata


class ReviewCanonicalResponse(StrictSchema):
    document_version_id: int
    review_status: ReviewStatus
    rag_status: RagStatus
    markdown: str
    metadata: DocumentMetadata
    

class MarkdownMetadataPreviewResponse(StrictSchema):
    metadata: dict[str, Any]