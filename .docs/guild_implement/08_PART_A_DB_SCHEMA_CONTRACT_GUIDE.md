# 08. PostgreSQL Ingestion Mapping Guide

Không định nghĩa schema trong file này. Dùng duy nhất:

```text
.docs/spec/ctu-service/10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md
```

Mục tiêu của Guide 08 là map DTO ingestion vào contract đó.

## Boundary mapping

```text
YAML/API stable key       PostgreSQL persistence
document_key          -> documents.document_key
version_key           -> document_versions.version_key
chunk_key             -> document_chunks.chunk_key
parent_chunk_key      -> resolve document_chunks.parent_chunk_id
responsible_department -> departments.code + document_recipients
effective_date input  -> document_recipients.effective_date
```

Không truyền ORM model ra API. Service trả public result DTO chứa các key/status cần thiết.

## Persist order

Trong short transaction đầu:

1. Resolve/upsert reference rows.
2. Upsert `Document` và `DocumentVersion`.
3. Replace recipients theo version nếu use case yêu cầu.
4. Insert Parent chunks và `flush()`.
5. Map `parent_chunk_key -> parent.id` trong memory.
6. Insert Child chunks với resolved `parent_chunk_id`.
7. Tạo/cập nhật `IngestionJob`.
8. Commit ở service.

Embedding và Qdrant chạy sau commit. Transaction ngắn tiếp theo ghi deterministic point IDs và
index status. Chi tiết lifecycle nằm tại Contract 10.

## Idempotency

- `document_key`, `version_key`, và chunk key trong version là natural lookup keys.
- Same version/chunk input không tạo duplicate rows.
- Re-index dùng cùng deterministic Qdrant point ID.
- Không xóa version cũ khi ingest version mới; lifecycle service đổi latest/status rõ ràng.

## Error handling

- Validation error xảy ra trước transaction.
- DB error rollback transaction hiện tại.
- External failure được ghi trong transaction mới; không rollback canonical rows đã commit.
- Không xóa/ghi đè canonical file đã tồn tại trong cleanup.

## Tests

- mapper dùng stable keys, không yêu cầu DB ID từ API;
- Parent map chỉ trong cùng version;
- recipient mapping dùng department code và effective date;
- retry không tăng row/point count;
- service trả DTO, không trả ORM object;
- repository không commit.

Guide 03 hướng dẫn ORM/migration; Guide 05 hướng dẫn DB smoke test; Guide 12 hướng dẫn repository
ingestion cụ thể.
