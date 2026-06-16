 06# 06. Đặc Tả API

## API Overview

### Base URL
- **Development:** `http://localhost:8000`
- **Production:** _[TBD]_

### API Versioning
- **Current version:** `/api/v1`

### Authentication
_[JWT token, header: Authorization: Bearer <token>]_

---

## Health Check APIs

### `GET /health`
**Purpose:** _[Health check]_
**Auth:** None
**Response:**
```json
{"status": "ok", "timestamp": "2026-06-10T10:00:00Z"}
```

---

## Auth APIs

### `POST /api/v1/auth/login`
**Purpose:** _[User login]_
**Request:**
```json
{"username": "student01", "password": "***"}
```
**Response:**
```json
{"access_token": "...", "token_type": "bearer", "user": {"id": "...", "role": "student"}}
```

### `POST /api/v1/auth/logout`
**Purpose:** _[Logout]_

---

## Reference Data APIs

### `GET /api/v1/departments`
**Purpose:** _[List departments]_

### `GET /api/v1/document-types`
**Purpose:** _[List document types]_

---

## Document Management APIs (Admin)

### `GET /api/v1/documents`
**Purpose:** _[List documents]_
**Query params:** _[page, limit, department, document_type, status]_

### `POST /api/v1/documents`
**Purpose:** _[Upload new document]_
**Request:** _[multipart/form-data: file + metadata]_

### `GET /api/v1/documents/{id}`
**Purpose:** _[Get document detail]_

### `GET /api/v1/documents/{id}/versions`
**Purpose:** _[List versions of a document]_

### `GET /api/v1/document-versions/{id}`
**Purpose:** _[Get version detail]_

### `PUT /api/v1/document-versions/{id}`
**Purpose:** _[Update version metadata]_

### `POST /api/v1/document-versions/{id}/validate`
**Purpose:** _[Validate metadata]_

### `POST /api/v1/document-versions/{id}/approve`
**Purpose:** _[Approve document]_

### `POST /api/v1/document-versions/{id}/reject`
**Purpose:** _[Reject document]_

### `POST /api/v1/document-versions/{id}/publish`
**Purpose:** _[Publish to RAG]_

### `POST /api/v1/document-versions/{id}/unpublish`
**Purpose:** _[Deactivate from RAG]_

---

## Ingestion APIs (Admin)

### `POST /api/v1/ingestion/jobs`
**Purpose:** _[Create ingestion job]_
**Request:**
```json
{"document_version_id": "..."}
```

### `GET /api/v1/ingestion/jobs`
**Purpose:** _[List ingestion jobs]_

### `GET /api/v1/ingestion/jobs/{id}`
**Purpose:** _[Get job detail + progress]_

### `POST /api/v1/ingestion/jobs/{id}/retry`
**Purpose:** _[Retry failed job]_

---

## RAG Answer APIs (Student)

### `POST /api/v1/rag/answer`
**Purpose:** _[Get answer từ RAG]_

**Request:**
```json
{
  "query": "Em muốn xin cấp bảng điểm thì cần gì?",
  "user_role": "student",
  "domain_filter": ["pdt", "hoc_vu"],
  "strict_latest": false,
  "session_id": "..."
}
```

**Response:**
```json
{
  "answer": "...",
  "citations": [
    {
      "document_id": "...",
      "version_id": "...",
      "title": "...",
      "page_start": 1,
      "page_end": 2,
      "section_title": "...",
      "source_file": "...",
      "quote_snippet": "..."
    }
  ],
  "related_assets": [
    {
      "asset_id": "...",
      "title": "...",
      "file_path": "...",
      "download_url": "..."
    }
  ],
  "confidence": "high",
  "retrieval_count": 3,
  "trace_id": "..."
}
```

---

## Asset APIs

### `GET /api/v1/assets`
**Purpose:** _[List assets]_

### `GET /api/v1/assets/{id}`
**Purpose:** _[Get asset detail]_

### `GET /api/v1/assets/{id}/download`
**Purpose:** _[Download asset file]_

---

## Chat History APIs (Student)

### `GET /api/v1/chat/sessions`
**Purpose:** _[List chat sessions]_

### `GET /api/v1/chat/sessions/{id}/messages`
**Purpose:** _[Get messages in a session]_

### `POST /api/v1/chat/sessions`
**Purpose:** _[Create new session]_

### `DELETE /api/v1/chat/sessions/{id}`
**Purpose:** _[Delete session]_

---

## Error Response Format

### Standard Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid metadata",
    "details": [
      {"field": "effective_date", "issue": "Cannot be in the future"}
    ],
    "trace_id": "..."
  }
}
```

### Error Codes
- `VALIDATION_ERROR` — _[400]_
- `UNAUTHORIZED` — _[401]_
- `FORBIDDEN` — _[403]_
- `NOT_FOUND` — _[404]_
- `CONFLICT` — _[409]_
- `INTERNAL_ERROR` — _[500]_

---

## Pagination Format

### Request
```
GET /api/v1/documents?page=1&limit=20
```

### Response
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

**Status:** Skeleton — Cần điền chi tiết request/response schemas  
**Priority:** P1
