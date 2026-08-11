# Database Sync Rules

Nguồn chuẩn duy nhất cho PostgreSQL, Qdrant payload, lifecycle và retrieval eligibility:

```text
.docs/spec/ctu-service/10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md
```

File này chỉ giữ workflow đồng bộ, không lặp field/table/index.

## Change workflow

1. Thay đổi Contract 10 trước và nêu rõ invariant bị đổi.
2. Cập nhật bootstrap SQL và forward Alembic migration tương ứng.
3. Cập nhật ORM/Pydantic mapper; không ép hai loại model thành một.
4. Cập nhật ingestion/retrieval payload mapper.
5. Chạy schema inspection, smoke insert, Qdrant acceptance và retrieval tests.

## Stable boundary

- YAML/API/RAG dùng `*_key`.
- PostgreSQL relation dùng `*_id`.
- Service/repository chịu trách nhiệm resolve key sang ID.
- PostgreSQL giữ canonical content; Qdrant chỉ giữ Child vector và structural payload.
- Repository không commit; service sở hữu transaction.

## Drift check

Khi contract đổi, tìm toàn repo theo tên field/status/collection cũ. Task chưa hoàn thành nếu ORM,
migration, bootstrap SQL, payload mapper, guide hoặc test vẫn mô tả contract khác.
