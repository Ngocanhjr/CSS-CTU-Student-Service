# CTU Student Service Backend

FastAPI backend for metadata governance, ingestion orchestration, retrieval, and grounded RAG answers.

## Required stack

Updated: `2026-06-18`

| Concern | Decision |
|---|---|
| API framework | FastAPI |
| OCR tool | `ocr-pvl` |
| OCR engines inside `ocr-pvl` | PaddleOCR, VietOCR, and LlamaParse for table-heavy OCR cases |
| RAG framework | LangChain |
| Chunking | LangChain heading-aware / parent-child chunking |
| Embedding model | `BAAI/bge-m3` |
| Vector store | Qdrant |
| Metadata store | PostgreSQL |
| HNSW / advanced vector optimization | Future upgrade only; not part of the current MVP implementation |

## Indexing and retrieval policy

Expired documents are still useful for audit and admin/internal historical search. The backend may ingest, chunk, embed, and index them with:

```text
validity_status = expired
review_status = approved
rag_status = indexed
```

Student-facing `/rag/answer` must keep the stricter hard filter:

```text
validity_status = valid
review_status = approved
rag_status = published
```

Do not publish expired documents for student answers.

## Module ownership

| Module | Responsibility |
|---|---|
| `app/ingestion` | Upload flow, `ocr-pvl` OCR integration, Markdown normalization, metadata validation, LangChain chunking, indexing job orchestration |
| `app/ocr` | OCR adapter layer for `ocr-pvl`; use PaddleOCR / VietOCR for normal pages and LlamaParse for pages with complex tables |
| `app/embedding` | BGE-M3 model loading, batch embedding, vector normalization, embedding version tracking |
| `app/vectorstore` | Qdrant collection creation, upsert, search, deactivate/delete |
| `app/retrieval` | LangChain-compatible retriever composition, metadata filters, hybrid retrieval, fusion, reranking, parent context expansion |
| `app/llm` | Grounded prompt construction, answer generation, citation validation |

## MVP target from 2026-06-08 to 2026-06-19

Run one end-to-end vertical slice with working code:

```text
ocr-pvl OCR
  - PaddleOCR / VietOCR for normal Vietnamese text pages
  - LlamaParse for table-heavy or difficult table pages
→ reviewed Markdown
→ metadata validation
→ LangChain parent-child chunks
→ BGE-M3 vectors
→ Qdrant points
→ PostgreSQL document/chunk metadata
→ /rag/answer response with citations
```

## HNSW decision

HNSW-related work is deferred to the upgraded version. In the current implementation phase, do not spend time on custom HNSW tuning, custom HNSW parameters, or HNSW-based optimization experiments. The first goal is to make the basic RAG pipeline run correctly, return relevant answers, and provide citations.

After the MVP RAG flow is stable, HNSW tuning can be revisited as a performance and retrieval-quality optimization task.
