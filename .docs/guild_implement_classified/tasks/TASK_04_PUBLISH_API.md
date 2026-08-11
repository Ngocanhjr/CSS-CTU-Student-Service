# Task 04: Publish/Unpublish API

## Mục tiêu
Cho phép publish document để đưa vào RAG chatbot và unpublish để tạm ẩn khỏi kết quả tìm kiếm.

## Endpoints cần implement

### 1. POST /api/v1/versions/{document_version_id}/publish
```json
Response 200:
{
  "document_version_id": 1,
  "rag_status": "published",
  "published_at": "2024-01-15T10:30:00Z"
}

Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Document must be indexed before publishing" }
```

### 2. POST /api/v1/versions/{document_version_id}/unpublish
```json
Response 200:
{
  "document_version_id": 1,
  "rag_status": "indexed",
  "unpublished_at": "2024-01-15T10:30:00Z"
}

Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Document is not published" }
```

---

## Business Rules

### Publish
1. **Chỉ publish** nếu `rag_status` = `indexed`
2. Update `rag_status` = `published`
3. Vectors trong Qdrant đã sẵn sàng, chỉ cần đánh dấu document là active

### Unpublish
1. **Chỉ unpublish** nếu `rag_status` = `published`
2. Update `rag_status` = `indexed`
3. **Không xóa vectors** - chỉ đánh dấu không active để có thể re-publish nhanh

---

## Checklist

### Backend - Schema

- [ ] **Thêm schemas** trong `backend/app/schemas/documents_management.py`
```python
from datetime import datetime

class PublishResponse(StrictSchema):
    document_version_id: int
    rag_status: str
    published_at: datetime

class UnpublishResponse(StrictSchema):
    document_version_id: int
    rag_status: str
    unpublished_at: datetime
```

### Backend - Service

- [ ] **Thêm functions** trong `backend/app/documents/service.py`
```python
from datetime import datetime, timezone

async def publish_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Mark document version as published."""
    
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")
    
    if version.rag_status != "indexed":
        raise ValueError(
            f"Document must be indexed before publishing (current: {version.rag_status})"
        )
    
    now = datetime.now(timezone.utc)
    version.rag_status = "published"
    version.published_at = now
    await session.commit()
    
    return {
        "document_version_id": document_version_id,
        "rag_status": "published",
        "published_at": now,
    }


async def unpublish_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Mark document version as unpublished (but keep vectors)."""
    
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")
    
    if version.rag_status != "published":
        raise ValueError(
            f"Document is not published (current: {version.rag_status})"
        )
    
    now = datetime.now(timezone.utc)
    version.rag_status = "indexed"
    version.unpublished_at = now
    await session.commit()
    
    return {
        "document_version_id": document_version_id,
        "rag_status": "indexed",
        "unpublished_at": now,
    }
```

### Backend - Endpoints

- [ ] **Thêm endpoints** trong `backend/app/api/documents.py`
```python
from app.schemas.documents_management import PublishResponse, UnpublishResponse

@router.post(
    "/{document_version_id}/publish",
    response_model=PublishResponse,
)
async def publish_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> PublishResponse:
    try:
        return await publish_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{document_version_id}/unpublish",
    response_model=UnpublishResponse,
)
async def unpublish_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> UnpublishResponse:
    try:
        return await unpublish_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

### Database Migration (nếu cần)

- [ ] **Thêm columns** nếu chưa có
```python
# Kiểm tra document_versions table có columns:
# - published_at: TIMESTAMP
# - unpublished_at: TIMESTAMP
# Nếu chưa có, tạo migration mới
```

### Frontend

- [ ] **Thêm API functions** trong `admin-frontend/src/api/client.js`
```javascript
publishDocument(versionId) {
  return request(`/api/v1/versions/${versionId}/publish`, { method: 'POST' })
},

unpublishDocument(versionId) {
  return request(`/api/v1/versions/${versionId}/unpublish`, { method: 'POST' })
},
```

- [ ] **Thêm UI controls** trong `DocumentEditPage.jsx`
```jsx
async function handlePublish() {
  setBusy(true)
  try {
    await api.publishDocument(documentId)
    const updated = await api.getDocument(documentId)
    setDoc(updated)
    setResult({ updated: true, message: 'Đã publish thành công' })
  } catch (err) {
    setError(err.message)
  } finally {
    setBusy(false)
  }
}

async function handleUnpublish() {
  if (!confirm('Unpublish sẽ ẩn tài liệu khỏi chatbot. Tiếp tục?')) return
  setBusy(true)
  try {
    await api.unpublishDocument(documentId)
    const updated = await api.getDocument(documentId)
    setDoc(updated)
    setResult({ updated: true, message: 'Đã unpublish' })
  } catch (err) {
    setError(err.message)
  } finally {
    setBusy(false)
  }
}

// Conditional buttons
{doc.rag_status === 'indexed' && (
  <button className="btn" onClick={handlePublish} disabled={busy}>
    Publish
  </button>
)}

{doc.rag_status === 'published' && (
  <button className="btn ghost warn" onClick={handleUnpublish} disabled={busy}>
    Unpublish
  </button>
)}
```

---

## RAG Integration

Khi query chatbot, cần filter chỉ lấy documents có `rag_status = published`:

```python
# Trong retriever/search logic
filter = Filter(
    must=[
        FieldCondition(
            key="rag_status",
            match=MatchValue(value="published")
        )
    ]
)
```

Hoặc store `is_published: bool` trong Qdrant payload để filter nhanh hơn.

---

## Test

```bash
# Test publish (assuming version 1 has rag_status=indexed)
curl -X POST http://localhost:8000/api/v1/versions/1/publish
# Expected: 200 with rag_status=published

# Test publish not-indexed (should fail)
curl -X POST http://localhost:8000/api/v1/versions/2/publish
# Expected: 409 Conflict

# Test unpublish
curl -X POST http://localhost:8000/api/v1/versions/1/unpublish
# Expected: 200 with rag_status=indexed

# Test unpublish not-published (should fail)
curl -X POST http://localhost:8000/api/v1/versions/1/unpublish
# Expected: 409 Conflict
```

---

## Definition of Done

- [ ] Endpoint publish chuyển `indexed` → `published`
- [ ] Endpoint unpublish chuyển `published` → `indexed`
- [ ] Trả về 409 nếu status không hợp lệ
- [ ] Timestamps được lưu vào database
- [ ] Frontend có nút Publish/Unpublish tùy theo status
- [ ] RAG retriever filter chỉ documents published
