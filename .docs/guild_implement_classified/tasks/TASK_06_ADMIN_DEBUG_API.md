# Task 06: Admin Debug APIs

## Mục tiêu
APIs hỗ trợ admin debug và kiểm tra dữ liệu chunks/vectors trong hệ thống.

## Endpoints cần implement

### 1. GET /api/v1/admin/chunks/{document_version_id}
Xem danh sách chunks của một document version.

```json
Response 200:
{
  "document_version_id": 1,
  "total_chunks": 15,
  "parent_chunks": 5,
  "child_chunks": 10,
  "chunks": [
    {
      "id": 1,
      "chunk_key": "qd-2024-001-p1",
      "chunk_type": "parent",
      "parent_chunk_key": null,
      "heading_path": ["Chương I", "Điều 1"],
      "page_start": 1,
      "page_end": 2,
      "token_count": 450,
      "content_preview": "Quy định này áp dụng cho...",
      "has_embedding": true
    }
  ]
}

Response 404: { "detail": "Document version not found" }
```

### 2. GET /api/v1/admin/vectors/{document_version_id}
Xem vectors trong Qdrant của một document version.

```json
Response 200:
{
  "document_version_id": 1,
  "collection": "chunks",
  "total_vectors": 10,
  "vectors": [
    {
      "point_id": "uuid-string",
      "chunk_key": "qd-2024-001-c1",
      "score": null,
      "payload": {
        "document_id": 1,
        "document_version_id": 1,
        "title": "Quy định học vụ",
        "chunk_type": "child"
      }
    }
  ]
}

Response 404: { "detail": "Document version not found" }
Response 503: { "detail": "Qdrant unavailable" }
```

### 3. GET /api/v1/admin/search-test
Test search với query string (không cần LLM).

```json
Request Query Params:
?q=quy trình nghỉ học&top_k=5&department_id=1

Response 200:
{
  "query": "quy trình nghỉ học",
  "embedding_time_ms": 120,
  "search_time_ms": 45,
  "results": [
    {
      "chunk_key": "qd-2024-001-c3",
      "document_version_id": 1,
      "title": "Quy định nghỉ học tạm thời",
      "score": 0.892,
      "content_preview": "Sinh viên có thể xin nghỉ..."
    }
  ]
}
```

---

## Checklist

### Backend - Schemas

- [ ] **Tạo file** `backend/app/schemas/admin_debug.py`
```python
from __future__ import annotations
from app.schemas.base import StrictSchema


class ChunkDebugItem(StrictSchema):
    id: int
    chunk_key: str
    chunk_type: str
    parent_chunk_key: str | None
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    token_count: int | None
    content_preview: str
    has_embedding: bool


class ChunksDebugResponse(StrictSchema):
    document_version_id: int
    total_chunks: int
    parent_chunks: int
    child_chunks: int
    chunks: list[ChunkDebugItem]


class VectorDebugItem(StrictSchema):
    point_id: str
    chunk_key: str
    score: float | None
    payload: dict


class VectorsDebugResponse(StrictSchema):
    document_version_id: int
    collection: str
    total_vectors: int
    vectors: list[VectorDebugItem]


class SearchTestResult(StrictSchema):
    chunk_key: str
    document_version_id: int
    title: str
    score: float
    content_preview: str


class SearchTestResponse(StrictSchema):
    query: str
    embedding_time_ms: int
    search_time_ms: int
    results: list[SearchTestResult]
```

### Backend - Service

- [ ] **Tạo file** `backend/app/admin/debug_service.py`
```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.databases.models.chunks import DocumentChunk
from app.databases.models.documents import DocumentVersion
from app.vectorstore.qdrant_client import get_qdrant_client
from app.embedding.embedder import get_embeddings


async def get_chunks_debug(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Get all chunks for a document version."""
    
    # Verify document exists
    version = await session.get(DocumentVersion, document_version_id)
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")
    
    # Get chunks
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == document_version_id)
        .order_by(DocumentChunk.id)
    )
    chunks = result.scalars().all()
    
    parent_count = sum(1 for c in chunks if c.chunk_type == "parent")
    child_count = sum(1 for c in chunks if c.chunk_type == "child")
    
    return {
        "document_version_id": document_version_id,
        "total_chunks": len(chunks),
        "parent_chunks": parent_count,
        "child_chunks": child_count,
        "chunks": [
            {
                "id": c.id,
                "chunk_key": c.chunk_key,
                "chunk_type": c.chunk_type,
                "parent_chunk_key": c.parent_chunk_key,
                "heading_path": c.heading_path or [],
                "page_start": c.page_start,
                "page_end": c.page_end,
                "token_count": c.token_count,
                "content_preview": (c.content[:150] + "...") if c.content and len(c.content) > 150 else c.content,
                "has_embedding": c.embedding is not None,
            }
            for c in chunks
        ],
    }


async def get_vectors_debug(
    document_version_id: int,
) -> dict:
    """Get vectors from Qdrant for a document version."""
    
    client = get_qdrant_client()
    
    # Scroll through all points with matching document_version_id
    points, _ = client.scroll(
        collection_name="chunks",
        scroll_filter={
            "must": [
                {"key": "document_version_id", "match": {"value": document_version_id}}
            ]
        },
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    
    return {
        "document_version_id": document_version_id,
        "collection": "chunks",
        "total_vectors": len(points),
        "vectors": [
            {
                "point_id": str(p.id),
                "chunk_key": p.payload.get("chunk_key", ""),
                "score": None,
                "payload": p.payload,
            }
            for p in points
        ],
    }


async def search_test(
    query: str,
    top_k: int = 5,
    department_id: int | None = None,
) -> dict:
    """Test vector search without LLM generation."""
    
    # Embed query
    embed_start = time.perf_counter()
    embeddings = await get_embeddings([query])
    embed_time = int((time.perf_counter() - embed_start) * 1000)
    
    # Search Qdrant
    client = get_qdrant_client()
    
    search_filter = {
        "must": [
            {"key": "rag_status", "match": {"value": "published"}}
        ]
    }
    
    if department_id:
        search_filter["must"].append(
            {"key": "department_id", "match": {"value": department_id}}
        )
    
    search_start = time.perf_counter()
    results = client.search(
        collection_name="chunks",
        query_vector=embeddings[0],
        query_filter=search_filter,
        limit=top_k,
        with_payload=True,
    )
    search_time = int((time.perf_counter() - search_start) * 1000)
    
    return {
        "query": query,
        "embedding_time_ms": embed_time,
        "search_time_ms": search_time,
        "results": [
            {
                "chunk_key": r.payload.get("chunk_key", ""),
                "document_version_id": r.payload.get("document_version_id"),
                "title": r.payload.get("title", ""),
                "score": round(r.score, 4),
                "content_preview": r.payload.get("content", "")[:200],
            }
            for r in results
        ],
    }
```

### Backend - Endpoints

- [ ] **Thêm endpoints** trong `backend/app/api/admin_ingestion.py` hoặc tạo file mới
```python
from app.admin.debug_service import (
    get_chunks_debug,
    get_vectors_debug,
    search_test,
)
from app.schemas.admin_debug import (
    ChunksDebugResponse,
    VectorsDebugResponse,
    SearchTestResponse,
)


@router.get(
    "/chunks/{document_version_id}",
    response_model=ChunksDebugResponse,
)
async def debug_chunks(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await get_chunks_debug(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/vectors/{document_version_id}",
    response_model=VectorsDebugResponse,
)
async def debug_vectors(
    document_version_id: int,
):
    try:
        return await get_vectors_debug(document_version_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Qdrant unavailable") from exc


@router.get(
    "/search-test",
    response_model=SearchTestResponse,
)
async def test_search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    department_id: int | None = Query(default=None),
):
    try:
        return await search_test(
            query=q,
            top_k=top_k,
            department_id=department_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
```

### Frontend (Optional)

- [ ] **Thêm debug panel** cho admin UI
```javascript
// admin-frontend/src/api/client.js
getChunksDebug(versionId) {
  return request(`/api/v1/admin/chunks/${versionId}`)
},

getVectorsDebug(versionId) {
  return request(`/api/v1/admin/vectors/${versionId}`)
},

searchTest(query, topK = 5, departmentId = null) {
  const params = new URLSearchParams({ q: query, top_k: topK })
  if (departmentId) params.append('department_id', departmentId)
  return request(`/api/v1/admin/search-test?${params}`)
},
```

---

## Test

```bash
# Get chunks for document version 1
curl http://localhost:8000/api/v1/admin/chunks/1

# Get vectors from Qdrant
curl http://localhost:8000/api/v1/admin/vectors/1

# Test search
curl "http://localhost:8000/api/v1/admin/search-test?q=quy%20trinh%20nghi%20hoc&top_k=5"

# Test search with filter
curl "http://localhost:8000/api/v1/admin/search-test?q=hoc%20bong&department_id=1"
```

---

## Security Notes

⚠️ **Các APIs này chỉ dành cho admin** - cần thêm authentication/authorization trong production:

```python
from app.auth.dependencies import require_admin

@router.get("/chunks/{document_version_id}")
async def debug_chunks(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin),  # Auth check
):
    ...
```

---

## Definition of Done

- [ ] GET /admin/chunks/{id} trả về danh sách chunks từ PostgreSQL
- [ ] GET /admin/vectors/{id} trả về vectors từ Qdrant
- [ ] GET /admin/search-test thực hiện vector search và trả về kết quả với timing
- [ ] Xử lý errors (404, 503) đúng cách
- [ ] Response times hợp lý (< 500ms cho chunks, < 1s cho vectors)
