from app.schemas.base import StrictSchema
from app.schemas.enums import Audience, Domain, OcrStatus, RagStatus, ReviewStatus

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
    rag_statuses: list[RagStatus]


#ChunkType, EmbeddingStatus, QdrantStatus