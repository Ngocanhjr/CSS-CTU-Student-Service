# Mỗi bước nhận vào dữ liệu gì, trả ra dữ liệu gì, và dữ liệu đó bắt buộc có những trường nào.
# - Chuẩn hóa dữ liệu truyền giữa các bước.
# - Tránh trả kết quả bằng dictionary không có cấu trúc.
# - Giữ metadata phục vụ citation, expansion và debug.
# Định nghĩa dữ liệu dùng trong retrieval:

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


ExpansionReason = Literal[
    "direct_hit",  #chunk tìm thấy trực tiếp bằng dense/sparse
    "parent_context", #chunk cha lấy để bổ sung ngữ cảnh
    "child_expansion", #chunk con được mở rộng thêm
    "sibling_expansion", #chunk cùng cấp
    "split_neighbor", # phần liền kề của nd bị chia nhỏ
]

#Chứa ngữ cảnh của cuộc hội thoại trước khi retrieval
#khi user hỏi câu hỏi khá mơ hồ, thì sẽ tìm lại các câu hỏi trước đó để lấy ngữ cảnh 
@dataclass(frozen=True)
class RetrievalContext:
    current_document_key: str | None = None
    current_version_key: str | None = None
    recent_topic: str | None = None
    used_chunk_keys: tuple[str, ...] = ()

# Kết quả của bước query_resolver.py
# Trả lời cho câu hỏi: có cần chạy retrieval không? Nếu có thì kiếm câu gì và giới hạn trong tài liệu nào
@dataclass(frozen=True)
class QueryDecision:
    should_search: bool
    query: str
    
    response_message: str | None = None #Nội dung hệ thống có thể trả lời trực tiếp.
    clarification_question: str | None = None #Câu hỏi yêu cầu người dùng cung cấp thêm thông tin.
    
    document_key: str | None = None
    version_key: str | None = None
    is_follow_up: bool = False


@dataclass(frozen=True)
class RetrievalResult:
    # Dùng để lket với bảng DocumentChunk
    postgres_chunk_id: int
    postgres_parent_chunk_id: int | None

    document_key: str
    version_key: str

    chunk_key: str
    parent_chunk_key: str | None

    # score ban đầu có thể score sau fusion. Khi rerank sẽ cập nhật lại score
    score: float
    content: str
    title: str

    # Dữ liệu dùng để trích dẫn nguồn
    page_start: int | None
    page_end: int | None
    source_file: str
    source_url: str
    citation: str

    # Cấu trúc tài liệu: giúp hệ thống hiểu chunk nằm ở đâu trong cấu trúc tài liệu.
    heading_path: list[str]
    item_path: list[str]
    legal_unit_type: str

    # key phục vụ expansion: tìm các thành phần có quan hệ logic
    block_type: str | None = None
    logical_item_key: str | None = None
    logical_item_keys: list[str] | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None

    # Một mục quá dài có thể bị chia thành nhiều chunk.
    split_index: int = 0
    split_count: int = 1
    
    # Thứ tự item -> dùng để sắp xếp lại đúng thứ tự
    chunk_index: int | None = None
    item_marker: str | None = None
    item_level: int | None = None

    # kết quả tìm trực tiếp; kết quả được bổ sung sau expansion.
    expansion_reason: ExpansionReason = "direct_hit"
    parent_content: str | None = None

    # Metadata tài liệu phục vụ màn "Chi tiết tài liệu" trên client.
    issued_date: date | None = None
    issuing_authority: str | None = None
    document_type: str | None = None

    # Đường dẫn object trên R2 để client mở file gốc hoặc bản OCR.
    source_path: str = ""
    canonical_markdown_path: str = ""
