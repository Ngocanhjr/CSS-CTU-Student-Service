# 08. Đặc Tả OCR và Ingestion Pipeline

**Version:** 1.0  
**Last Updated:** 2026-06-16  
**Status:** Final

---

## Pipeline Overview

```
1. Upload file → storage
2. Create ingestion_job (current_stage: uploaded)
3. OCR via ocr-pvl → Markdown output
4. Markdown normalization → cleaned output
5. Human review (Obsidian/editor)
6. Approved Markdown → 01_Dataset/ (canonical)
7. Metadata validation (YAML frontmatter)
8. LangChain chunking → parent-child chunks
9. BGE-M3 embedding → vectors
10. Qdrant upsert → indexed
11. Update rag_status: published
```

---

## OCR Tools (via ocr-pvl)

**Backend calls:** `ocr-pvl` only (không call trực tiếp PaddleOCR/VietOCR/LlamaParse)

**ocr-pvl router:**
- Normal pages → PaddleOCR + VietOCR
- Table-heavy pages → LlamaParse
- Complex layouts → LlamaParse

---

## OCR Output Requirements

**Must preserve:**
- Page markers: `<!-- page: N -->`
- Heading structure: `#`, `##`, `###`
- Tables: Markdown table format
- Lists: `-` or `*` format

---

## Markdown Normalization

**Cleaning:**
- Remove extra blank lines (max 1)
- Fix heading hierarchy (no skip)
- Normalize list formatting
- Validate page markers exist

---

## Human Review Workflow

**Steps:**
1. Reviewer opens Markdown trong Obsidian
2. Fix OCR errors, formatting issues
3. Add/validate YAML frontmatter
4. Save → 01_Dataset/
5. Update review_status: approved

---

## Metadata Validation

**Required fields check:**
```python
REQUIRED = ["document_id", "version_id", "document_type"]
PUBLISH_REQUIRED = ["effective_date"]
```

**Date validation:** effective_date <= expiry_date (if both are set)

**Enum validation:** document_type, confidentiality, etc.

---

## Ingestion Job Stage Lifecycle

```
uploaded → ocr_running → ocr_done → need_review → 
approved → chunking → embedding → indexing → active
```

**Error tracking:** store the failed `current_stage` with a clear `error_message`.

---

## Error Handling

- OCR failed → Retry 2x, then flag for manual processing
- Validation failed → Return specific field errors
- Indexing failed → Retry 2x, log error

---

**References:** `.docs/INGESTION_PIPELINE.md`, `04_MODULE_SPEC.md`, `07_RAG_SPEC.md`

**Next:** [09. Frontend Spec →](09_FRONTEND_SPEC.md)
- **Remove:** _[Headers/footers lặp lại, decorative layout, duplicate noise]_
- **Never:** _[Rewrite legal/procedural meaning, thêm deadlines/fees không có source]_

### Validation
_[Check page markers có đủ không, tables có structure không]_

---

## YAML Metadata Frontmatter

### Required Fields
```yaml
document_id: ""
version_id: ""
title: ""
document_type: ""
domain: ""
department: ""
audience: []
effective_date: ""
```

### Optional Fields
```yaml
code: ""
issued_date: ""
expiry_date: ""
version_label: ""
is_latest: false
replaces: []
replaced_by: []
amends: []
amended_by: []
supplements: []
supplemented_by: []
```

Do not add `priority` or `chunking_strategy` to YAML metadata.

### Status Fields
```yaml
collection_status: "collected"
ocr_status: "done"
review_status: "not_reviewed"
rag_status: "not_indexed"
validity_status: "unchecked"
```

`ocr_status` has no `"not_required"` value. Markdown/text/parser-only sources use `"done"` once parser validation is complete.

---

## Admin Workflow Steps

| Step | Actor | Result |
|------|-------|--------|
| 1. Upload | Admin | Original file stored |
| 2. Create job | Backend | Ingestion job created |
| 3. OCR | ocr-pvl | Markdown output |
| 4. Clean Markdown | Admin/reviewer | Clean Markdown |
| 5. Complete metadata | Admin | YAML frontmatter filled |
| 6. Validate metadata | Backend | Valid/invalid with reasons |
| 7. Human review | Reviewer | approved/rejected/need_fix |
| 8. Chunking | Backend (LangChain) | Parent/child chunks |
| 9. Embedding | Backend (BGE-M3) | Vectors created |
| 10. Indexing | Backend (Qdrant) | Points upserted |
| 11. Publish | Backend | rag_status = "published" |

---

## Ingestion Job Stage Progression

```
uploaded → ocr_running → ocr_done → metadata_pending → metadata_validated
→ review_pending → approved → chunking_done → embedded → indexed → active
```

---

## Indexing Eligibility Rules

### Hard Requirements (ALL must be true)
```
ocr_status = "done"
AND review_status = "approved"
AND validity_status = "valid"
AND confidentiality = "public"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

### Ranking Preference (NOT a hard filter)
_[Prefer is_latest=true khi conflict]_

---

## Publish Transition

### After Successful Indexing
```
rag_status: indexed → published
```

### Student Retrieval Filter
```
rag_status = "published" (plus all hard requirements)
```

---

## Error Handling

### OCR Errors
_[Retry logic, fallback to manual review]_

### Validation Errors
_[Return detailed error messages, block publish]_

### Indexing Errors
_[Log error, retry logic, mark job as failed]_

---

## Retry Strategy

### Transient Failures
_[Network errors, Qdrant connection → auto retry with exponential backoff]_

### Permanent Failures
_[OCR không đọc được, invalid format → require manual intervention]_

---

## Output Folder Structure

### Suggested Paths
```
storage/
├── raw/                  # Original uploaded files
├── ocr_output/           # OCR Markdown output
├── canonical/            # Reviewed canonical Markdown
└── assets/               # Forms, attachments
```

---

## Relationship: ocr/, nlcs/, chatbot/

### ocr/
_[OCR tool code (ocr-pvl)]_

### nlcs/01_Dataset/
_[Canonical reviewed Markdown documents]_

### chatbot/backend/
_[Backend gọi ocr-pvl, process Markdown, index to Qdrant]_

---

**Status:** Skeleton — Cần điền chi tiết workflow và error handling  
**Priority:** P1
