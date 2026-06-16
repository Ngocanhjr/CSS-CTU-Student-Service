# Architecture Guide

## Target architecture

```text
Student/Admin
→ Flutter Frontend (Mobile/Web)
→ Backend API
→ RAG Service
→ PostgreSQL + Qdrant + Object/File Storage
```

## Pinned implementation decisions

Updated: `2026-06-08`

These choices are fixed for the implementation window from `2026-06-08` to `2026-06-19`.

| Area | Decision |
|---|---|
| OCR tool | `ocr-pvl` |
| OCR implementation | PaddleOCR + VietOCR + LlamaParse through `ocr-pvl` |
| RAG workflow framework | LangChain |
| Chunking framework | LangChain chunking utilities with heading-aware parent-child rules |
| Embedding model | `BAAI/bge-m3` |
| Vector database | Qdrant |
| Code-running target | End-to-end vertical slice running by `2026-06-19` |
| Retrieval optimization | HNSW tuning is future-only, not part of the current MVP |

## Layer responsibilities

| Layer | Responsibility |
|---|---|
| Flutter Frontend | Chat UI, citation drawer, procedure detail/checklist, admin dashboard, document upload/review screens. |
| Backend API | Auth/RBAC, CRUD, document/version/asset workflow, ingestion orchestration, chat orchestration. |
| RAG Service | LangChain-based query normalization, chunk/retrieval orchestration, intent/entity extraction, retrieval, reranking, context building, LLM call, citation validation. |
| PostgreSQL | Source of truth for metadata, versions, status, chunks, assets, relationships, jobs. |
| Qdrant | Vector retrieval index with minimal payload. |
| Storage | Original files, OCR outputs, canonical Markdown, downloadable assets. |
| Worker/Queue | `ocr-pvl` OCR jobs, LangChain chunking jobs, BGE-M3 embedding, Qdrant indexing, reindexing jobs. |


## OCR-PVL boundary

`ocr-pvl` is the only OCR entry point for the current implementation phase. Do not add another OCR tool directly into the backend pipeline unless the project stack decision changes.

`ocr-pvl` internally uses:

| Tool | Used for |
|---|---|
| PaddleOCR | Detecting text/layout regions from PDF/image pages. |
| VietOCR | Vietnamese text recognition. |
| LlamaParse | Table-heavy pages and complex layouts where table structure must be preserved. |

The expected output is Markdown that preserves headings, lists, tables, and page markers such as `<!-- page: 4 -->` so citations can be traced back to source pages.

## HNSW boundary

Do not implement or tune HNSW during the `2026-06-08` to `2026-06-19` runnable-code phase. The current goal is a correct end-to-end RAG flow. HNSW tuning belongs to a later optimization phase after retrieval quality, latency, and dataset size are measured.

## PostgreSQL vs Qdrant

PostgreSQL is the source of truth.

Qdrant is not the source of truth. It stores only vector points and minimal payload for filtering/tracing.

Do not store long asset lists, rich relationship data, or governance metadata only in Qdrant. Join from PostgreSQL when needed.

Version governance also belongs in PostgreSQL. Use structured `document_version_relationships` rows for `replaces`, `amends`, and `supplements`; Qdrant payload may duplicate small IDs for tracing but must not be the source of truth for deciding which versions to include.

## Recommended stack

| Area | Suggested technology |
|---|---|
| Frontend | Flutter |
| Mobile/Web UI | Flutter Material 3, responsive layout |
| State management | Riverpod or BLoC; prefer one pattern consistently |
| API client | Dio or generated OpenAPI client |
| Backend API | FastAPI |
| RAG Service | FastAPI Python service |
| RAG framework | LangChain |
| OCR | `ocr-pvl` |
| Chunking | LangChain heading-aware parent-child chunking |
| Embedding | `BAAI/bge-m3` |
| Database | PostgreSQL |
| Vector DB | Qdrant |
| Storage | Local storage first, later MinIO/S3-compatible |
| Queue | Start sync/background task; later Celery/RQ/Redis |
| Monitoring | Structured logs first; later OpenTelemetry/Langfuse |

## Current backend structure

The current backend folder structure is authoritative. Codex must follow it instead of creating a new `modules/`, `db/`, `embeddings/`, `vector_index/`, or `rag_service/` structure.

```text
backend/
├── app/
│   ├── api/
│   ├── config/
│   ├── core/
│   ├── databases/
│   ├── embedding/
│   ├── ingestion/
│   ├── llm/
│   ├── retrieval/
│   ├── schemas/
│   ├── vectorstore/
│   ├── __init__.py
│   └── main.py
├── logs/
└── .dockerignore
```

## Backend folder boundary

| Folder | Responsibility |
|---|---|
| `app/api` | FastAPI route definitions and router registration. Keep handlers thin. |
| `app/config` | Environment variables, settings, service URLs, model names, database/Qdrant config. |
| `app/core` | Shared utilities: exceptions, dependency injection, security helpers, logging, constants. |
| `app/databases` | PostgreSQL engine/session, SQLAlchemy/SQLModel models, base metadata, migration helpers. |
| `app/embedding` | BGE-M3 model loading, text embedding, batch embedding, vector normalization. |
| `app/ingestion` | Upload, `ocr-pvl` OCR/parser workflow, Markdown normalization, metadata validation, LangChain chunking orchestration, indexing job orchestration. |
| `app/llm` | LLM client, grounded prompt builder, answer generation, answer formatting. |
| `app/retrieval` | LangChain-compatible retrieval orchestration, metadata filters, dense retrieval, sparse retrieval, hybrid retrieval, RRF fusion, reranking, parent context expansion. |
| `app/schemas` | Pydantic request/response schemas and DTOs. |
| `app/vectorstore` | Qdrant client, collection creation, vector upsert, vector search, deactivate/delete points. |
| `app/main.py` | FastAPI application entrypoint and top-level router registration. |

## Feature-to-folder mapping

| Feature/task | Primary folder(s) |
|---|---|
| Auth endpoints | `app/api`, `app/core`, `app/schemas` |
| Department/document type APIs | `app/api`, `app/databases`, `app/schemas` |
| Document/version metadata APIs | `app/api`, `app/databases`, `app/schemas` |
| Asset/form APIs | `app/api`, `app/databases`, `app/schemas` |
| Ingestion job creation/status | `app/api`, `app/ingestion`, `app/databases`, `app/schemas` |
| OCR/text extraction | `app/ingestion` using `ocr-pvl` |
| Metadata validation | `app/ingestion`, `app/databases` |
| Chunk preview/persist | `app/ingestion`, `app/databases` using LangChain chunking utilities |
| Embedding | `app/embedding` using `BAAI/bge-m3` |
| Qdrant upsert/search/deactivate | `app/vectorstore` |
| Retrieval/rerank/context expansion | `app/retrieval`, `app/vectorstore`, `app/databases` |
| LLM answer generation | `app/llm`, `app/retrieval` |
| `/rag/answer` endpoint | `app/api`, `app/retrieval`, `app/llm`, `app/schemas` |

## Frontend boundary

Flutter is a presentation client. Flutter should call Backend API and RAG endpoints, then render returned data.

Flutter must not:

- connect directly to PostgreSQL or Qdrant;
- decide whether a document is valid, latest, public, or approved without backend confirmation;
- hard-code procedure content, deadlines, fees, departments, or forms;
- bypass citation validation;
- store official document metadata as local truth.
