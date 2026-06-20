# Coding Rules

## General rules

- Keep code modular and testable.
- Do not put business logic directly in route/controller files.
- Keep frontend display logic separate from backend security/validity logic.
- Prefer explicit status transitions for ingestion and publishing.
- Add migrations when schema changes.
- Add tests for status validation, publish rule, retrieval filters, and citation validation.
- Follow the current backend folder structure. Do not create a new `modules/`, `db/`, `embeddings/`, `vector_index/`, `rag_service/`, or `services/` structure.
- Use `ocr-pvl` as the OCR tool for project documents.
- Treat PaddleOCR, VietOCR, and LlamaParse as internal tools of `ocr-pvl`; backend code should integrate through `ocr-pvl`, not bypass it.
- Use LangChain for RAG workflow orchestration, especially chunking and retrieval composition.
- Use `BAAI/bge-m3` as the embedding vector model for the first Qdrant collection.
- Do not implement HNSW tuning in the MVP/current runnable-code phase; keep it as a documented future optimization.

## Current schema decisions

- Do not add a document metadata `priority` field or `Priority` enum in `app/schemas/enums.py`.
- Do not add `chunking_strategy` to YAML metadata or a `ChunkingStrategy` enum. Chunking behavior is a fixed service-level decision for the MVP.
- Do not add `ocr_status = "not_required"`. Native text/Markdown or parser-only inputs still transition to `ocr_status = "done"` after extraction/parser validation is complete.

## Current FastAPI backend structure

This is the structure Codex must follow:

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

## Backend placement rules

| Code type | Place it in |
|---|---|
| FastAPI routers/endpoints | `app/api` |
| Pydantic request/response DTOs | `app/schemas` |
| Environment/app settings | `app/config` |
| Shared exceptions/dependencies/security/logging | `app/core` |
| PostgreSQL engine/session/models/repositories | `app/databases` |
| Upload/OCR/metadata validation/chunking/indexing workflow | `app/ingestion` with `ocr-pvl` and LangChain chunking |
| Embedding model and vector creation | `app/embedding` with `BAAI/bge-m3` |
| Qdrant client, collections, upsert/search/deactivate | `app/vectorstore` |
| Metadata filtering, dense/sparse retrieval, fusion, reranking, context expansion | `app/retrieval` with LangChain-compatible orchestration |
| LLM client, prompts, answer generation, citation validation | `app/llm` |
| FastAPI app startup/router registration | `app/main.py` |

## Route/service pattern

Prefer this pattern:

```text
app/api/<feature>.py
  → receives HTTP request
  → validates with app/schemas/<feature>.py
  → calls service from the correct domain folder
  → returns typed response

app/<domain>/service.py
  → contains business workflow

app/databases/repositories.py or app/databases/<feature>_repository.py
  → contains database operations
```

Examples:

| Feature | API | Schema | Service |
|---|---|---|---|
| Create ingestion job | `app/api/ingestion.py` | `app/schemas/ingestion.py` | `app/ingestion/service.py` |
| Validate metadata | `app/api/ingestion.py` | `app/schemas/ingestion.py` | `app/ingestion/metadata_validator.py` |
| Run OCR | `app/api/ingestion.py` or worker | `app/schemas/ingestion.py` | `app/ingestion/ocr_pvl.py` |
| Preview chunks | `app/api/ingestion.py` | `app/schemas/ingestion.py` | `app/ingestion/langchain_chunker.py` |
| Upsert Qdrant points | `app/api/ingestion.py` or worker | `app/schemas/ingestion.py` | `app/vectorstore/qdrant_client.py` + `app/embedding/service.py` |
| Search retrieval | `app/api/retrieval.py` | `app/schemas/retrieval.py` | `app/retrieval/service.py` |
| RAG answer | `app/api/rag.py` | `app/schemas/rag.py` | `app/retrieval/service.py` + `app/llm/answer_generator.py` |

## Ingestion service rules

OCR jobs must call `ocr-pvl`. Do not introduce another OCR provider for the MVP unless the project owner changes the stack decision. PaddleOCR, VietOCR, and LlamaParse must be used through the `ocr-pvl` workflow/wrapper.

Chunking jobs must use LangChain as the framework while preserving local CTU-specific rules for headings, page markers, tables, and citations.

Every ingestion stage must update `ingestion_jobs`.

Failures must record:

```text
current_stage = <stage_name>
error_message = <clear reason>
```

Do not silently skip invalid documents. Return a clear reason when a document cannot be indexed.

## Indexing and publish eligibility rule

Indexing eligibility and retrieval/publish eligibility are separate.

A document version may be chunked/embedded/indexed when:

```text
ocr_status = "done"
AND review_status = "approved"
AND validity_status = "valid"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

A document version may transition to `rag_status = "published"` only after Qdrant upsert succeeds and the same hard requirements above still hold. `published` is an output of indexing, not a prerequisite for indexing.

**Note on `is_latest`:** Do not require `is_latest = true` as a hard filter. Older documents may still be valid and necessary as supplementary, referenced, or contextual sources. Use `is_latest` only as a ranking preference when multiple versions of the same document conflict.

Version governance must distinguish full replacement from partial amendment/supplement:

```text
replacement  = new version replaces old version; old version becomes replaced/deactivated
amendment    = new version modifies part of a valid base version; retrieve both when relevant
supplement   = new version adds content to a valid base version; retrieve both when relevant
```

Do not set a base version to `validity_status = "replaced"` when the newer version only amends or supplements it.

After chunks are embedded and Qdrant points are successfully upserted, the backend may transition:

```text
rag_status: indexed → published
```

Student-facing retrieval must only use chunks where:

```text
rag_status = "published"
```


## HNSW rule

HNSW is not part of the current implementation target from `2026-06-08` to `2026-06-19`.

During MVP, code should focus on:

- correct Qdrant collection creation with BGE-M3 vector size and cosine distance;
- correct upsert/search path;
- metadata filtering;
- citation validation;
- runnable `/rag/answer` flow.

Only add HNSW-specific parameters, tuning, or benchmark tasks in a later optimization branch/phase after the RAG pipeline runs successfully.

## Retrieval code rules

- Apply metadata filter before or during retrieval.
- Join back to PostgreSQL for full metadata and asset relationships.
- Use LangChain for retriever composition and context assembly when implementing RAG workflow pieces.
- Validate citations before returning answer.
- Store trace/debug info for evaluation.
- Do not let Qdrant decide document validity or versioning.
- Resolve replacement/amendment/supplement relationships from PostgreSQL before context assembly.
- Do not retrieve expired, replaced, private, unreviewed, or unpublished chunks.

## Flutter frontend rules

- Use Flutter as the only frontend stack.
- Prefer Material 3 and responsive layout.
- Use one state-management pattern consistently, preferably Riverpod for MVP or BLoC if the project already uses it.
- Keep API DTOs separate from UI widgets.
- Keep business workflow decisions in Backend, not Flutter.
- Do not hard-code procedure content, forms, fees, deadlines, or departments in Flutter.
- Always render citation/source info when provided.
- Show backend validation errors, missing-source fallbacks, and citation warnings clearly.
- Add widget tests for critical screens when feasible.

## Flutter frontend structure

```text
frontend/
├── lib/
│   ├── main.dart
│   ├── app.dart
│   ├── core/
│   │   ├── config/
│   │   ├── network/
│   │   ├── theme/
│   │   ├── routing/
│   │   └── widgets/
│   ├── features/
│   │   ├── auth/
│   │   ├── chat/
│   │   ├── citations/
│   │   ├── procedures/
│   │   ├── assets/
│   │   ├── documents/
│   │   ├── ingestion/
│   │   └── admin_dashboard/
│   └── shared/
│       ├── models/
│       ├── dto/
│       └── utils/
└── test/
```

## Testing priorities

Add tests for:

- metadata validation;
- publish eligibility rule;
- ingestion stage transition;
- Qdrant payload creation;
- retrieval filter excluding expired/replaced/private/unreviewed chunks;
- citation validator behavior;
- `/rag/answer` fallback when sources are insufficient;
- Flutter chat screen and citation drawer when feasible.
