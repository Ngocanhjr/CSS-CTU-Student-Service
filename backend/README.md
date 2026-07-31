# CTU Student Service Backend

FastAPI backend for metadata governance, ingestion orchestration, hybrid retrieval, and grounded RAG answers.

## Scope

This backend **receives pre-processed canonical Markdown files** that have already been OCR'd and reviewed externally. LlamaParse and the OCR pipeline run outside this codebase.

The backend is responsible for:
- Accepting canonical Markdown + YAML metadata
- Validating metadata
- Chunking with parent-child strategy
- Embedding child chunks
- Indexing into Qdrant
- Hybrid retrieval (dense + sparse + RRF)
- Grounded answer generation with citations

## Required stack

Updated: `2026-07-04`

| Concern | Decision |
|---|---|
| API framework | FastAPI |
| RAG framework | LangChain |
| Chunking | `langchain-text-splitters` structural parent-child chunking |
| Embedding model | `BAAI/bge-m3` |
| Vector store | Qdrant |
| Metadata store | PostgreSQL |
| Retrieval | Hybrid: dense + sparse + RRF |
| HNSW / advanced reranker | Future upgrade only |

## Reranker configuration

Set these variables in the project `.env` to enable the semantic reranker:

```dotenv
JINA_API_KEY=<your Jina API key>
JINA_RERANK_MODEL=jina-reranker-v3
JINA_RERANK_URL=https://api.jina.ai/v1/rerank
JINA_RERANK_TIMEOUT=8
```

If Jina is unavailable, the backend preserves the hybrid RRF ranking instead
of falling back to keyword-only reranking.

## Query rewriting

Before retrieval, the configured LLM can generate up to two meaning-preserving
Vietnamese search variants. This is enabled by default and does not require a
document re-index. Control it with:

```dotenv
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_MAX_QUERIES=3
QUERY_REWRITE_TIMEOUT_SECONDS=12
```

## Indexing and retrieval policy

Student-facing `/api/v1/rag/answer` must use:

```text
review_status = approved
rag_status = published
```

## Module ownership

| Module | Responsibility |
|---|---|
| `app/ingestion` | Receive canonical Markdown, metadata validation, chunking, indexing job orchestration |
| `app/embedding` | BGE-M3 model loading, batch embedding, vector normalization |
| `app/vectorstore` | Qdrant collection creation, upsert, search |
| `app/retrieval` | Metadata filters, dense retrieval, sparse retrieval, RRF fusion, parent context expansion |
| `app/llm` | Grounded prompt construction, answer generation, citation validation |
| `app/databases` | PostgreSQL models, repositories, migrations |
| `app/schemas` | Pydantic DTOs |
| `app/api` | FastAPI routers |

> `app/ocr` does not exist. OCR/LlamaParse processing happens outside this backend.

## MVP flow

```text
Canonical Markdown (pre-OCR'd, reviewed externally)
-> metadata validation
-> langchain-text-splitters parent-child chunks
-> BGE-M3 vectors
-> PostgreSQL metadata and sparse search
-> Qdrant dense search
-> RRF fusion
-> /api/v1/rag/answer response with citations
```

## Deferred

HNSW tuning and advanced reranking are post-MVP optimizations.
