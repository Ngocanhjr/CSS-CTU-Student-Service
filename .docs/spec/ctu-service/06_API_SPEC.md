# 06. API Spec

Use `/api/v1` prefix for all public API routes.

## Health

```http
GET /api/v1/health/database
```

Returns `{"status":"available"}` when PostgreSQL answers `SELECT 1`, otherwise
`{"status":"unavailable"}`. This endpoint is informational and always returns HTTP 200.

## RAG answer

```http
POST /api/v1/rag/answer
```

Request:

```json
{
  "query": "Em muốn xin bảng điểm thì cần gì?",
  "user_role": "student",
  "prefer_current": true
}
```

Response:

```json
{
  "answer": "...",
  "citations": [],
  "related_assets": [],
  "trace_id": "..."
}
```

## Ingestion jobs

```http
POST /api/v1/ingestion/jobs
GET /api/v1/ingestion/jobs/{id}
```

Job status uses `current_step`.

## Admin chunk review

```http
POST /api/v1/admin/document-versions/{id}/chunk-preview
POST /api/v1/admin/document-versions/{id}/chunks/approve
POST /api/v1/admin/document-versions/{id}/index
```

Preview is read-only. Approve replaces the version's Parent/Child rows in
`document_chunks` and persists `ingestion_jobs.current_step = chunks_approved`.
Index is rejected unless that durable approval marker and the approved rows still
match the current canonical Markdown.

## Documents

```http
GET /api/v1/documents
GET /api/v1/documents/{id}
GET /api/v1/document-versions/{id}
```

Status fields are on `document_versions`.

Do not append `version_status_history`; that table is not in the current schema.
