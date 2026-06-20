from __future__ import annotations

from pydantic import Field

from app.schemas.base import StrictSchema
from app.schemas.enums import (
    AssetType,
    DocumentAssetRelationType,
    FileType,
    RagStatus,
    ReviewStatus,
    ValidityStatus,
)

class AssetMetadata(StrictSchema):
    asset_key: str = Field(min_length=1)
    asset_type: AssetType
    title: str = ""

    file_path: str = ""
    file_type: FileType = "pdf"
    download_url: str = ""
    checksum: str | None = None

    validity_status: ValidityStatus = "unchecked"
    is_latest: bool = True
    review_status: ReviewStatus = "not_reviewed"
    rag_status: RagStatus = "not_indexed"

class DocumentAssetRelation(StrictSchema):
    document_key: str = Field(min_length=1)
    #version_key: str = Field(min_length=1)
    asset_key: str = Field(min_length=1)

    relation_type: DocumentAssetRelationType = "reference"
    required: bool = False
    required_when: str | None = None
    display_order: int = Field(default=0, ge=0)