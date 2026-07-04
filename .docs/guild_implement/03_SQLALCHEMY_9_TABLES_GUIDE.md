# 03. Hướng Dẫn Implement 9 PostgreSQL Tables Bằng SQLAlchemy + Alembic

**Last Updated:** 2026-07-04

Source of truth cho schema: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`.
File này hướng dẫn tạo đủ 9 table core trong PostgreSQL bằng SQLAlchemy ORM và Alembic
migration, khớp đúng DDL trong spec 05.

## Mục Tiêu

Tạo đủ 9 table (đúng thứ tự spec 05):

```text
1. departments
2. document_types
3. documents
4. document_versions
5. document_chunks
6. ingestion_jobs
7. document_recipients
8. assets
9. document_assets
```

Sau bước này cần đạt được:

```text
SQLAlchemy models import được
Alembic autogenerate được migration
alembic upgrade head tạo đủ 9 table trong schema css
insert smoke test được 1 document/version/chunk/asset/job
```

## Quy Ước Key Và ID

Giữ đúng quy ước:

```text
id           = primary key nội bộ database
*_id         = foreign key nội bộ database
document_key = stable key của document trong YAML/RAG
version_key  = stable key của document version trong YAML/RAG
asset_key    = stable key của asset trong YAML/RAG
```

Ví dụ:

```text
documents.id = 12
documents.document_key = "quy-trinh-cap-bang-diem"

document_versions.id = 33
document_versions.document_id = 12
document_versions.version_key = "quy-trinh-cap-bang-diem-v1"

assets.id = 7
assets.asset_key = "form-xin-cap-bang-diem"
```

Trong DB relationships, dùng `*_id`. Trong YAML/Pydantic/RAG payload, dùng `*_key`.

## Dependencies Cần Thêm

File:

```text
chatbot/backend/requirements.txt
```

Cần có thêm:

```text
SQLAlchemy>=2.0
alembic>=1.13
```

Nếu dùng sync engine để đơn giản lúc đầu, thay `asyncpg` bằng:

```text
psycopg[binary]>=3.1
```

Khuyến nghị backend FastAPI dùng async:

```text
SQLAlchemy async + asyncpg
```

## File/Folder Cần Tạo

Trong:

```text
chatbot/backend/
```

nên có:

```text
alembic.ini
alembic/
  env.py
  versions/
app/databases/
  __init__.py
  base.py
  session.py
  models/
    __init__.py
    documents.py
    assets.py
    chunks.py
    ingestion.py
    recipients.py
```

Tách theo domain ngay từ đầu vì đã chốt làm đủ 9 table. Không tách mỗi table một file ở giai đoạn đầu để tránh import relationship bị rối.

## Bước 1: `app/databases/base.py`

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


metadata = MetaData(schema="css")


class Base(DeclarativeBase):
    metadata = metadata
```

Dùng schema `css` vì note hiện tại đã tạo schema:

```text
CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;
```

## Bước 2: `app/databases/session.py`

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = "postgresql+asyncpg://ct239h:password@localhost:5432/ctu_student_service"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

Tạm thời có thể hardcode để smoke test. Sau đó đổi sang settings/env loader.
## Bước 3: `app/databases/models/` Theo Domain

Phân nhóm:

```text
models/documents.py
- Department
- DocumentType
- Document
- DocumentVersion
- DocumentRecipient

models/assets.py
- Asset
- DocumentAsset

models/chunks.py
- DocumentChunk

models/ingestion.py
- IngestionJob

models/__init__.py
- import/export tất cả model để Alembic thấy metadata
```

### Import Nên Dùng Trong Các File Model

```python
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.databases.base import Base
```

Nên dùng SQLAlchemy 2.x style:

```python
Mapped[str]
mapped_column(...)
```

### `app/databases/models/__init__.py`

File này bắt buộc import tất cả model. Nếu thiếu import, Alembic có thể không thấy table khi autogenerate.

```python
from app.databases.models.assets import Asset, DocumentAsset
from app.databases.models.chunks import DocumentChunk
from app.databases.models.documents import (
    Department,
    Document,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
)
from app.databases.models.ingestion import IngestionJob

__all__ = [
    "Asset",
    "Department",
    "Document",
    "DocumentAsset",
    "DocumentChunk",
    "DocumentRecipient",
    "DocumentType",
    "DocumentVersion",
    "IngestionJob",
]
```

### Relationship Import Lưu Ý

Để tránh circular import, dùng string relationship hoặc `from __future__ import annotations`.

## `models/documents.py`

```text
app/databases/models/documents.py
```

### Model 1: `Department`

Khớp DDL spec 05 (`departments`): chỉ có `id`, `code`, `name`, `description`, `is_active`.

```python
class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    recipients: Mapped[list["DocumentRecipient"]] = relationship(back_populates="department")
```

### Model 2: `DocumentType`

Khớp DDL spec 05 (`document_types`): `id`, `code`, `name`, `is_active`.

```python
class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    documents: Mapped[list["Document"]] = relationship(back_populates="document_type")
```
### Model 3: `Document`

Khớp DDL spec 05 (`documents`): không có `department_id`, không có `created_at/updated_at`.

```python
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(100))
    audience: Mapped[dict | None] = mapped_column(JSONB)
    document_type_id: Mapped[int | None] = mapped_column(ForeignKey("css.document_types.id"))

    document_type: Mapped["DocumentType"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
```

Ghi chú:

```text
Document KHÔNG có department_id trực tiếp.
Quan hệ với departments đi qua bảng document_recipients (theo document_version).
```

### Model 4: `DocumentVersion`

Khớp DDL spec 05 (`document_versions`). Status nằm trực tiếp trong bảng này. Không có
`validity_status` ở version (chỉ `assets` mới có).

```python
class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    issued_date: Mapped[date | None] = mapped_column(Date)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    source_url: Mapped[str | None] = mapped_column(Text)
    source_path: Mapped[str | None] = mapped_column(Text)
    canonical_markdown_path: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10), default="vi", nullable=False)
    issuing_authority: Mapped[str | None] = mapped_column(String(255))
    signer: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(64))
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB)
    accessed_date: Mapped[date | None] = mapped_column(Date)

    # Status fields nằm trực tiếp trong document_versions (không có bảng riêng)
    ocr_status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(50), default="not_reviewed", nullable=False, index=True)
    rag_status: Mapped[str] = mapped_column(String(50), default="not_indexed", nullable=False, index=True)
    status_note: Mapped[str | None] = mapped_column(Text)

    document_id: Mapped[int] = mapped_column(ForeignKey("css.documents.id", ondelete="CASCADE"), nullable=False, index=True)

    document: Mapped["Document"] = relationship(back_populates="versions")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    recipients: Mapped[list["DocumentRecipient"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
```

Publish rule (validate ở service/Pydantic):

```text
Indexing eligibility: ocr_status = done AND review_status = approved
Student filter query:  review_status = approved AND rag_status = published
```
## `models/chunks.py`

```text
app/databases/models/chunks.py
```

### Model 5: `DocumentChunk`

Khớp DDL spec 05 (`document_chunks`): dùng `parent_chunk_id` và `chunk_type`, có
`heading_path`, `section_title`, `page_start/page_end`, `token_count`, `checksum`,
`qdrant_point_id`.

```python
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("css.document_chunks.id"), nullable=True)
    chunk_key: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    section_title: Mapped[str | None] = mapped_column(Text)
    heading_path: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))

    qdrant_point_id: Mapped[str | None] = mapped_column(String(255))
    index_status: Mapped[str] = mapped_column(String(50), default="not_indexed", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), nullable=False, index=True)

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
    parent: Mapped["DocumentChunk | None"] = relationship(remote_side=[id])

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_key", name="uq_document_chunk_key"),
        UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunk_index"),
    )
```

`chunk_type` là `parent` hoặc `child`. Child chunk trỏ về parent qua `parent_chunk_id`.

## `models/ingestion.py`

```text
app/databases/models/ingestion.py
```

### Model 6: `IngestionJob`

Khớp DDL spec 05 (`ingestion_jobs`): dùng `current_step`, không có `tool_name`.

```python
class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(50))
    current_step: Mapped[str | None] = mapped_column(String(100))
    total_chunks: Mapped[int | None] = mapped_column(Integer)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), nullable=False, index=True)

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="ingestion_jobs")
```

Ghi chú:

```text
ingestion_jobs.status là trạng thái chạy job.
ingestion_jobs.current_step lưu bước hiện tại trong pipeline (không dùng current_stage).
Workflow status của document (ocr/review/rag) nằm trực tiếp trong document_versions.
```

## `models/documents.py` (tiếp): `DocumentRecipient`

### Model 7: `DocumentRecipient`

Khớp DDL spec 05 (`document_recipients`): composite PK
`(document_version_id, department_id, effective_date)`, FK về **version**, có
`effective_date`. Không có `id` PK, không có `recipient_type`.

```python
class DocumentRecipient(Base):
    __tablename__ = "document_recipients"

    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("css.departments.id"), primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="recipients")
    department: Mapped["Department"] = relationship(back_populates="recipients")
```

Ghi chú:

```text
effective_date = ngày phòng ban tiếp nhận văn bản.
effective_date nằm trong PK vì cùng một version có thể được gửi lại cho cùng phòng ban
vào ngày khác; nếu PK chỉ (document_version_id, department_id) thì lần gửi thứ hai sẽ
vi phạm khóa chính.
```

## `models/assets.py`

```text
app/databases/models/assets.py
```

### Model 8: `Asset`

Khớp DDL spec 05 (`assets`): chỉ `asset_key`, `title`, `asset_type`, `url`, `checksum`,
`validity_status`, `created_at`. Không có `file_path/file_type/download_url/is_latest/review_status/rag_status`.

```python
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(64))
    validity_status: Mapped[str] = mapped_column(String(50), default="valid", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    document_links: Mapped[list["DocumentAsset"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
```

### Model 9: `DocumentAsset`

Khớp DDL spec 05 (`document_assets`): composite PK
`(document_version_id, asset_id, relation_type)`, có `required_when`, `display_order`.
Không có cột `required` boolean, không có `created_at/updated_at`.

```python
class DocumentAsset(Base):
    __tablename__ = "document_assets"

    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("css.assets.id", ondelete="CASCADE"), primary_key=True)
    relation_type: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    required_when: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document_version: Mapped["DocumentVersion"] = relationship()
    asset: Mapped["Asset"] = relationship(back_populates="document_links")
```

## Bước 4: Alembic Init

Tại:

```text
chatbot/backend
```

Chạy:

```powershell
alembic init alembic
```

Sửa `alembic/env.py` để import metadata:

```python
from app.databases.base import Base
from app.databases import models  # noqa: F401, imports app/databases/models/__init__.py

target_metadata = Base.metadata
```

Sửa database URL trong `alembic.ini` tạm thời:

```ini
sqlalchemy.url = postgresql+asyncpg://ct239h:password@localhost:5432/ctu_student_service
```

Nếu Alembic async setup phức tạp, có thể dùng sync URL trong Alembic:

```ini
sqlalchemy.url = postgresql+psycopg://ct239h:password@localhost:5432/ctu_student_service
```

Nhưng khi đó cần dependency:

```text
psycopg[binary]>=3.1
```

## Bước 5: Tạo Migration

```powershell
alembic revision --autogenerate -m "create core rag tables"
```

Mở file migration và kiểm tra:

```text
schema="css"
9 table được tạo
unique constraint cho document_key/version_key/asset_key
FK dùng css.<table>.id
document_assets có composite PK (document_version_id, asset_id, relation_type)
document_versions có ocr_status/review_status/rag_status/status_note
document_recipients có composite PK (document_version_id, department_id, effective_date)
```

Nếu migration không có `schema="css"`, kiểm tra lại `Base.metadata = MetaData(schema="css")`.

## Bước 6: Chạy Migration

```powershell
alembic upgrade head
```

Kiểm tra bằng:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"
```

Mong đợi:

```text
css.departments
css.document_types
css.documents
css.document_versions
css.document_chunks
css.ingestion_jobs
css.document_recipients
css.assets
css.document_assets
```

## Bước 7: Smoke Insert Test

Sau migration, tạo script/test insert:

```text
tests/test_database_models.py
```

Mục tiêu:

```text
insert Department
insert DocumentType
insert Document
insert DocumentVersion (với ocr_status/review_status/rag_status)
insert DocumentRecipient (document_version_id, department_id, effective_date)
insert Asset
insert DocumentAsset
insert DocumentChunk parent
insert DocumentChunk child (dùng parent_chunk_id)
insert IngestionJob
```

Chưa cần test Qdrant trong bước này.

## Common Mistakes Cần Tránh

- Dùng `document_key` làm FK. Sai. FK trong DB phải là `document_id -> documents.id`.
- Dùng `version_key` làm FK trong `document_chunks`. Sai. Dùng `document_version_id -> document_versions.id`.
- Dùng `asset_key` trong `document_assets` làm FK. Sai. Dùng `asset_id -> assets.id`.
- Đưa `department_id` vào `documents`. Sai. Dùng bảng `document_recipients` theo version.
- Dùng `parent_id` thay vì `parent_chunk_id` trong `document_chunks`. Sai.
- Dùng `chunk_level` thay vì `chunk_type` trong `document_chunks`. Sai.
- Dùng `current_stage` hoặc thêm `tool_name` trong `ingestion_jobs`. Sai, dùng `current_step`.
- Tạo bảng riêng `document_version_status`. Sai, status nằm trực tiếp trong `document_versions`.
- Thêm `validity_status` vào `document_versions`. Sai, chỉ `assets` có `validity_status`.
- Bắt buộc `is_latest = true` để retrieve. Sai, `is_latest` chỉ là ranking preference.
- Quên schema `css` trong Alembic migration.

## Definition Of Done

Hoàn thành bước 03 khi:

```text
requirements có SQLAlchemy/Alembic/Postgres driver
app.databases.models import được và export đủ 9 model
alembic revision autogenerate được
alembic upgrade head thành công
\dt css.* thấy đủ 9 table
smoke insert test pass
```

---

> **Lưu ý:** Xem `19_MIGRATE_10_TO_9_TABLES_GUIDE.md` để migrate từ schema cũ (10 bảng có
> `document_version_status`/`document_version_relationships`) sang schema 9 bảng hiện tại.
> Source of truth cho field/PK/FK: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`.
