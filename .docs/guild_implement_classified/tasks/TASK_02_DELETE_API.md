# Task 02: Document Delete API

## Mục tiêu
Cho phép xóa document version chưa được index.

## Endpoint cần implement

### DELETE /api/v1/versions/{document_version_id}
```
Response 204: No Content (xóa thành công)
Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Cannot delete indexed document. Deindex first." }
```

---

## Business Rules

1. **Chỉ cho phép xóa** nếu `rag_status` in [`not_indexed`, `failed`]
2. **Từ chối xóa** nếu đã indexed → trả về 409
3. **Cascade delete:**
   - Xóa các `ingestion_jobs` liên quan
   - Xóa file canonical markdown trên filesystem
   - Xóa record `document_version`
4. **Không xóa document** nếu còn version khác

---

## Checklist

### Backend

- [ ] **Thêm function** trong `backend/app/documents/service.py`
```python
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import DocumentVersion
from app.databases.models.ingestion import IngestionJob

async def delete_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> None:
    """Delete a document version if not indexed."""
    
    # 1. Fetch version
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    version = result.scalar_one_or_none()
    
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")
    
    # 2. Check rag_status
    if version.rag_status not in ("not_indexed", "failed"):
        raise ValueError(
            f"Cannot delete indexed document (rag_status={version.rag_status}). "
            "Deindex first."
        )
    
    # 3. Delete related ingestion jobs
    await session.execute(
        delete(IngestionJob).where(
            IngestionJob.document_version_id == document_version_id
        )
    )
    
    # 4. Delete canonical markdown file
    if version.canonical_markdown_path:
        md_path = Path(version.canonical_markdown_path)
        if md_path.exists():
            md_path.unlink()
    
    # 5. Delete version record
    await session.delete(version)
    await session.commit()
```

- [ ] **Thêm endpoint** trong `backend/app/api/documents.py`
```python
from fastapi import status

@router.delete(
    "/{document_version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await delete_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

### Frontend

- [ ] **Thêm API function** trong `admin-frontend/src/api/client.js`
```javascript
deleteDocument(versionId) {
  return request(`/api/v1/versions/${versionId}`, { method: 'DELETE' })
},
```

- [ ] **Thêm nút xóa** trong `DocumentEditPage.jsx` hoặc `DocumentsListPage.jsx`
```jsx
async function handleDelete(versionId) {
  if (!confirm('Bạn có chắc muốn xóa tài liệu này?')) return
  try {
    await api.deleteDocument(versionId)
    // Refresh list or navigate back
  } catch (err) {
    setError(err.message)
  }
}

// Only show delete button if not indexed
{doc.rag_status === 'not_indexed' && (
  <button className="btn ghost danger" onClick={() => handleDelete(doc.id)}>
    Xóa
  </button>
)}
```

---

## Test

```bash
# Test delete success (assuming version 1 has rag_status=not_indexed)
curl -X DELETE http://localhost:8000/api/v1/versions/1 -v
# Expected: 204 No Content

# Test delete indexed document (should fail)
curl -X DELETE http://localhost:8000/api/v1/versions/2 -v
# Expected: 409 Conflict

# Test delete non-existent
curl -X DELETE http://localhost:8000/api/v1/versions/9999 -v
# Expected: 404 Not Found
```

---

## Edge Cases

1. **File không tồn tại**: Nếu `canonical_markdown_path` trỏ đến file đã bị xóa thủ công, không raise error, chỉ log warning
2. **Concurrent delete**: Sử dụng database transaction để tránh race condition
3. **Source file**: Không xóa `source_path` vì có thể dùng để re-upload

---

## Definition of Done

- [ ] Endpoint DELETE trả về 204 khi xóa thành công
- [ ] Trả về 409 nếu document đã indexed
- [ ] Trả về 404 nếu không tìm thấy
- [ ] File markdown bị xóa khỏi filesystem
- [ ] Ingestion jobs liên quan bị xóa
- [ ] Frontend có nút xóa với confirmation dialog
