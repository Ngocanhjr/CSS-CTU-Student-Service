"""
schema cho document metadata
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import *

class DocumentBaseMetadata(StrictSchema):
    """
    DocumentMetadata mô tả thông tin về tài liệu sau khi đã được OCR/parser và review, trước khi đưa vào RAG.

    - title: tiêu đề tài liệu, có thể lấy từ metadata hoặc trích xuất từ nội dung.
    - document_type: loại tài liệu, ví dụ: quy_trinh, bieu_mau, hoi_dap, ...
    - responsible_department: tài liệu được gửi tới các bộ phận liên quan
    input: list[str] các department code, ví dụ: ["hoc_vu", "tai_chinh", "nhan_su"]
    or
    responsible_department:
        - PDT 
        - PCTSV
    """
    #Documents
    document_key: str = Field(min_length=1)
    title: str = ""
    document_type: DocumentType
    domain: str = "" #hoc_vu, tai_chinh, nhan_su, phap_ly, ky_thuat, quy_trinh, bieu_mau, hoi_dap, unknown
    audience: list[Audience] = Field(default_factory=list)
    responsible_department: list[str] = Field(default_factory=list)
    
    @field_validator("audience")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


    @field_validator("responsible_department")
    @classmethod
    def clean_department_codes(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            item = item.strip()
            if item and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_/-]*", item):
                raise ValueError("Department code must be letters, numbers, underscore, slash, or dash")
            if item:
                cleaned.append(item)
        return cleaned
    
class DocumentVersionStatusFields(StrictSchema):
    """
    DocumentVersionStatusFields mô tả các trường trạng thái của phiên bản tài liệu, bao gồm trạng thái OCR, review, RAG và ghi chú trạng thái.
    follow enum OcrStatus, ReviewStatus, RagStatus
    """
    ocr_status: OcrStatus = "not_started"
    review_status: ReviewStatus = "not_reviewed"
    rag_status: RagStatus = "not_indexed"
    status_note: str | None = None
    
class DocumentVersionMetadata(DocumentVersionStatusFields):   
    """
    DocumentVersionMetadata mô tả thông tin về phiên bản tài liệu, bao gồm các trường trạng thái và metadata liên quan đến phiên bản.
    - version_key: khóa định danh phiên bản tài liệu.
    - issuing_authority: cơ quan ban hành tài liệu.
    - signer_name: tên người ký tài liệu.
    - code: mã số tài liệu. (Gốc trên bên trái, ví dụ: QĐ-1234, TB-5678)
    - issued_date: ngày ban hành tài liệu.
    - effective_date: ngày hiệu lực chung, dùng khi map mọi responsible_department sang document_recipients.
    - is_latest: đánh dấu phiên bản này có phải là phiên bản mới nhất hay không.
    - source_url: URL nguồn gốc của tài liệu trên web.
    - source_path: đường dẫn lưu file gốc trên server.
    - canonical_markdown_path: đường dẫn tới file Markdown chính thức đã OCR/làm sạch/review, tức file dùng làm nguồn chính để chunk/index vào RAG.
    - file_type: loại file (ví dụ: pdf, docx, md).
    - accessed_date: ngày truy cập tài liệu.
    """
    version_key: str = Field(min_length=1)
    issuing_authority: str | None = None #co quan ban hanh
    signer_name: str | None = None
    
    code: str | None = None
    issued_date: date | None = None
    effective_date: date | None = None
        
    is_latest: bool = False
    
    source_url: str = "" # URL nguồn gốc trên web
    source_path: str | None = None #đường dẫn lưu file gốc trên server
    canonical_markdown_path: str = "" #đường dẫn tới file Markdown chính thức đã OCR/làm sạch/review, tức file dùng làm nguồn chính để chunk/index vào RAG
    file_type: str = "md"
    accessed_date: date | None = None
    
    language: str = "vi"
    
    checksum: str = Field(min_length=1, max_length=64)
    parser: str | None = None
    ocr_engine: str | None = None
    notes: str = ""

    # Validate publish rule
    @model_validator(mode="after")
    def validate_publish_rules(self) -> "DocumentVersionMetadata":
        if self.rag_status != "published":
            return self
        
        if self.ocr_status != "done":
            raise ValueError("published document requires ocr_status done")
        if self.review_status != "approved":
            raise ValueError("published document requires review_status approved")

        return self

class DocumentMetadata(DocumentBaseMetadata, DocumentVersionMetadata):
    #nhận metadata phụ từ YAML
    model_config = ConfigDict(extra="allow")
    

    
    
