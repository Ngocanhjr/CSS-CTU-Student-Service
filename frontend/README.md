# CTU Student Service Frontend

Flutter frontend for the student chat UI, citation viewer, procedure screens, and admin ingestion/review workflow.

## Frontend decision

Updated: `2026-06-08`

Use Flutter only. Do not introduce React, Next.js, Tailwind, or plain HTML for the app UI unless the project owner changes the decision.

## Backend pipeline shown in UI

Admin screens should display the current backend pipeline decisions:

| Stage | Decision |
|---|---|
| OCR | `ocr-pvl` using PaddleOCR / VietOCR for normal OCR and LlamaParse for table-heavy OCR cases |
| Chunking / RAG workflow | LangChain |
| Embedding | `BAAI/bge-m3` |
| Vector store | Qdrant |
| Metadata store | PostgreSQL |
| HNSW optimization | Future upgrade only; not part of the current MVP pipeline |

## MVP target from 2026-06-08 to 2026-06-19

The frontend should support the minimum UI needed to verify a running vertical slice with working code:

- chat screen calling `/rag/answer`;
- citation/source drawer;
- related assets/forms section;
- admin ingestion job status showing OCR, review, metadata validation, chunk, embed, and index stages;
- clear status labels for `ocr-pvl`, LangChain chunking, BGE-M3 embedding, PostgreSQL metadata, and Qdrant indexing.

Flutter must not hard-code official procedure content, deadlines, fees, forms, or departments. These must come from backend responses with citations.

## UI note for HNSW

Do not show HNSW as an active feature in the MVP UI. If it appears in admin planning screens, label it clearly as a future optimization after the basic RAG workflow has run successfully.
