# Các model hỗ trợ Qdrant:

# RetrievalFilter: bộ lọc tìm kiếm;
# QdrantChunkPayload: cấu trúc payload;
# QdrantSearchResult: kết quả tìm kiếm.

from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass(frozen=True )
class RetrievalFilter:
    department: str | None = None
    audience: str | None = None
    document_type: str | None = None
    domain: str | None = None
    document_key: str | None = None
    version_key: str | None = None
    chunk_type: str | None = "child"
    review_status: str | None = None
    rag_status: str | None = None
    audience: str | None = None
    
class QdrantChunkPayload(BaseModel):
    document_key: str
    version_key: str
    title: str
    source_file: str
    document_type: str
    domain: str
    audience: list[str]
    audience_student: bool
    review_status: str
    rag_status: str
    is_latest: bool
    chunk_key: str
    parent_chunk_key: str | None
    chunk_type: str
    heading_path: list[str]
    item_path: list[str]
    postgres_chunk_id: int
    chunk_index: int
    source_url: str | None = None
    postgres_parent_chunk_id: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    block_type: str = "paragraph"
    legal_unit_type: str = "none"
    logical_item_key: str | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    logical_item_keys: list[str] = Field(default_factory=list)
    split_index: int = 0
    split_count: int = 1
    item_marker: str | None = None
    item_level: int | None = None
    

@dataclass(frozen=True)
class QdrantSearchResult:
    point_id: str
    score: float
    payload: dict
