# Hướng dẫn Implement các API còn thiếu

## Tổng quan

Tài liệu này chia nhỏ các API cần implement thành các task độc lập, mỗi task có thể giao cho 1 agent thực hiện.

---

## Agent 1: Reference Data APIs

### Mục tiêu
Tạo API lấy dữ liệu tham chiếu (document types, departments) từ database thay vì hardcode ở frontend.

### Files cần tạo/sửa
- `backend/app/api/reference.py` (tạo mới)
- `backend/app/main.py` (đăng ký router)
- `admin-frontend/src/api/client.js` (thêm functions)
- `admin-frontend/src/api/referenceData.js` (chuyển sang gọi API)

### API Specifications

#### 1.1 GET /api/v1/reference/document-types
```
Response 200:
[
  { "id": 1, "code": "noi_quy", "name": "Nội quy", "is_active": true },
  { "id": 2, "code": "quy_trinh", "name": "Quy trình", "is_active": true }
]
```

#### 1.2 GET /api/v1/reference/departments
```
Response 200:
[
  { "id": 1, "code": "PDT", "name": "Phòng Đào tạo", "is_active": true },
  { "id": 2, "code": "PCTSV", "name": "Phòng Công tác Sinh viên", "is_active": true }
]
```

### Schema cần tạo
```python
# backend/app/schemas/reference.py
from app.schemas.base import StrictSchema

class DocumentTypeResponse(StrictSchema):
    id: int
    code: str
    name: str
    is_active: bool

class DepartmentResponse(StrictSchema):
    id: int
    code: str
    name: str
    is_active: bool
```

### Implementation Steps
1. Tạo schema `backend/app/schemas/reference.py`
2. Tạo router `backend/app/api/reference.py` với 2 endpoints
3. Query từ tables `document_types` và `departments` (đã có trong DB)
4. Đăng ký router trong `main.py`
5. Update frontend client và components

### Test
```bash
curl http://localhost:8000/api/v1/reference/document-types
curl http://localhost:8000/api/v1/reference/departments
```

---

## Agent 2: Document Delete API

### Mục tiêu
Cho phép xóa document version chưa được index.

### Files cần tạo/sửa
- `backend/app/api/documents.py` (thêm endpoint)
- `backend/app/documents/service.py` (thêm function)
- `admin-frontend/src/api/client.js` (thêm function)

### API Specification

#### 2.1 DELETE /api/v1/versions/{document_version_id}
```
Response 204: No Content (xóa thành công)
Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Cannot delete indexed document. Deindex first." }
```

### Business Rules
- Chỉ cho phép xóa nếu `rag_status` = `not_indexed` hoặc `failed`
- Nếu đã indexed → trả về 409, yêu cầu deindex trước
- Xóa cascade: document_version → ingestion_jobs (nếu có)
- Xóa file canonical markdown trên filesystem

### Implementation Steps
1. Thêm function `delete_document_version()` trong `service.py`
2. Kiểm tra `rag_status` trước khi xóa
3. Xóa file markdown từ `canonical_markdown_path`
4. Xóa record trong database
5. Thêm endpoint DELETE trong `documents.py`
6. Update frontend client

### Test
```bash
curl -X DELETE http://localhost:8000/api/v1/versions/1
```

---

## Agent 3: Deindex API

### Mục tiêu
Gỡ index document (xóa chunks từ PostgreSQL và vectors từ Qdrant).

### Files cần tạo/sửa
- `backend/app/api/documents.py` (thêm endpoint)
- `backend/app/documents/service.py` (thêm function)
- `backend/app/vectorstore/repository.py` (thêm delete function)
- `admin-frontend/src/api/client.js` (thêm function)

### API Specification

#### 3.1 POST /api/v1/versions/{document_version_id}/deindex
```
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

### Business Rules
- Chỉ deindex nếu `rag_status` in [`chunked`, `embedded`, `indexed`, `published`]
- Xóa tất cả records trong `document_chunks` theo `document_version_id`
- Xóa vectors trong Qdrant theo filter `document_version_id`
- Update `rag_status` = `not_indexed`

### Implementation Steps
1. Thêm `delete_vectors_by_version()` trong `vectorstore/repository.py`
2. Thêm `delete_chunks_by_version()` trong `databases/repositories/chunks.py`
3. Tạo function `deindex_document_version()` trong `documents/service.py`
4. Thêm endpoint POST trong `documents.py`
5. Update frontend

### Qdrant Delete Query
```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

client.delete(
    collection_name="chunks",
    points_selector=Filter(
        must=[
            FieldCondition(
                key="document_version_id",
                match=MatchValue(value=document_version_id)
            )
        ]
    )
)
```

### Test
```bash
curl -X POST http://localhost:8000/api/v1/versions/1/deindex
```

---

## Agent 4: Publish/Unpublish APIs

### Mục tiêu
Quản lý trạng thái publish của document (cho phép/không cho phép xuất hiện trong kết quả search).

### Files cần tạo/sửa
- `backend/app/api/documents.py` (thêm 2 endpoints)
- `backend/app/documents/service.py` (thêm functions)
- `admin-frontend/src/api/client.js` (thêm functions)

### API Specifications

#### 4.1 POST /api/v1/versions/{document_version_id}/publish
```
Response 200:
{
  "document_version_id": 1,
  "rag_status": "published",
  "published_at": "2024-01-15T10:30:00Z"
}

Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Document must be indexed before publishing" }
```

#### 4.2 POST /api/v1/versions/{document_version_id}/unpublish
```
Response 200:
{
  "document_version_id": 1,
  "rag_status": "indexed",
  "unpublished_at": "2024-01-15T10:30:00Z"
}

Response 404: { "detail": "Document version not found" }
Response 409: { "detail": "Document not published" }
```

### Business Rules
- Publish: chỉ khi `rag_status` = `indexed`
- Unpublish: chỉ khi `rag_status` = `published`
- Update Qdrant payload `is_published` = true/false (optional, hoặc filter khi search)

### Implementation Steps
1. Thêm functions `publish_document_version()` và `unpublish_document_version()` trong `service.py`
2. Update `rag_status` trong database
3. (Optional) Update payload trong Qdrant
4. Thêm 2 endpoints trong `documents.py`
5. Update frontend

### Test
```bash
curl -X POST http://localhost:8000/api/v1/versions/1/publish
curl -X POST http://localhost:8000/api/v1/versions/1/unpublish
```

---

## Agent 5: Chat/RAG API

### Mục tiêu
API chính của chatbot - nhận câu hỏi, tìm kiếm context từ Qdrant, sinh câu trả lời.

### Files cần tạo/sửa
- `backend/app/api/chat.py` (tạo mới)
- `backend/app/schemas/chat.py` (tạo mới)
- `backend/app/main.py` (đăng ký router)

### API Specification

#### 5.1 POST /api/v1/chat
```
Request:
{
  "message": "Thủ tục xin nghỉ học tạm thời như thế nào?",
  "conversation_id": "uuid-optional",
  "filters": {
    "department_id": 1,
    "document_type_id": 2
  }
}

Response 200:
{
  "answer": "Để xin nghỉ học tạm thời, sinh viên cần...",
  "sources": [
    {
      "document_id": 1,
      "document_version_id": 3,
      "title": "Quy định nghỉ học tạm thời",
      "chunk_key": "QD-2024-001_v1_c3",
      "content_preview": "Sinh viên có nhu cầu nghỉ học...",
      "score": 0.89,
      "page": 2
    }
  ],
  "conversation_id": "uuid"
}

Response 400: { "detail": "Message cannot be empty" }
Response 503: { "detail": "LLM service unavailable" }
```

### Schema
```python
# backend/app/schemas/chat.py
from app.schemas.base import StrictSchema
from pydantic import Field

class ChatRequest(StrictSchema):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    filters: dict | None = None

class SourceChunk(StrictSchema):
    document_id: int
    document_version_id: int
    title: str
    chunk_key: str
    content_preview: str
    score: float
    page: int | None = None

class ChatResponse(StrictSchema):
    answer: str
    sources: list[SourceChunk]
    conversation_id: str
```

### Implementation Flow
1. Nhận message từ user
2. Tạo embedding cho message (dùng `embedder.py`)
3. Search Qdrant với filter `is_published=true` (hoặc `rag_status=published`)
4. Lấy top-k chunks làm context
5. Gọi LLM với prompt + context (dùng `rag_chain.py`)
6. Trả về answer + sources

### Implementation Steps
1. Tạo schema `backend/app/schemas/chat.py`
2. Tạo router `backend/app/api/chat.py`
3. Integrate với `retriever.py` để search
4. Integrate với `rag_chain.py` để generate answer
5. Đăng ký router trong `main.py`

### Existing Code to Use
- `backend/app/retrieval/retriever.py` - đã có logic search
- `backend/app/llm/rag_chain.py` - đã có logic RAG
- `backend/app/embedding/embedder.py` - đã có logic embedding

### Test
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Thủ tục xin nghỉ học tạm thời?"}'
```

---

## Agent 6: Admin Chunks API (Optional/Debug)

### Mục tiêu
API debug để xem chi tiết chunks của document.

### Files cần tạo/sửa
- `backend/app/api/admin_ingestion.py` (thêm endpoint)

### API Specification

#### 6.1 GET /api/v1/admin/document-versions/{document_version_id}/chunks
```
Query params:
- chunk_type: parent | child (optional)
- limit: int (default 50)
- offset: int (default 0)

Response 200:
{
  "total": 15,
  "chunks": [
    {
      "id": 1,
      "chunk_key": "QD-2024-001_v1_p1",
      "chunk_type": "parent",
      "content": "...",
      "heading_path": ["Chương 1", "Điều 1"],
      "page_start": 1,
      "page_end": 2,
      "token_count": 350,
      "has_embedding": true
    }
  ]
}
```

### Implementation Steps
1. Query `document_chunks` table với filters
2. Join với embeddings table để check `has_embedding`
3. Trả về paginated results

---

## Thứ tự ưu tiên implement

| Priority | Agent | API | Lý do |
|----------|-------|-----|-------|
| 1 | Agent 5 | Chat API | Core functionality của chatbot |
| 2 | Agent 1 | Reference Data | Loại bỏ hardcode, cần cho filters |
| 3 | Agent 3 | Deindex | Cần để sửa document đã index |
| 4 | Agent 4 | Publish/Unpublish | Control visibility |
| 5 | Agent 2 | Delete | Cleanup documents |
| 6 | Agent 6 | Admin Chunks | Debug only |

---

## Conventions chung

### Error Handling
```python
from fastapi import HTTPException

# 404 - Not found
raise HTTPException(status_code=404, detail="Document version not found")

# 409 - Conflict (business rule violation)
raise HTTPException(status_code=409, detail="Cannot delete indexed document")

# 422 - Validation error
raise HTTPException(status_code=422, detail="Invalid input")
```

### Response Models
- Luôn dùng Pydantic models với `response_model=`
- Kế thừa từ `StrictSchema` để reject extra fields

### Database Session
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.databases.session import get_session

@router.get("/endpoint")
async def endpoint(session: AsyncSession = Depends(get_session)):
    ...
```

### Testing
- Mỗi API cần có test file tương ứng trong `backend/test/api/`
- Test cả happy path và error cases
