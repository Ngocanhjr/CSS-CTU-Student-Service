# Project Context — CTU Student Service

## Goal

CTU Student Service is a **Procedural RAG System** for Trường Đại học Cần Thơ.

The system helps students complete administrative procedures, not only ask FAQ-style questions.

## Current implementation decisions

Updated: `2026-06-08`

| Area | Decision |
|---|---|
| OCR tool | `ocr-pvl` |
| RAG workflow framework | LangChain |
| Chunking | LangChain implementation of heading-aware parent-child chunking |
| Embedding vector model | `BAAI/bge-m3` |
| Runnable-code target | End-to-end vertical slice by `2026-06-19` |

## OCR-PVL decision

`ocr-pvl` is the official OCR tool for the current project phase.

Inside this project, `ocr-pvl` means:

| Component | Role |
|---|---|
| PaddleOCR | General OCR/layout detection for scanned PDF/image pages. |
| VietOCR | Vietnamese text recognition and correction support. |
| LlamaParse | Table-heavy or layout-complex pages, especially when tables must be preserved for RAG citation. |

OCR output is an intermediate artifact. The canonical RAG source remains reviewed Markdown with metadata, page markers, and citation anchors.

## MVP vs future optimization

For the implementation window from `2026-06-08` to `2026-06-19`, the goal is runnable code, not retrieval micro-optimization.

Current MVP applies:

- `ocr-pvl` for OCR/parser output;
- LangChain for chunking/RAG orchestration;
- `BAAI/bge-m3` for embeddings;
- Qdrant with cosine distance for vector storage/search.

HNSW-specific tuning is a future enhancement after the end-to-end RAG pipeline runs successfully and benchmark results show that search speed needs improvement.


It must support:

- procedure classification;
- retrieval of official CTU documents;
- eligibility/condition checking;
- checklist generation;
- form/asset recommendation;
- department routing;
- answer generation with mandatory citations.

## Core problem

Student-service information is scattered across:

- PDF regulations;
- procedure documents;
- Word/PDF forms;
- announcements;
- department websites;
- CTU office pages.

A normal LLM chatbot may hallucinate. Keyword search may miss semantic matches. Therefore, this project uses RAG with document governance, versioning, effective-date filtering, and citation validation.

## Data source order

| Source type | Use |
|---|---|
| Official CTU PDF/DOCX/form | Primary source |
| Canonical Markdown in `01_Dataset` | Main source for chunking and RAG |
| OCR output | Intermediate only |
| Tracking notes | Workflow tracking only, not RAG source |
| Research notes | Design reference only, not student-answer corpus |

## Answer principle

For student-facing answers:

- cite document/version/page/section;
- do not invent deadlines, fees, required forms, departments, or eligibility conditions;
- say the system lacks enough source information when retrieval is insufficient;
- prefer explicit replacement relationships first when sources conflict, then use latest/effective-date signals as ranking preferences.
