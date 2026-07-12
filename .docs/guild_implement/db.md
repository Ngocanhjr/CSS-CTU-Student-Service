# Database and Schema Sync Rules

Tài liệu này quy định cách đồng bộ giữa:

- Pydantic schemas: `chatbot/backend/app/schemas`
- SQLAlchemy database models: `chatbot/backend/app/databases/models`
- Alembic migrations: `chatbot/backend/alembic/versions`

Mục tiêu là giữ API/ingestion dùng stable key để dễ trace, còn database dùng primary key và foreign key nội bộ để bảo toàn toàn vẹn dữ liệu.

## 1. Nguyên tắc chính

Schema không nên phụ thuộc vào database id sinh tự động.

- Schema/input/output dùng stable business keys: `document_key`, `version_key`, `asset_key`, `chunk_key`, `parent_chunk_key`.
- Database dùng `id` làm primary key nội bộ.
- Database dùng các cột FK nội bộ như `document_id`, `document_version_id`, `asset_id`, `parent_chunk_id`.
- Service/repository layer chịu trách nhiệm resolve stable key sang database id khi ghi DB.

Không đưa `id` nội bộ vào metadata ingestion nếu không cần thiết. Metadata nên ưu tiên key ổn định để có thể trace, re-ingest, upsert, và debug qua nhiều môi trường DB.

## 2. Quy ước đặt tên

Dùng `_key` cho định danh ổn định ngoài DB:

```text
document_key
version_key
asset_key
chunk_key
parent_chunk_key
```

Dùng `_id` cho khóa nội bộ trong DB:

```text
id
document_id
document_version_id
asset_id
parent_chunk_id
```

Nếu một trường là FK tới bảng khác trong SQLAlchemy model, tên nên là `_id`. Nếu một trường xuất hiện trong schema ingestion/API và được tạo trước khi insert DB, tên nên là `_key`.

## 3. Rule đồng bộ schema và DB

Mỗi entity có stable key phải có constraint duy nhất trong DB:

| Entity | Schema key | DB internal id | DB unique rule |
| --- | --- | --- | --- |
| Document | `document_key` | `documents.id` | `documents.document_key` unique |
| Document version | `version_key` | `document_versions.id` | `document_versions.version_key` unique |
| Asset | `asset_key` | `assets.id` | `assets.asset_key` unique |
| Chunk | `chunk_key` | `document_chunks.id` | unique theo version |

Mỗi schema field bắt buộc phải có cột tương ứng trong DB, trừ các field chỉ dùng để resolve quan hệ.

Ngoai le MVP: `Chunk.metadata` la derived structural payload cho Qdrant, khong persist vao
`document_chunks`. Payload nay duoc regenerate tu canonical Markdown khi recreate Qdrant.

Ví dụ:

- `document_key` trong schema dùng để tìm `documents.id`.
- `version_key` trong schema dùng để tìm `document_versions.id`.
- `parent_chunk_key` trong schema dùng để tìm parent `document_chunks.id`.
- Các field resolve-only này có thể không lưu trực tiếp trong bảng con nếu FK nội bộ đã đủ để join ngược.

## 4. Document rules

Schema document dùng `document_key` làm định danh nghiệp vụ ổn định.

Database:

- `documents.id` là primary key.
- `documents.document_key` là unique, indexed, nullable false.
- Các bảng con không cần lặp lại `document_key` nếu đã join được qua `document_versions.document_id`.

Khi ingest:

1. Nhận `document_key` từ metadata/schema.
2. Upsert hoặc tìm `documents` bằng `document_key`.
3. Dùng `documents.id` cho các FK nội bộ.

## 5. Document version rules

Schema version dùng `version_key` để đại diện cho một phiên bản tài liệu.

Database:

- `document_versions.id` là primary key.
- `document_versions.document_id` FK tới `documents.id`.
- `document_versions.version_key` unique, indexed, nullable false.

Khi ingest:

1. Resolve `document_key` thành `document_id`.
2. Upsert hoặc tìm `document_versions` bằng `version_key`.
3. Đảm bảo `version_key` thuộc đúng `document_id`.

Không gán chunk trực tiếp vào `document_key` nếu không có `version_key`, vì chunk phụ thuộc vào nội dung của từng version.

## 6. Asset rules

Schema asset dùng `asset_key`.

Database:

- `assets.id` là primary key.
- `assets.asset_key` unique, indexed, nullable false.
- Bảng liên kết `document_assets` dùng `document_version_id` và `asset_id`.

Khi ingest relation asset:

1. Resolve `document_key` và `version_key` thành `document_version_id`.
2. Resolve `asset_key` thành `asset_id`.
3. Ghi relation bằng FK nội bộ.

Nếu schema relation chỉ có `document_key` mà không có `version_key`, cần có rule rõ ràng để chọn version, vì asset relation trong DB đang gắn vào document version.

## 7. Chunk rules

Chunk parent và child đều là record trong cùng bảng `document_chunks`.

Database dùng self-FK:

```text
document_chunks.id
document_chunks.parent_chunk_id -> document_chunks.id
```

Schema không nên dùng `parent_chunk_id`, vì client/chunker chưa biết DB id. Schema nên dùng:

```text
chunk_key: str
parent_chunk_key: str | None
chunk_type: parent | child
```

Rule bắt buộc:

- Parent chunk: `parent_chunk_key` phải null.
- Child chunk: `parent_chunk_key` phải có giá trị.
- Parent và child cùng nằm trong `document_chunks`.
- `parent_chunk_id` trong DB phải trỏ tới một chunk cùng `document_version_id`.
- `chunk_key` phải ổn định trong phạm vi một `document_version`.

Nên có cột DB:

```text
document_chunks.chunk_key
```

Và constraint:

```text
UNIQUE(document_version_id, chunk_key)
```

Không nên chỉ dựa vào `chunk_index`, vì `chunk_index` tốt cho thứ tự, nhưng không phải định danh ổn định để resolve parent-child hay sync với vector store.

## 8. Chunk insert flow

Flow khuyến nghị khi ghi chunks:

1. Validate schema `Chunk`.
2. Resolve `version_key` thành `document_version_id`.
3. Insert hoặc upsert tất cả parent chunks trước, theo `chunk_key`.
4. Tạo map `{chunk_key: id}` cho parent chunks trong cùng `document_version_id`.
5. Insert child chunks, resolve `parent_chunk_key` thành `parent_chunk_id`.
6. Lưu `chunk_key` trong DB để hỗ trợ re-ingest, upsert, audit, và Qdrant payload.

Nếu child chunk tham chiếu parent không tồn tại, ingestion phải fail sớm thay vì tạo record mồ côi.

## 9. Qdrant/vector payload rule

Vector payload nên dùng stable keys:

```text
document_key
version_key
chunk_key
parent_chunk_key
chunk_type
page_start
page_end
heading_path
```

Có thể thêm DB id cho debug nội bộ, nhưng không được xem DB id là định danh chính của vector payload.

`qdrant_point_id` nên có tính ổn định, ví dụ sinh từ `version_key + chunk_key`, để upsert không tạo duplicate vectors.

## 10. Alembic migration rule

Mọi thay đổi SQLAlchemy model liên quan đến cột, FK, index, constraint phải có Alembic migration tương ứng.

Checklist khi thêm/sửa field:

- Cập nhật Pydantic schema nếu field đi qua API/ingestion.
- Cập nhật SQLAlchemy model nếu field cần lưu DB.
- Cập nhật Alembic migration.
- Cập nhật tests schema validation.
- Cập nhật tests database model/constraint nếu field ảnh hưởng FK, unique, hoặc check constraint.

Không chỉ sửa model mà bỏ qua migration.

## 11. Contract hiện tại cần cảnh giác

Tại thời điểm viết rule này, cần đặc biệt đồng bộ các điểm sau:

- `schemas/chunks.py` đang dùng `chunk_key` và `parent_chunk_key`.
- `databases/models/chunks.py` đang dùng `parent_chunk_id` self-FK, đúng hướng.
- `databases/models/chunks.py` nên bổ sung `chunk_key` và unique `(document_version_id, chunk_key)`.
- Tests cũ có thể còn dùng `chunk_key` hoặc `parent_chunk_key`; nên đổi sang `chunk_key` và `parent_chunk_key` ở schema layer.
- `DocumentAssetRelation` nên có `version_key` nếu relation trong DB tiếp tục gắn vào `document_version_id`.

## 12. Quyết định thiết kế

Thiết kế được chấp nhận:

```text
Schema boundary:
document_key, version_key, chunk_key, parent_chunk_key

Database boundary:
documents.id
document_versions.id
document_chunks.id
document_chunks.parent_chunk_id
```

Kết luận:

- Parent hay child đều là chunk, nên lưu chung bảng `document_chunks`.
- `parent_chunk_id` là FK nội bộ dùng để bảo toàn quan hệ trong DB.
- `parent_chunk_key` là contract dùng ở schema/API/ingestion.
- Cần lưu `chunk_key` trong DB để resolve, upsert, và trace ổn định.
