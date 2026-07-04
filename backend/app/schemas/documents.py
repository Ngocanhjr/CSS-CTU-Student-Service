"""
schema cho document metadata
"""

from __future__ import annotations

from datetime import datetime, date
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import *

class DocumentBaseMetadata(StrictSchema):
    """
    DocumentMetadata mô tả thông tin về tài liệu sau khi đã được OCR/parser và review, trước khi đưa vào RAG.

    - title: tiêu đề tài liệu, có thể lấy từ metadata hoặc trích xuất từ nội dung.
    """
    #Documents
    document_key: str = Field(min_length=1)
    title: str = ""
    
    department: str = ""
    document_type: DocumentType
    domain: str = "" #hoc_vu, tai_chinh, nhan_su, phap_ly, ky_thuat, quy_trinh, bieu_mau, hoi_dap, unknown
    audience: list[str] = Field(default_factory=list)
    @field_validator("audience")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @field_validator("department")
    @classmethod
    def     validate_department_code(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_/-]*", value):
            raise ValueError("Department code must be uppercase letters, numbers, or underscores")
        return value
class DocumentVersionStatus(StrictSchema):
    validity_status: ValidityStatus = "unchecked"
    collection_status: CollectionStatus = "collected"
    ocr_status: OcrStatus = "not_started"
    review_status: ReviewStatus = "not_reviewed"
    rag_status: RagStatus = "not_indexed"
    status_note: str = ""
    
class DocumentVersionMetadata(DocumentVersionStatus):   
    version_key: str = Field(min_length=1)
    version_label: str = "" 
    code: str | None = None
    issued_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    
    version_role: VersionRole = "base"
        
    is_latest: bool = False

    replaces: list[str] = Field(default_factory=list)
    replaced_by: list[str] = Field(default_factory=list)
    amends: list[str] = Field(default_factory=list)
    amended_by: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    supplemented_by: list[str] = Field(default_factory=list)
    
    source_url: str = "" # URL nguồn gốc trên web
    source_file: str = "" #tên file gốc
    source_path: str | None = None #đường dẫn lưu file gốc trên server
    canonical_markdown_path: str = "" #đường dẫn tới file Markdown chính thức đã OCR/làm sạch/review, tức file dùng làm nguồn chính để chunk/index vào RAG
    file_type: str = "md"
    accessed_date: date | None = None
    
    language: str = "vi"
    citation_type: CitationType = "page"
    
    related_asset_keys: list[str] = Field(default_factory=list)
    
    checksum: str = Field(min_length=1)
    parser: str | None = None
    ocr_engine: str | None = None
    notes: str = ""
    
    @field_validator(
        "replaces", 
        "replaced_by", 
        "amends", 
        "amended_by", 
        "supplements", 
        "supplemented_by",
        "related_asset_keys",
    )
    
    @classmethod
    def clean_version_relations(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]
    
    # Validate date range
    @model_validator(mode="after")
    def validate_version_range(self) -> "DocumentVersionMetadata":
        if self.effective_date and self.expiry_date and self.effective_date > self.expiry_date:
            raise ValueError("Effective date must be before expiry date")
        return self

    @model_validator(mode="after")
    def validate_version_rules(self) -> "DocumentVersionMetadata":
        #Nếu tài liệu đã bị thay thế (replaced) thì phải biết nó bị thay bởi version nào (replaced_by).
        if self.validity_status == "replaced" and not self.replaced_by:
            raise ValueError("Replaced document requires replaced_by")
        
        #Nếu version này là bản thay thế thì phải khai báo nó thay thế bản nào (replaces).
        if self.version_role == "replacement" and not self.replaces:
            raise ValueError("Replacement version requires replaces")
        
        #Nếu version này là bản sửa đổi thì phải khai báo nó sửa bản nào (amends).
        if self.version_role == "amendment" and not self.amends:
            raise ValueError("Amendment version requires amends")
        
        #Nếu version này là bản bổ sung thì phải khai báo nó bổ sung cho bản nào (supplements).
        if self.version_role == "supplement" and not self.supplements:
            raise ValueError("Supplement version requires supplements")
        
        return self
    
    # Validate publish rule
    @model_validator(mode="after")
    def validate_publish_rules(self) -> "DocumentVersionMetadata":
        if self.rag_status != "published":
            return self
        
        if self.ocr_status != "done":
            raise ValueError("published document requires ocr_status done")
        if self.review_status != "approved":
            raise ValueError("published document requires review_status approved")
        if self.validity_status != "valid":
            raise ValueError("published document requires validity_status valid")
        
        return self


class DocumentMetadata(DocumentBaseMetadata, DocumentVersionMetadata):
    #nhận metadata phụ từ YAML
    model_config = ConfigDict(extra="allow")
    

    
    
