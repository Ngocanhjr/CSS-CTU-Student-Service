# 08. Đặc Tả Ingestion Pipeline

**Version:** 4.0
**Status:** Final

## Scope

OCR/LlamaParse chạy **bên ngoài** backend này. Backend nhận canonical Markdown đã được
OCR và review từ trước, sau đó tiến hành phần còn lại của RAG pipeline.

## Pipeline (backend scope)

```text
1. Nhận canonical Markdown + YAML metadata (đã OCR và review bên ngoài)
2. Create ingestion_jobs row
3. Validate metadata
4. Chunk with LangChain / langchain-text-splitters
5. Embed with BAAI/bge-m3
6. Upsert to Qdrant
7. Set rag_status = published
```

## Yêu cầu canonical Markdown đầu vào

Markdown nhận vào phải đã có:

- Heading hierarchy đúng cấu trúc
- Bảng và danh sách được giữ nguyên
- Page markers cho citation: `<!-- page: N -->`
- Không có nội dung bịa đặt
- YAML metadata khớp với `document_versions`

## `ingestion_jobs`

Final fields:

```text
id
job_type
status
current_step
total_chunks
processed_chunks
error_message
started_at
finished_at
created_by
created_at
updated_at
document_version_id
```

Use `current_step`, not `current_stage`.

## Status fields

Status lives on `document_versions`:

```text
ocr_status
review_status
rag_status
status_note
```

Do not use `collection_status` or `version_status_history`.

## Indexing eligibility

All must be true before indexing/publishing:

```text
ocr_status = done
AND review_status = approved
```

After successful indexing:

```text
rag_status = published
```

## Error handling

- Metadata invalid: block indexing until fixed.
- Review rejected: keep `review_status` as rejected or need_fix.
- Qdrant upsert failed: keep job failed and retry from indexing step.

## References

- `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`
- `chatbot/.docs/spec/ctu-service/07_RAG_SPEC.md`
