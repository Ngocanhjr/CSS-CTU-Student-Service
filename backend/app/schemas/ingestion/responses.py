from app.schemas.base import StrictSchema
from app.schemas.documents import DocumentMetadata


class CanonicalUploadResponse(StrictSchema):
    document_id: int
    document_version_id: int
    ingestion_job_id: int

    canonical_markdown_path: str
    markdown: str
    metadata: DocumentMetadata