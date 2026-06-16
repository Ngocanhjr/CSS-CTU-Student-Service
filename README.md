# CTU Student Service Chatbot

This folder contains the chatbot implementation workspace for CTU Student Service.

## Current decisions

Updated: `2026-06-08`

| Area | Decision |
|---|---|
| Frontend | Flutter |
| Backend API | FastAPI |
| RAG Service | FastAPI Python service |
| OCR tool | `ocr-pvl` |
| OCR engines inside `ocr-pvl` | PaddleOCR, VietOCR, and LlamaParse for table-heavy OCR cases |
| RAG workflow framework | LangChain |
| Chunking | LangChain heading-aware / parent-child chunking |
| Embedding vector model | `BAAI/bge-m3` |
| Vector DB | Qdrant |
| Metadata DB | PostgreSQL |
| HNSW / advanced vector optimization | Future upgrade only, after the basic RAG workflow runs successfully; do not apply it in the current MVP pipeline |
| Runnable-code target | End-to-end vertical slice from `2026-06-08` to `2026-06-19` |

## Implementation target

From `2026-06-08` to `2026-06-19`, the project should produce a running vertical slice with working code:

```text
ocr-pvl OCR
  - PaddleOCR / VietOCR for normal Vietnamese document OCR
  - LlamaParse for table-heavy pages or difficult table layouts
→ reviewed canonical Markdown
→ LangChain chunking
→ BGE-M3 embeddings
→ Qdrant indexing and retrieval
→ /rag/answer with citations
→ minimal Flutter chat UI
```

## Current MVP scope

The current implementation should focus on getting the full RAG pipeline running first:

1. OCR documents with `ocr-pvl`.
2. Normalize and review Markdown output.
3. Validate required metadata.
4. Chunk documents with LangChain.
5. Create embeddings with `BAAI/bge-m3`.
6. Store metadata in PostgreSQL.
7. Store vectors in Qdrant.
8. Return grounded answers with citations.
9. Connect the minimal Flutter UI to the backend.

Do **not** prioritize HNSW tuning, custom HNSW search strategy, or advanced vector-index optimization in this phase. HNSW-related optimization belongs to the upgraded version after the MVP RAG flow is already running correctly.

## Documentation

Read `AGENTS.md` first, then the relevant file in `.docs/`:

| Need | File |
|---|---|
| Project context | `.docs/PROJECT_CONTEXT.md` |
| Architecture | `.docs/ARCHITECTURE.md` |
| Backend structure | `.docs/BACKEND_STRUCTURE.md` |
| Ingestion and OCR | `.docs/INGESTION_PIPELINE.md` |
| RAG retrieval | `.docs/RAG_RETRIEVAL.md` |
| Database schema | `.docs/DATABASE_SCHEMA.md` |
| Flutter UI | `.docs/FRONTEND_FLUTTER.md` |
| Coding rules | `.docs/CODING_RULES.md` |
| Implementation order | `.docs/IMPLEMENTATION_ORDER.md` |
