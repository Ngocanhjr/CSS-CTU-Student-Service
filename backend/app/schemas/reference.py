from app.schemas.base import StrictSchema


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
