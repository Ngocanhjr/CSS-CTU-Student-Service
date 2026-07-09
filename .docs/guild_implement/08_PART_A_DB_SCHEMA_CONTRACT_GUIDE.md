# 08. Part A - Hướng Dẫn Chốt Contract DB/Schema Trước Khi Ingest

**Last Updated:** 2026-06-20

File này tách chi tiết từ `07_DETAILED_RAG_INGESTION_IMPLEMENTATION_GUIDE.md`, phần A.

Mục tiêu của part A là chốt lại contract giữa:

```text
Pydantic schema Chunk
SQLAlchemy model DocumentChunk
Alembic migration
Qdrant payload
```

Quyết định sau khi review:

```text
Schema/API/chunker dung chunk_key va parent_chunk_key.
Database luu chunk_key trong document_chunks.
Database dung parent_chunk_id lam self-FK noi bo toi document_chunks.id.
```

Source of truth cho schema DB: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`.

---

## 1. Kết Luận Thiết Kế

### 1.1. ID nào dùng ở đâu

Dùng thống nhất:

```text
Chunk.chunk_key          = stable key trong schema/API/preview/Qdrant
Chunk.parent_chunk_key   = stable parent key trong schema/API/preview/Qdrant
DocumentChunk.id             = internal PostgreSQL primary key
DocumentChunk.chunk_key      = stable key luu trong DB
DocumentChunk.parent_chunk_id = internal FK resolved from parent_chunk_key
qdrant_point_id              = ID point trong Qdrant
```

Lý do:

```text
PostgreSQL la source of truth.
document_chunks.id la primary key noi bo.
chunk_key la dinh danh on dinh de idempotent ingest, upsert vector, va trace qua moi truong DB.
```

### 1.2. Trade-off

Lưu `document_chunks.chunk_key` có lợi:

```text
idempotent re-ingest
payload Qdrant on dinh theo version_key + chunk_key
khong phu thuoc vao sequence id cua PostgreSQL
```

Nhưng có điểm cần nhớ:

```text
can migration them cot chunk_key
repository phai validate parent_chunk_key ton tai trong cung document_version_id
van can postgres_chunk_id trong payload de hydrate nhanh tu DB
```

Vì vậy pipeline phải có 2 giai đoạn:

```text
1. Chunker tao Chunk voi stable chunk_key.
2. Repository insert/upsert parent chunks theo chunk_key.
3. Repository map parent_chunk_key -> parent_chunk_id va insert/upsert child chunks.
```

---

## 2. File Cần Sửa/Kiểm Tra

```text
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/databases/models/chunks.py
chatbot/backend/app/databases/models/documents.py
chatbot/backend/alembic/versions/42bc821c519a_create_core_rag_tables.py
chatbot/backend/test/schemas/chunks_test.py
chatbot/backend/test/databases/test_database_models.py
```

Nếu sửa model, cần tạo migration mới hoặc sửa migration đầu tiên nếu database chưa chốt.

---

## 3. Sửa `schemas/chunks.py`

File:

```text
chatbot/backend/app/schemas/chunks.py
```

Hiện tại field nullable đang khai báo kiểu `int` nhưng default `None`.

Nên sửa thành:

```python
class Chunk(StrictSchema):
    document_key: str = Field(min_length=1)
    version_key: str = Field(min_length=1)

    chunk_key: str = Field(min_length=1)
    parent_chunk_key: str | None = None
    chunk_type: ChunkType

    content: str = Field(min_length=1)
    heading_path: list[str] = Field(default_factory=list)

    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    chunk_index: int = Field(ge=0)
    token_count: int | None = Field(default=None, ge=0)

    metadata: dict[str, Any] = Field(default_factory=dict)
```

Lý do:

```text
Field(default=None) phai di voi type int | None.
Neu khong, code van co the chay nhung contract khong ro.
```

Không đổi validator parent-child:

```python
if self.chunk_type == "parent" and self.parent_chunk_key is not None:
    raise ValueError("parent chunk must not have parent_chunk_key")

if self.chunk_type == "child" and not self.parent_chunk_key:
    raise ValueError("child chunk requires parent_chunk_key")
```

---

## 4. Sửa `models/chunks.py`

File:

```text
chatbot/backend/app/databases/models/chunks.py
```

Bắt buộc thêm cột `chunk_key`.

Cần sửa nullable cho các field có thể không có page/token:

```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("css.document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_key: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("css.document_chunks.id"),
        nullable=True,
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text)
    section_title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64))

    qdrant_point_id: Mapped[str | None] = mapped_column(String(255))
    index_status: Mapped[str] = mapped_column(
        String(50),
        default="not_indexed",
        nullable=False,
        index=True,
    )
```

Giữ constraints:

```python
__table_args__ = (
    UniqueConstraint("document_version_id", "chunk_key", name="uq_document_chunk_key"),
    UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunk_index"),
)
```

Lưu ý:

```text
Spec 05 dung ca UNIQUE(document_version_id, chunk_key) va UNIQUE(document_version_id, chunk_index).
chunk_key stable giup idempotent re-ingest.
chunk_type nhan gia tri 'parent' hoac 'child'.
```

---

## 5. Sửa `models/documents.py`

File:

```text
chatbot/backend/app/databases/models/documents.py
```

Kiểm tra các field ngày (theo spec 05, document_versions chỉ có issued_date và accessed_date;
không có effective_date/expiry_date):

```python
issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
accessed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
```

Lý do:

```text
Pydantic DocumentVersionMetadata cho phep None.
Nhieu tai lieu hanh chinh khong co issued_date/accessed_date ro rang.
```

Kiểm tra `updated_at`.

Nếu model cần insert smoke test mà không truyền `updated_at`, nên có server_default:

```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
)
```

Áp dụng cho các table có `updated_at`.

---

## 6. Sửa Alembic Migration

File:

```text
chatbot/backend/alembic/versions/42bc821c519a_create_core_rag_tables.py
```

Nếu database chưa có data quan trọng, có thể sửa migration đầu tiên cho nhanh.

Cần kiểm tra:

```python
sa.Column('issued_date', sa.Date(), nullable=True)
sa.Column('accessed_date', sa.Date(), nullable=True)
sa.Column('page_start', sa.Integer(), nullable=True)
sa.Column('page_end', sa.Integer(), nullable=True)
sa.Column('token_count', sa.Integer(), nullable=True)
```

Và các cột `updated_at` nên có:

```python
server_default=sa.text('now()')
```

Nếu database đã chạy migration và có data, không sửa migration cũ. Tạo migration mới:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\alembic.exe revision -m "relax nullable chunk fields"
```

Trong migration mới dùng:

```python
op.alter_column("document_chunks", "page_start", nullable=True, schema="css")
op.alter_column("document_chunks", "page_end", nullable=True, schema="css")
op.alter_column("document_chunks", "token_count", nullable=True, schema="css")
op.alter_column("document_versions", "issued_date", nullable=True, schema="css")
op.alter_column("document_versions", "accessed_date", nullable=True, schema="css")
```

---

## 7. Repository Mapping Sau Khi Insert DB

Trong ingestion repository, khi insert chunks:

```python
draft_to_db_id: dict[str, int] = {}

for chunk in parent_chunks:
    row = DocumentChunk(
        document_version_id=version_id,
        chunk_key=chunk.chunk_key,
        chunk_index=chunk.chunk_index,
        chunk_type="parent",
        heading_path=" > ".join(chunk.heading_path) if chunk.heading_path else None,
        section_title=chunk.heading_path[-1] if chunk.heading_path else None,
        content=chunk.content,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        token_count=chunk.token_count,
        index_status="not_indexed",
    )
    session.add(row)
    await session.flush()
    draft_to_db_id[chunk.chunk_key] = row.id
```

Sau đó insert child:

```python
for chunk in child_chunks:
    parent_chunk_id = draft_to_db_id[chunk.parent_chunk_key]
    row = DocumentChunk(
        document_version_id=version_id,
        parent_chunk_id=parent_chunk_id,
        chunk_key=chunk.chunk_key,
        chunk_index=chunk.chunk_index,
        chunk_type="child",
        heading_path=" > ".join(chunk.heading_path) if chunk.heading_path else None,
        section_title=chunk.heading_path[-1] if chunk.heading_path else None,
        content=chunk.content,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        token_count=chunk.token_count,
        index_status="not_indexed",
    )
    session.add(row)
    await session.flush()
    draft_to_db_id[chunk.chunk_key] = row.id
```

Sau khi insert:

```text
stable key: row.chunk_key
internal DB id: row.id
```

Qdrant payload dùng:

```json
{
  "chunk_key": "doc-v1::c::0001",
  "parent_chunk_key": "doc-v1::p::0001",
  "postgres_chunk_id": 123
}
```

Không dùng PostgreSQL id làm `chunk_key` trong payload student-facing.

---

## 8. Test Cần Sửa/Thêm

### 8.1. Schema test

File:

```text
chatbot/backend/test/schemas/chunks_test.py
```

Thêm test:

```python
def test_chunk_accepts_unknown_page_and_token_count():
    chunk = Chunk(
        document_key="doc-001",
        version_key="doc-001-v1",
        chunk_key="p-001",
        chunk_type="parent",
        content="Noi dung",
        chunk_index=0,
    )

    assert chunk.page_start is None
    assert chunk.page_end is None
    assert chunk.token_count is None
```

### 8.2. Database smoke test

File:

```text
chatbot/backend/test/databases/test_database_models.py
```

Thêm hoặc sửa một child chunk cho phép null:

```python
child_chunk_without_page = DocumentChunk(
    document_version_id=version.id,
    parent_chunk_id=parent_chunk.id,
    chunk_key="doc-v1::c::0002",
    chunk_index=2,
    chunk_type="child",
    heading_path="Root > No page",
    section_title="No page",
    content="Child without page marker",
    page_start=None,
    page_end=None,
    token_count=None,
    index_status="not_indexed",
)
```

---

## 9. Lệnh Kiểm Tra

Chạy schema tests:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/schemas
```

Chạy DB test với database test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/databases
```

---

## 10. Done Khi

- [ ] `Chunk.page_start`, `Chunk.page_end`, `Chunk.token_count` dùng type `int | None`.
- [ ] `DocumentChunk.page_start`, `page_end`, `token_count` nullable trong model và migration.
- [ ] `DocumentVersion.issued_date`, `accessed_date` nullable nếu schema cho phép.
- [ ] Thêm cột stable `chunk_key` trong DB và unique `(document_version_id, chunk_key)`.
- [ ] `DocumentChunk` dùng `chunk_type` và `parent_chunk_id` (không dùng chunk_level/parent_id).
- [ ] Repository có mapping parent_chunk_key -> parent_chunk_id.
- [ ] Qdrant payload dùng stable `chunk_key` và `postgres_chunk_id` riêng.
- [ ] Test schema và DB smoke test pass.

---

## 11. Lỗi Dễ Gặp

### Lỗi: `page_start` null nhưng DB báo not-null

Nguyên nhân:

```text
Migration van nullable=False.
```

Xử lý:

```text
Sua migration hoac tao migration moi alter column nullable.
```

### Lỗi: không map được child sang parent

Nguyên nhân:

```text
Chunker tao parent_chunk_key khong khop voi chunk_key cua parent draft.
```

Xử lý:

```text
In ra draft_to_db_id va danh sach child parent_chunk_key trong preview.
```

### Lỗi: Qdrant payload dùng draft id

Nguyên nhân:

```text
Upsert Qdrant truoc khi insert DB.
```

Xử lý:

```text
Luon insert PostgreSQL truoc, lay DocumentChunk.id, roi moi embed/upsert.
```
