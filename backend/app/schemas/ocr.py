from typing import Any

from app.schemas.base import StrictSchema


class OcrDocumentResponse(StrictSchema):
    source_filename: str
    markdown: str
    metadata: dict[str, Any]
    parser: str = "llamaparse_postprocessed"
    ocr_engine: str = "LlamaParse API"
    language: str = "vi"
