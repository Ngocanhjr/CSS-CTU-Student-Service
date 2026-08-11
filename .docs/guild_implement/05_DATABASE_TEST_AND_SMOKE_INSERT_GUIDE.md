# 05. PostgreSQL Smoke Test Guide

Physical schema và expected indexes nằm tại Contract 10. Guide này chỉ mô tả test, không lặp DDL:

```text
.docs/spec/ctu-service/10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md
```

## Safety

- Chỉ chạy trên database test riêng.
- Kiểm tra URL/database name trước lệnh cleanup.
- Không drop database dev hoặc production.
- Chọn bootstrap SQL hoặc Alembic; không chạy cả hai.

## Setup

Alembic path:

```text
cd backend
alembic upgrade head
alembic current
```

Direct bootstrap path cho database trống:

```text
psql -v ON_ERROR_STOP=1 -f infrastructure/postgres/bootstrap/001_create_retrieval_schema.sql
```

Điều chỉnh working directory/path theo môi trường; không hard-code credential vào guide hoặc test.

## Schema assertions

Chạy các acceptance query ở Contract 10 và kiểm tra:

- đúng 9 table trong schema `css`;
- FTS index Child tồn tại;
- eligibility/latest indexes tồn tại;
- seed `document_types` có các code canonical.

## Minimal smoke scenario

Trong một transaction test:

1. Insert/reuse `DocumentType` và `Department`.
2. Insert một `Document` với audience student-visible.
3. Insert một approved/published `DocumentVersion`.
4. Insert một Parent `DocumentChunk`, gọi `flush()` lấy ID.
5. Insert một Child trỏ `parent_chunk_id` vừa lấy.
6. Insert một `DocumentRecipient` và `IngestionJob`.
7. Insert một `Asset` cùng `DocumentAsset` relation nếu test asset mapping.
8. Query lại graph và assert key, status, Parent/Child relation.
9. Roll back transaction hoặc xóa theo test key.

Không gọi embedding/Qdrant trong database smoke test. Cross-store flow thuộc E2E test.

## Required failure cases

- duplicate `document_key`, `version_key`, hoặc `(version_id, chunk_key)` bị reject;
- Child thiếu/không đúng Parent bị reject;
- published khi chưa `done/approved` bị reject;
- page range hoặc status ngoài contract bị reject;
- hai latest versions của cùng document bị reject.

## Done

Smoke test đạt khi có thể dựng DB trống, insert/query/rollback scenario trên, và schema inspection
không khác Contract 10.
