# 01. Project Overview

## Goal

CTU Student Service helps students ask procedural questions and receive grounded answers with citations from approved university documents.

## MVP stack

| Area | Decision |
|---|---|
| Frontend | Flutter |
| Backend | FastAPI |
| OCR/parser | LlamaParse only |
| RAG | LangChain |
| Chunking | `langchain-text-splitters` parent-child |
| Embedding | `BAAI/bge-m3` |
| Metadata DB | PostgreSQL |
| Vector DB | Qdrant |
| Retrieval | Hybrid dense + sparse + RRF |

## MVP flow

```text
Upload document
-> LlamaParse
-> reviewed canonical Markdown
-> metadata validation
-> chunking
-> embedding
-> PostgreSQL + Qdrant
-> /api/v1/rag/answer
-> answer with citations
```

## Non-MVP

- HNSW tuning.
- Advanced reranker.
- Query expansion.
- Non-Flutter frontend.
- Non-FastAPI backend.
