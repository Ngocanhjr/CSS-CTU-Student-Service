# 04. Module Spec

## Backend modules

| Module | Responsibility |
|---|---|
| `app/api` | FastAPI routes |
| `app/ingestion` | Receive canonical Markdown, metadata validation, chunking, indexing job orchestration |
| `app/embedding` | BGE-M3 embeddings |
| `app/vectorstore` | Qdrant |
| `app/retrieval` | Hybrid retrieval and RRF |
| `app/llm` | Prompt, answer, citation validation |
| `app/databases` | PostgreSQL models and repositories |
| `app/schemas` | Pydantic DTOs |

> OCR/LlamaParse chạy bên ngoài backend này. Backend chỉ nhận canonical Markdown
> đã được OCR và review từ trước. Không có module `app/ocr` hay `llamaparse_adapter`.

## Frontend modules

- Chat screen calls `/api/v1/rag/answer`.
- Citation drawer displays source document/version/chunk.
- Admin ingestion screen displays `current_step`.

## Removed/currently not used

- `collection_status`
- `version_status_history`
- `document_version_status` (bảng riêng — status nằm trong `document_versions`)
- `document_version_relationships` (bảng riêng — đã loại khỏi schema)
- `chunk_level` (dùng `chunk_type`)
- `parent_id` (dùng `parent_chunk_id`)
- `current_stage` (dùng `current_step`)
