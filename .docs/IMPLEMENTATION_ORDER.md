# Implementation Order

## First vertical slice

Do this before building a large system:

1. Clean vault paths and duplicate PDFs.
2. Pick 3–5 seed documents.
3. OCR/parse to Markdown with `ocr-pvl`.
4. Clean Markdown and preserve page markers.
5. Add YAML metadata.
6. Validate metadata enums and version relationships.
7. Human review and approve.
8. Persist document/version metadata and version relationships in PostgreSQL.
9. Chunk with LangChain using heading-aware parent-child strategy.
10. Embed child chunks with BGE-M3.
11. Create Qdrant collection with BGE-M3 vector size and cosine distance only.
12. Upsert child chunks with minimal payload.
13. Add PostgreSQL FTS/BM25 search.
14. Add RRF fusion.
15. Add reranker.
16. Add version relationship expansion.
17. Add parent context expansion.
18. Add citation validation.
19. Build `/rag/answer` endpoint and minimal Flutter UI.
20. Create 50–100 benchmark questions.

## Implementation plan: 2026-06-08 to 2026-06-19

Target: by `2026-06-19`, the project must run an end-to-end code path for a small vertical slice:

```text
ocr-pvl OCR
→ reviewed Markdown
→ metadata/version relationship validation
→ LangChain chunking
→ BGE-M3 embeddings
→ Qdrant indexing
→ /rag/answer with citations
```

HNSW-specific tuning is deliberately excluded from this date range. It is only considered after the code path above runs successfully.

| Date range | Focus | Output |
|---|---|---|
| 2026-06-08 to 2026-06-09 | Finalize stack and vertical-slice documents | `ocr-pvl`, LangChain, BGE-M3, Qdrant config documented; 3–5 docs selected |
| 2026-06-10 to 2026-06-11 | OCR + Markdown cleaning | `ocr-pvl` output with page markers/headings/tables; cleaned Markdown ready for review |
| 2026-06-12 to 2026-06-13 | Canonical dataset + metadata/version validation | Approved canonical Markdown, backend metadata validation path, version relationship fields |
| 2026-06-14 to 2026-06-15 | LangChain chunking + BGE-M3 embedding | Parent/child chunks persisted; embeddings generated with `BAAI/bge-m3` |
| 2026-06-16 to 2026-06-17 | Qdrant indexing + retrieval POC | Qdrant collection `ctu_chunks_bge_m3` with cosine distance; retrieval returns cited chunks; no HNSW tuning |
| 2026-06-18 | `/rag/answer` vertical slice | Backend answer endpoint returns grounded answer, citations, and related assets |
| 2026-06-19 | Run and verify code | Local code path runs end-to-end with 3–5 documents and smoke-test questions |

## Do not build too early

Delay these until needed:

- `procedures` table;
- `procedure_steps`;
- `eligibility_rules`;
- full chat history;
- RBAC/audit complexity;
- advanced Flutter admin dashboard;
- multi-agent workflow;
- HNSW tuning;

Start with one correct pipeline before expanding.


## Flutter frontend MVP order

1. Create Flutter project structure.
2. Add theme, routing, network client, and environment config.
3. Implement chat screen calling `/rag/answer`.
4. Implement citation drawer and related assets section.
5. Implement admin document list and ingestion job progress screens.
6. Implement metadata validation/review UI.
7. Implement publish/reindex actions only after backend endpoints exist.


## Backend-aligned coding order

When starting backend implementation, follow this order inside the current folder structure:

1. `app/config`: settings and environment loading.
2. `app/schemas`: shared enums and Pydantic DTOs, especially `schemas/enums.py` and `schemas/rag.py`.
3. `app/databases`: PostgreSQL session, base models, document/version/chunk/relationship models.
4. `app/api`: health check and basic router registration.
5. `app/ingestion`: metadata validation and ingestion job progress flow.
6. `app/ingestion`: `ocr-pvl` integration and LangChain chunking service.
7. `app/embedding`: BGE-M3 embedding service.
8. `app/vectorstore`: Qdrant collection and upsert/search helpers.
9. `app/retrieval`: LangChain-compatible metadata filters, dense/sparse retrieval, fusion, rerank, version relationship expansion, context expansion.
10. `app/llm`: prompt and grounded answer generation.
11. `app/api/rag.py`: `/rag/answer` endpoint.
12. Flutter UI: chat screen, citation drawer, admin ingestion progress.
