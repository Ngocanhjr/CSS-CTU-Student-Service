# Backend Structure

This backend uses FastAPI and follows the current folder structure below. Codex must follow this structure instead of creating parallel or duplicate modules.

## Required backend stack

Updated: `2026-06-08`

| Concern | Required choice |
|---|---|
| OCR | `ocr-pvl` integration belongs in `app/ingestion` |
| OCR internal tools | PaddleOCR, VietOCR, LlamaParse through `ocr-pvl` |
| RAG/chunking framework | LangChain integration belongs in `app/ingestion` and `app/retrieval` |
| Embedding | `BAAI/bge-m3` integration belongs in `app/embedding` |
| Vector store | Qdrant integration belongs in `app/vectorstore` |
| HNSW | Future optimization only; do not implement/tune in MVP code path |

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

## Folder responsibilities

| Folder | Responsibility |
|---|---|
| `app/api` | FastAPI routers and endpoint definitions. Do not put business logic directly in route handlers. |
| `app/config` | Environment variables, application settings, service URLs, model names, database/Qdrant configuration. |
| `app/core` | Shared core utilities such as exceptions, dependency injection, security helpers, constants, logging helpers. |
| `app/databases` | PostgreSQL connection, SQLAlchemy/SQLModel session, base model, database initialization helpers, migration helpers. |
| `app/embedding` | BGE-M3 model loading, text embedding, batch embedding, vector normalization. |
| `app/ingestion` | Document ingestion workflow: `ocr-pvl` OCR/text extraction, Markdown normalization, metadata validation, LangChain chunking orchestration, indexing job orchestration. |
| `app/llm` | LLM client, prompt templates, grounded answer generation, answer formatting. |
| `app/retrieval` | LangChain-compatible retrieval orchestration, metadata filtering, dense retrieval, sparse retrieval, hybrid retrieval, RRF fusion, reranking, parent context expansion. |
| `app/schemas` | Pydantic schemas for API requests and responses. |
| `app/vectorstore` | Qdrant client, collection creation, vector upsert, search, deactivate/delete points. |
| `app/main.py` | FastAPI application entrypoint and router registration. |


### OCR-PVL service boundary

`app/ingestion/ocr_pvl.py` should wrap the project OCR command/service. Backend code should call this wrapper instead of calling PaddleOCR, VietOCR, or LlamaParse directly from route handlers.

Recommended responsibility split:

| Component | Backend responsibility |
|---|---|
| PaddleOCR | Used inside `ocr-pvl` for page OCR/layout detection. |
| VietOCR | Used inside `ocr-pvl` for Vietnamese text recognition. |
| LlamaParse | Used inside `ocr-pvl` for table-heavy pages or complex table preservation. |
| Backend wrapper | Run job, capture output path, update `ingestion_jobs`, normalize Markdown path/status. |

## Implementation rules

- Keep PostgreSQL logic inside `app/databases`.
- Keep Qdrant logic inside `app/vectorstore`.
- Keep BGE-M3 embedding logic inside `app/embedding`.
- Keep retrieval orchestration and LangChain retrieval composition inside `app/retrieval`.
- Keep `ocr-pvl`, metadata validation, LangChain chunking, and indexing pipeline logic inside `app/ingestion`.
- Keep LLM prompt and answer generation inside `app/llm`.
- Keep route handlers thin. API routes should call service functions from the correct module.
- Do not add HNSW tuning, HNSW-specific config, or HNSW benchmark work to the MVP vertical slice.
- Keep request/response DTOs in `app/schemas`.
- Do not create duplicate folders such as `database`, `db`, `embeddings`, `vector_index`, `rag_service`, `modules`, or `services` unless the project structure is intentionally refactored.
- Do not hard-code procedure content, deadlines, departments, fees, or forms in backend code.
- Operational answers must come from approved, valid, public, indexed documents with citations.

## Suggested internal files

These names are suggestions, not strict requirements. Use them when implementing the corresponding feature.

```text
app/config/
├── settings.py

app/core/
├── exceptions.py
├── dependencies.py
├── logging.py
├── security.py

app/databases/
├── session.py
├── base.py
├── repositories.py
├── models/
│   ├── __init__.py
│   ├── document.py
│   ├── document_relationship.py
│   └── chunk.py

app/api/
├── health.py
├── reference_data.py
├── documents.py
├── ingestion.py
├── retrieval.py

app/schemas/
├── enums.py
├── rag.py
├── common.py
├── reference_data.py
├── documents.py
├── ingestion.py
├── retrieval.py
├── rag.py

app/ingestion/
├── service.py
├── metadata_validator.py
├── markdown_parser.py
├── ocr_pvl.py
├── chunking/
│   ├── __init__.py
│   └── markdown_chunker.py
├── job_runner.py

app/embedding/
├── service.py
├── bge_m3.py

app/vectorstore/
├── qdrant_client.py
├── collections.py
├── payloads.py

app/retrieval/
├── service.py
├── langchain_pipeline.py
├── filters.py
├── versioning.py
├── dense.py
├── sparse.py
├── fusion.py
├── reranker.py
├── context.py

app/llm/
├── client.py
├── prompts.py
├── answer_generator.py
├── citation_validator.py
```

## API route rule

Route files in `app/api` should only:

1. validate request body/query/path parameters through Pydantic schemas;
2. call the correct service layer;
3. return typed response schemas;
4. translate known exceptions into HTTP errors.

Route files should not:

- directly run OCR;
- directly call Qdrant;
- directly embed text;
- directly construct long prompts;
- directly decide publish eligibility without calling the ingestion/validation service.

## Versioning boundary

Use `app/schemas/enums.py` for shared status and version enums, including `VersionRole`.

Use `app/schemas/rag.py` for Pydantic `DocumentMetadata` and `Chunk` schemas. The chunker should return `list[Chunk]`, not SQLAlchemy models.

Use `app/databases/models/document_relationship.py` for structured version relationships:

```text
replacement version --replaces--> old version
amendment version   --amends--> base version
supplement version  --supplements--> base version
```

Use `app/retrieval/versioning.py` to expand retrieved chunks with related valid base/amendment/supplement versions. Do not put this logic in Qdrant payload handling.
