# 11. Implementation Plan

## MVP sequence

1. Finalize 9-table schema and migrations.
2. Receive canonical Markdown (pre-OCR'd and reviewed externally).
3. Validate metadata against `document_versions` fields.
4. Implement parent-child chunking with `langchain-text-splitters`.
5. Persist chunks with `parent_chunk_id` into `document_chunks`.
6. Embed child chunks with BGE-M3.
7. Upsert Qdrant points with correct payload.
8. Add PostgreSQL sparse search (FTS/BM25).
9. Add RRF fusion.
10. Implement `/api/v1/rag/answer`.
11. Build minimal Flutter chat UI.

## Done criteria

- `/api/v1/rag/answer` returns grounded answer and citations.
- Student retrieval uses `review_status = approved AND rag_status = published` only.
- Related assets come from `document_assets` joined to `assets`.
- `document_chunks` uses `chunk_type` (`parent`/`child`) and `parent_chunk_id`.
- `ingestion_jobs` uses `current_step`, not `current_stage`.
- No active code references removed tables: `document_version_status`, `document_version_relationships`, `collection_status`.

## Backend structure

Use FastAPI with this package boundary:

| Package | Responsibility |
|---|---|
| `app/api` | Versioned routes and endpoint definitions |
| `app/schemas` | Pydantic request/response DTOs |
| `app/config` | Settings, service URLs, model names, DB/Qdrant config |
| `app/core` | Exceptions, dependency injection, security helpers, constants, logging |
| `app/databases` | PostgreSQL models, repositories, migrations |
| `app/ingestion` | Canonical Markdown intake, metadata validation, chunking, indexing jobs |
| `app/embedding` | BGE-M3 loading, embedding, vector normalization |
| `app/vectorstore` | Qdrant client, collections, upsert, search |
| `app/retrieval` | Dense retrieval, sparse retrieval, RRF, filters, parent expansion |
| `app/llm` | LLM client, prompts, answer generation, citation validation |

Route files must validate input, call service layer, return typed schemas, and translate known exceptions.
Do not put business rules directly in route files.

## Coding rules

- Add migrations when schema changes.
- Add tests for status validation, publish rules, retrieval filters, and citation validation.
- Keep API DTOs separate from Flutter UI widgets.
- Keep security, publish, and validity rules in backend.
- Do not hard-code official procedure content in frontend.
- Do not add removed fields or tables: `priority`, `chunking_strategy`, `collection_status`, `document_version_status`, `version_status_history`.
- YAML/Pydantic/RAG payloads use stable keys such as `document_key`, `version_key`, `asset_key`, `chunk_key`, `parent_chunk_key`.
- Database models use IDs/FKs such as `document_id`, `document_version_id`, `asset_id`, `department_id`, `document_type_id`, `parent_chunk_id`.
