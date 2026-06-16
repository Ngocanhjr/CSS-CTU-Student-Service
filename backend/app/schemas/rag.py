from __future__ import annotations
from datetime import datetime, date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import *

class DocumentMetadata(BaseModel):
    """
    DocumentMetadata mô tả thông tin về tài liệu sau khi đã được OCR/parser và review, trước khi đưa vào RAG.

    - title: tiêu đề tài liệu, có thể lấy từ metadata hoặc trích xuất từ nội dung.
    """
    
    
