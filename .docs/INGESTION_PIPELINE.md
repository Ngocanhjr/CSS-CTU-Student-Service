# Ingestion Pipeline Guide

## Pipeline overview

```text
Original file
→ attachment intake tracking
→ OCR/parser output from ocr-pvl
→ Markdown cleaning
→ human review
→ canonical Markdown in 01_Dataset
→ document/version metadata validation
→ LangChain structure/heading-aware parent-child chunking
→ embed child chunks with BGE-M3
→ index child chunks into Qdrant
→ retrieval on child chunks
→ parent context expansion
→ grounded answer with citation
```

## Required tools

Updated: `2026-06-08`

| Stage | Required tool/framework |
|---|---|
| OCR | `ocr-pvl` |
| OCR internal components | PaddleOCR + VietOCR + LlamaParse through `ocr-pvl` |
| Markdown normalization input | `ocr-pvl` Markdown output with page markers |
| Chunking | LangChain chunking utilities with project heading-aware parent-child rules |
| Embedding | `BAAI/bge-m3` |
| Vector index | Qdrant collection using cosine distance |


## OCR-PVL mode selection

Use `ocr-pvl` for all OCR/parser work in this project. The backend should not decide to use a separate OCR provider outside this tool.

Recommended behavior inside the OCR-PVL step:

| Case | OCR-PVL behavior |
|---|---|
| Normal text page | PaddleOCR/layout detection + VietOCR Vietnamese recognition. |
| Vietnamese scanned text | VietOCR-focused recognition and cleanup. |
| Table-heavy page | Use LlamaParse/table path so Markdown keeps table structure. |
| Complex layout | Prefer LlamaParse path when Paddle/VietOCR output loses reading order or table shape. |

Required OCR Markdown output:

- preserve page markers, for example `<!-- page: 4 -->`;
- preserve table structure when it affects procedure requirements, fees, deadlines, forms, or departments;
- preserve headings/lists because LangChain chunking depends on structure;
- do not rewrite official procedural meaning during OCR cleanup.

## Do not skip review

Do not chunk or index OCR output directly before metadata validation and human review.

## Recommended admin workflow

| Step | Actor | Result |
|---|---|---|
| Upload document | Admin | Original file stored |
| Create ingestion job | Backend | Job status created |
| OCR/text extraction | Worker/service running `ocr-pvl` | OCR output Markdown |
| Markdown cleaning | Admin/reviewer/AI-assisted | Clean Markdown |
| Metadata completion | Admin | YAML frontmatter completed |
| Metadata validation | Backend | Valid/invalid with reason |
| Version relationship sync | Backend | `document_version_relationships` updated |
| Human review | Reviewer | approved/rejected/need_fix |
| Chunking | Backend/RAG service with LangChain | Parent/child chunks |
| Embedding | Worker/service with `BAAI/bge-m3` | Vectors created |
| Qdrant indexing | Worker/service | Points upserted |
| Publish | Backend | Document active in RAG |

## Required YAML before chunking

```yaml
---
document_id: ""
version_id: ""
title: ""
document_type: "noi_quy | quy_trinh | bieu_mau | hoi_dap"
domain: ""
department: ""
audience:
  - "student"

code: ""
issued_date:
effective_date:
expiry_date:
version: ""
is_latest: false
version_role: "base"
validity_status: "unchecked"
replaces: []
replaced_by: []
amends: []
amended_by: []
supplements: []
supplemented_by: []

collection_status: "collected"
ocr_status: "done"
review_status: "not_reviewed"
rag_status: "not_indexed"

source_url: ""
source_file: ""
source_path: ""
file_type: "pdf"
accessed_date:

language: "vi"
confidentiality: "public"
citation_type: "page"
ocr_engine: "ocr-pvl"
parser: "paddleocr+vietocr+llamaparse"
embedding_model: "BAAI/bge-m3"
created_at:
updated_at:
checksum:
---
```

## Indexing and publish rule

**Indexing eligibility** — A document version may be chunked/embedded/indexed when:

```text
ocr_status = "done"
AND review_status = "approved"
AND validity_status = "valid"
AND confidentiality = "public"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

**Note on `is_latest`:** Do not require `is_latest = true` for indexing eligibility. Older documents may still be valid and useful as supplementary, referenced, or required context. Use `is_latest` only as a ranking preference when multiple versions of the same document exist.

**Version governance:** Do not mark a base document as `replaced` when a newer document only amends or supplements part of it. Keep the base version `valid` and store structured version relationships during ingestion:

```text
replacement: source version replaces target version
amendment: source version amends target/base version
supplement: source version supplements target/base version
```

Chunking remains per-version. Retrieval is responsible for adding related base/amendment/supplement versions.

After chunks are embedded and Qdrant points are successfully upserted, the backend may transition:

```text
rag_status: indexed → published
```

Student-facing retrieval must only use chunks where:

```text
rag_status = "published"
```

## Ingestion job stages

Use `current_stage`, progress counters, timestamps, and `error_message` to track ingestion jobs:

```text
uploaded
ocr_running
ocr_done
metadata_pending
metadata_validated
review_pending
approved
chunking_done
embedded
indexed
active
```

## OCR cleaning rules

The OCR source for this project is `ocr-pvl`. Keep `ocr-pvl` page markers and table output intact unless a reviewer confirms that the OCR output is wrong. `ocr-pvl` may use PaddleOCR, VietOCR, and LlamaParse internally; do not remove table structure just because it came from the LlamaParse path.

Keep:

- headings;
- chapter/article/clause structure;
- tables;
- lists;
- page markers;
- form links;
- source anchors.

Remove:

- repeated headers/footers;
- decorative layout;
- duplicate page noise;
- unnecessary spacing.

Never:

- rewrite legal/procedural meaning;
- add missing deadlines/fees/forms;
- change dates, codes, department names, or conditions without source.
