# 03. SQLAlchemy Models and Alembic Guide

Contract vật lý duy nhất:

```text
.docs/spec/ctu-service/10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md
```

Executable clean-database DDL:

```text
infrastructure/postgres/bootstrap/001_create_retrieval_schema.sql
```

Guide này chỉ hướng dẫn cách hiện thực contract bằng SQLAlchemy/Alembic; không chép lại danh sách
cột, CHECK constraint hoặc index.

## File ownership

```text
backend/app/databases/base.py
backend/app/databases/session.py
backend/app/databases/models/
backend/alembic/versions/
```

Chín model/table thuộc các nhóm:

- document reference: `Department`, `DocumentType`;
- document lifecycle: `Document`, `DocumentVersion`, `DocumentRecipient`;
- retrieval content: `DocumentChunk`;
- assets: `Asset`, `DocumentAsset`;
- orchestration: `IngestionJob`.

Không tạo status-history table hoặc model song song.

## Mapping rules

- ORM `id/*_id` là persistence-internal.
- `*_key` là stable identity ở YAML/API/RAG boundary.
- `DocumentChunk.parent_chunk_id` là self-FK; DTO dùng `parent_chunk_key` trước khi persist.
- Status nằm trực tiếp trên `DocumentVersion`.
- JSONB/list, nullable, default, length, FK action, unique constraint và index phải match Contract 10.
- Relationship chỉ phục vụ navigation thật; không thêm bidirectional relationship nếu không có caller.

## Implementation order

1. Giữ một `Base` và một session factory hiện có.
2. Map model theo Contract 10, không copy model thành module mới.
3. Import toàn bộ model trong Alembic metadata.
4. Autogenerate migration, sau đó review thủ công constraint/index/SQL type.
5. Chạy upgrade trên database trống.
6. Chạy schema inspection và smoke insert theo Guide 05.

## Provisioning rule

Database trống dùng đúng một đường:

- direct bootstrap SQL; hoặc
- Alembic migration đã được reconcile với Contract 10.

Không chạy cả hai trên cùng database. Database đã có dữ liệu chỉ dùng forward migration; không sửa
migration đã apply và không chạy clean bootstrap đè lên.

## Transaction boundary

Repository có thể `add`, `query`, `flush`; không `commit` hoặc `rollback`. Use-case service sở hữu
transaction. Không giữ transaction trong lúc gọi storage, embedding hoặc Qdrant.

## Validation

```text
alembic upgrade head
alembic current
```

Sau đó xác nhận:

- đúng 9 table trong schema `css`;
- constraint/index quan trọng match Contract 10;
- Parent insert trước Child và self-FK resolve đúng;
- cascade behavior đúng;
- model metadata và database không sinh Alembic diff ngoài dự kiến.

Không tạo thêm repository abstraction chỉ để bọc một query dùng một lần.
