# 08. Đặc Tả Ingestion Pipeline

**Version:** 5.1
**Status:** Final

## Scope

Backend hỗ trợ hai đầu vào cho admin: upload Markdown có sẵn, hoặc upload file nguồn
vào trang OCR riêng. OCR dùng `app/ocr` và chỉ giữ file tạm trong thời gian request;
không ghi PostgreSQL/R2 trước khi admin review Markdown và bấm Lưu.

## Pipeline (backend scope)

```text
1. Nếu chưa có Markdown: admin upload file nguồn tại trang OCR
2. `POST /api/v1/admin/ocr` giữ basename file gốc trong vùng tạm, gọi `app/ocr`, gắn YAML metadata vào đầu Markdown và trả cả Markdown hoàn chỉnh lẫn metadata; chưa persistence
3. Trang OCR tự điền metadata kỹ thuật (`document_key`, `version_key`, checksum), hiển thị link xem nhanh YAML + nội dung OCR và form dùng chung với nhánh upload; admin review/chỉnh Markdown và bổ sung metadata nghiệp vụ tại đây
4. Admin bấm Lưu; `POST /api/v1/admin/canonical-markdown` lưu source + canonical Markdown vào R2 và document/version/job vào PostgreSQL
5. Validate metadata và approve review
6. Preview chunks (read-only), sau đó approve để lưu Parent/Child vào PostgreSQL và đặt `current_step = chunks_approved`
7. Index chỉ dùng bộ chunks đã approve; canonical Markdown thay đổi thì phải preview/approve lại
8. Embed Child chunks với BAAI/bge-m3
9. Upsert Child vectors vào Qdrant
10. Set `rag_status = indexed`; publish là thao tác riêng
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
