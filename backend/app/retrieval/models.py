# - Chuẩn hóa dữ liệu truyền giữa các bước.
# - Tránh trả kết quả bằng dictionary không có cấu trúc.
# - Giữ metadata phục vụ citation, expansion và debug.
# Định nghĩa dữ liệu dùng trong retrieval:

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ExpansionReason = Literal[
    "direct_hit",
    "parent_context",
    "child_expansion",
    "sibling_expansion",
    "split_neighbor",
]


@dataclass(frozen=True)
class RetrievalContext:
    current_document_key: str | None = None
    current_version_key: str | None = None
    recent_topic: str | None = None


@dataclass(frozen=True)
class QueryDecision:
    should_search: bool
    query: str
    clarification_question: str | None = None
    document_key: str | None = None
    version_key: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    postgres_chunk_id: int
    postgres_parent_chunk_id: int | None

    document_key: str
    version_key: str

    chunk_key: str
    parent_chunk_key: str | None

    score: float
    content: str
    title: str

    page_start: int | None
    page_end: int | None

    source_file: str
    source_url: str
    citation: str

    heading_path: list[str]
    item_path: list[str]
    legal_unit_type: str

    block_type: str | None = None
    logical_item_key: str | None = None
    logical_item_keys: list[str] | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None

    split_index: int = 0
    split_count: int = 1
    chunk_index: int | None = None
    item_marker: str | None = None
    item_level: int | None = None

    expansion_reason: ExpansionReason = "direct_hit"
    parent_content: str | None = None
