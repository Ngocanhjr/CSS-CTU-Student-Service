# 03. System Architecture

## Architecture

```text
Flutter
-> FastAPI Backend
-> PostgreSQL
-> Qdrant
-> LLM provider

[External, outside this codebase]
-> LlamaParse / OCR pipeline
-> Canonical Markdown review
-> Input to backend ingestion
```

## Core services

| Service | Responsibility |
|---|---|
| API | Versioned routes, auth/RBAC later, orchestration |
| Ingestion | Receive canonical Markdown, metadata validation, chunking, indexing job orchestration |
| Retrieval | Dense search, sparse search, RRF, parent expansion |
| LLM | Grounded answer generation and citation validation |
| PostgreSQL | Source of truth |
| Qdrant | Dense vector index |

> LlamaParse và OCR pipeline chạy bên ngoài backend. Backend chỉ nhận canonical
> Markdown đã được xử lý và review từ trước.

## API boundary

All public routes use `/api/v1`.

API details are maintained in `06_API_SPEC.md`.

## Job progress

Use `ingestion_jobs.current_step`.

Do not use `current_stage`.
