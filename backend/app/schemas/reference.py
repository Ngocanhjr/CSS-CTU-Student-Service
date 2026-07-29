from app.schemas.base import StrictSchema
from app.schemas.enums import (
    AssetType,
    Audience,
    Domain,
    OcrStatus,
    RagStatus,
    ReviewStatus,
    ValidityStatus,
)

class DocumentTypeResponse(StrictSchema):
    id: int
    code: str
    name: str
    is_active: bool


class DepartmentResponse(StrictSchema):
    id: int
    code: str
    name: str
    is_active: bool
    
class EnumOptionsResponse(StrictSchema):
    domains: list[Domain]
    audiences: list[Audience]
    ocr_statuses: list[OcrStatus]
    review_statuses: list[ReviewStatus]
    validity_statuses: list[ValidityStatus]
    rag_statuses: list[RagStatus]
    asset_types: list[AssetType]


#ChunkType, EmbeddingStatus, QdrantStatus
