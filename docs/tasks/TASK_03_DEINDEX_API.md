# Task 03: Deindex API

## Mục tiêu
Gỡ index document - xóa chunks từ PostgreSQL và vectors từ Qdrant để cho phép sửa lại document.

## Endpoint cần implement

### POST /api/v1/versions/{document_version_id}/deindex
```json
Response 200:
{
  "document_version_id": 1,
  "chunks_deleted": 15,
  "vectors_deleted": 12,
  "new_rag_status": "not_indexed"
}

Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Document not indexed" }
```

---

## Business Rules

1. **Chỉ deindex** nếu `rag_status` in [`chunked`, `embedded`, `indexed`, `published`]
2. **Từ chối** nếu `rag_status` = `not_indexed` → trả về 409
3. **Cascade delete:**
   - Xóa tất cả records trong `document_chunks` table
   - Xóa vectors trong Qdrant collection
4. **Update status** `rag_status` = `not_indexed`

---

## Checklist

### Backend - Qdrant Repository

- [ ] **Thêm function** trong `backend/app/vectorstore/repository.py`
```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

async def delete_vectors_by_version(
    client,
    collection_name: str,
    document_version_id: int,
) -> int:
    """Delete all vectors for a document version. Returns count deleted."""
    
    # First, count existing vectors
    count_result = client.count(
        collection_name=collection_name,
        count_filter=Filter(
            must=[
                FieldCondition(
                    key="document_version_id",
                    match=MatchValue(value=document_version_id)
                )
            ]
        )
    )
    count = count_result.count
    
    # Delete vectors
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_version_id",
                    match=MatchValue(value=document_version_id)
                )
            ]
        )
    )
    
    return count
```

### Backend - Chunks Repository

- [ ] **Thêm function** trong `backend/app/databases/repositories/chunks.py`
```python
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.chunks import DocumentChunk

async def delete_chunks_by_version(
    session: AsyncSession,
    document_version_id: int,
) -> int:
    """Delete all chunks for a document version. Returns count deleted."""
    
    # Count before delete
    count_result = await session.execute(
        select(func.count()).where(
            DocumentChunk.document_version_id == document_version_id
        )
    )
    count = count_result.scalar() or 0
    
    # Delete chunks
    await session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_version_id == document_version_id
        )
    )
    
    return count
```

### Backend - Service

- [ ] **Thêm function** trong `backend/app/documents/service.py`
```python
from app.databases.repositories.chunks import delete_chunks_by_version
from app.vectorstore.repository import delete_vectors_by_version
from app.vectorstore.qdrant_client import get_qdrant_client

INDEXED_STATUSES = {"chunked", "embedded", "indexed", "published"}

async def deindex_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Remove chunks and vectors for a document version."""
    
    # 1. Fetch version
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")
    
    # 2. Check rag_status
    if version.rag_status not in INDEXED_STATUSES:
        raise ValueError(
            f"Document not indexed (rag_status={version.rag_status})"
        )
    
    # 3. Delete chunks from PostgreSQL
    chunks_deleted = await delete_chunks_by_version(session, document_version_id)
    
    # 4. Delete vectors from Qdrant
    client = get_qdrant_client()
    vectors_deleted = await delete_vectors_by_version(
        client,
        collection_name="chunks",  # or from config
        document_version_id=document_version_id,
    )
    
    # 5. Update rag_status
    version.rag_status = "not_indexed"
    await session.commit()
    
    return {
        "document_version_id": document_version_id,
        "chunks_deleted": chunks_deleted,
        "vectors_deleted": vectors_deleted,
        "new_rag_status": "not_indexed",
    }
```

### Backend - Endpoint

- [ ] **Thêm schema** trong `backend/app/schemas/documents_management.py`
```python
class DeindexResponse(StrictSchema):
    document_version_id: int
    chunks_deleted: int
    vectors_deleted: int
    new_rag_status: str
```

- [ ] **Thêm endpoint** trong `backend/app/api/documents.py`
```python
from app.schemas.documents_management import DeindexResponse

@router.post(
    "/{document_version_id}/deindex",
    response_model=DeindexResponse,
)
async def deindex_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> DeindexResponse:
    try:
        return await deindex_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

### Frontend

- [ ] **Thêm API function** trong `admin-frontend/src/api/client.js`
```javascript
deindexDocument(versionId) {
  return request(`/api/v1/versions/${versionId}/deindex`, { method: 'POST' })
},
```

- [ ] **Thêm nút deindex** trong `DocumentEditPage.jsx`
```jsx
async function handleDeindex() {
  if (!confirm('Deindex sẽ xóa tất cả chunks và vectors. Tiếp tục?')) return
  setBusy(true)
  try {
    const result = await api.deindexDocument(documentId)
    alert(`Đã xóa ${result.chunks_deleted} chunks và ${result.vectors_deleted} vectors`)
    // Refresh document data
    const updated = await api.getDocument(documentId)
    setDoc(updated)
  } catch (err) {
    setError(err.message)
  } finally {
    setBusy(false)
  }
}

// Show deindex button only for indexed documents
{['chunked', 'embedded', 'indexed', 'published'].includes(doc.rag_status) && (
  <button className="btn ghost warn" onClick={handleDeindex} disabled={busy}>
    Deindex
  </button>
)}
```

---

## Test

```bash
# Test deindex success (assuming version 1 is indexed)
curl -X POST http://localhost:8000/api/v1/versions/1/deindex
# Expected: 200 with counts

# Verify chunks deleted
curl http://localhost:8000/api/v1/versions/1
# Expected: rag_status = "not_indexed"

# Test deindex not-indexed document (should fail)
curl -X POST http://localhost:8000/api/v1/versions/1/deindex
# Expected: 409 Conflict

# Test deindex non-existent
curl -X POST http://localhost:8000/api/v1/versions/9999/deindex
# Expected: 404 Not Found
```

---

## Qdrant Collection Info

Kiểm tra collection name và payload structure trong:
- `backend/app/vectorstore/qdrant_client.py`
- `backend/app/vectorstore/models.py`

Expected payload fields:
- `document_version_id`: int (filter key)
- `chunk_key`: str
- `document_id`: int
- Các metadata khác

---

## Definition of Done

- [ ] Endpoint POST trả về số chunks/vectors đã xóa
- [ ] Chunks bị xóa khỏi PostgreSQL `document_chunks` table
- [ ] Vectors bị xóa khỏi Qdrant collection
- [ ] `rag_status` được update thành `not_indexed`
- [ ] Trả về 409 nếu document chưa được index
- [ ] Frontend có nút deindex với confirmation
- [ ] Sau deindex, có thể edit và re-index document
