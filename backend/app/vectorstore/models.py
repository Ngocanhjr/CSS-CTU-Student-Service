# Các model hỗ trợ Qdrant:

# RetrievalFilter: bộ lọc tìm kiếm;
# QdrantChunkPayload: cấu trúc payload;
# QdrantSearchResult: kết quả tìm kiếm.

from dataclasses import dataclass
from pydantic import BaseModel

@dataclass(frozen=True )
class RetrievalFilter:
    department: str | None = None
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
    department: str
    document_type: str
    domain: str
    chunk_key: str
    parent_chunk_key: str | None
    chunk_type: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    content: str
    postgres_chunk_id: int | None = None
    review_status: str = "not_reviewed"
    rag_status: str = "not_indexed"
    is_latest: bool = False
    audience: list[str] = []
    

@dataclass(frozen=True)
class QdrantSearchResult:
    score: float
    payload: dict
