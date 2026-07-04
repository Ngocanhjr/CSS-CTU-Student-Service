# CTU Student Service Frontend

Flutter frontend for the student chat UI, citation viewer, procedure screens, and admin ingestion/review workflow.

## Frontend decision

Updated: `2026-07-04`

Use Flutter only. Do not introduce React, Next.js, Tailwind, or plain HTML for the app UI unless the project owner changes the decision.

## Backend pipeline shown in UI

| Stage | Decision |
|---|---|
| OCR/parser | LlamaParse only |
| Chunking / RAG workflow | LangChain |
| Embedding | `BAAI/bge-m3` |
| Retrieval | Hybrid: Qdrant dense + PostgreSQL sparse + RRF |
| Metadata store | PostgreSQL |
| HNSW optimization | Future upgrade only |

## MVP UI scope

- Chat screen calling `/api/v1/rag/answer`.
- Citation/source drawer.
- Related assets/forms section.
- Admin ingestion job status showing parse, review, metadata validation, chunk, embed, and index steps.
- Status labels for LlamaParse, chunking, embedding, PostgreSQL, and Qdrant.

Flutter must not hard-code official procedure content, deadlines, fees, forms, or departments. These must come from backend responses with citations.
