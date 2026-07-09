# 19. Hướng Dẫn Migrate Từ Schema 10 Bảng → 9 Bảng

**Last Updated:** 2026-07-04

File này hướng dẫn sửa toàn bộ code và migration từ schema cũ (10 bảng) sang schema chốt (9 bảng).

---

## Tổng Quan Thay Đổi

### Bảng bị xóa

```text
document_version_status    → xóa hoàn toàn
document_relationships     → xóa hoàn toàn (tên cũ: document_version_relationships)
```

### Bảng thêm mới

```text
document_recipients        → quan hệ M:N giữa document_versions và departments
```

### Thay đổi trong các bảng hiện có

| Bảng | Thay đổi |
| --- | --- |
| `documents` | Xóa `department_id` (quan hệ chuyển sang `document_recipients`) |
| `document_versions` | Thêm `issuing_authority`, `signer_name`, `ocr_status`, `review_status`, `rag_status`, `status_note` trực tiếp vào bảng |
| `assets` | Xóa `validity_status` |
| `document_chunks` | Đổi `parent_id` → `parent_chunk_id`; đổi `chunk_level` → `chunk_type` (đã đúng trong code hiện tại) |
| `ingestion_jobs` | Đổi `current_stage` → `current_step`; xóa `tool_name` |

---

## Bước 1: Sửa SQLAlchemy Models

### 1.1. `app/databases/models/documents.py`

**Xóa** class `DocumentVersionStatus` và class `DocumentRelationship` hoàn toàn.

**Sửa** class `Document` — xóa `department_id` và relationship `department`:

```python
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("css.document_types.id"))
    domain: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    audience: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    document_type: Mapped["DocumentType"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
```

> Xóa `department_id`, `department` relationship, và import `Department` khỏi `Document`. `Department` vẫn giữ nguyên class riêng cho bảng `departments`.

**Sửa** class `DocumentVersion` — thêm status fields, xóa relationship `status`:

```python
class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("css.documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    canonical_markdown_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="md", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="vi", nullable=False)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    accessed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Status fields — nằm trực tiếp trong bảng này, không có bảng riêng
    ocr_status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(50), default="not_reviewed", nullable=False, index=True)
    rag_status: Mapped[str] = mapped_column(String(50), default="not_indexed", nullable=False, index=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="versions")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )
    recipients: Mapped[list["DocumentRecipient"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )
    asset_links: Mapped[list["DocumentAsset"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )
```

`document_versions` không có `effective_date`/`expiry_date` (2 field này chỉ tồn tại trên `document_recipients`, xem class `DocumentRecipient` bên dưới), nên không cần `CheckConstraint` ngày trên bảng này. `checksum` bắt buộc vì dùng để audit nội dung version; model, schema và migration phải cùng `String(64), nullable=False`. `asset_links` là quan hệ ngược với bảng nối `document_assets`, không đặt tên `assets` để tránh nhầm với bảng `assets`.

**Thêm** class `DocumentRecipient` mới vào cuối file:

```python
class DocumentRecipient(Base):
    __tablename__ = "document_recipients"

    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("css.document_versions.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("css.departments.id"), primary_key=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, primary_key=True)

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="recipients")
    department: Mapped["Department"] = relationship(back_populates="recipients")
```

> **Ý nghĩa** `effective_date` **trong PK:** ngày phòng ban tiếp nhận văn bản. Nằm trong PK vì cùng một version có thể được gửi lại cho cùng phòng ban vào ngày khác.

### 1.2. `app/databases/models/assets.py`

**Sửa** class `Asset` — khớp bảng `assets` trong ERD. Bỏ `validity_status`, `file_path`, `file_type`, `download_url`, `updated_at`.

```python
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document_links: Mapped[list["DocumentAsset"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
```

**Sửa** class `DocumentAsset` — PK gồm đủ `document_version_id`, `asset_id`, `relation_type`. Không có `created_at/updated_at`.

```python
class DocumentAsset(Base):
    __tablename__ = "document_assets"

    document_version_id: Mapped[int] = mapped_column(
        ForeignKey("css.document_versions.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("css.assets.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    required_when: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="asset_links")
    asset: Mapped["Asset"] = relationship(back_populates="document_links")
```

> `document_assets` là bảng nối. `DocumentVersion.asset_links` và `Asset.document_links` trỏ tới các dòng nối, không trỏ trực tiếp tới object bên kia.

### 1.3. `app/databases/models/chunks.py`

**Kiểm tra** — code hiện tại đã dùng `chunk_type` đúng. Chỉ cần sửa `parent_id` → `parent_chunk_id`:

```python
parent_chunk_id: Mapped[int | None] = mapped_column(
    ForeignKey("css.document_chunks.id", ondelete="CASCADE"), nullable=True
)
```

Sửa relationship tương ứng:

```python
parent: Mapped["DocumentChunk | None"] = relationship(
    remote_side=[id], foreign_keys=[parent_chunk_id]
)
```

Sửa check constraint:

```python
CheckConstraint(
    "page_start IS NULL OR page_end IS NULL OR page_start <= page_end",
    name="chk_document_chunks_page_range",
),
```

Đổi `page_start`, `page_end`, `token_count` sang nullable:

```python
page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

### 1.3. `app/databases/models/ingestion.py`

Đổi `current_stage` → `current_step`, xóa `tool_name`:

```python
current_step: Mapped[str] = mapped_column(String(100), default="", nullable=False)
```

Xóa dòng:

```python
tool_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
```

### 1.4. `app/databases/models/__init__.py`

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

> Xóa `DocumentVersionStatus`, `DocumentRelationship` khỏi import và `__all__`.

### 1.5. `app/schemas/documents.py`

Sửa schema metadata cùng đợt với DB document model để YAML mới ingest được và để tránh nhầm `DocumentVersionStatus` schema với bảng DB cũ đã xóa.

**Đổi tên** schema status:

```python
class DocumentVersionStatusFields(StrictSchema):
    ocr_status: OcrStatus = "not_started"
    review_status: ReviewStatus = "not_reviewed"
    rag_status: RagStatus = "not_indexed"
    status_note: str = ""


class DocumentVersionMetadata(DocumentVersionStatusFields):
    ...
```

**Bổ sung** field metadata đang dùng trong YAML:

```python
class DocumentBaseMetadata(StrictSchema):
    document_key: str = Field(min_length=1)
    title: str = ""

    responsible_department: list[str] = Field(default_factory=list)
    document_type: DocumentType
    domain: str = ""
    audience: list[str] = Field(default_factory=list)
```

> `responsible_department` chỉ tồn tại trong YAML/schema metadata. DB không có cột này; khi ingest, map từng mã phòng ban sang `document_recipients`.

```python
class DocumentVersionMetadata(DocumentVersionStatusFields):
    ...
    issuing_authority: str | None = None
    signer_name: str | None = None
    checksum: str = Field(min_length=1, max_length=64)
```

> Dùng `signer_name` thống nhất theo DB/YAML. Không dùng `signer`. Không dùng `validity_status` trong DB hoặc YAML metadata. `documents`, `document_versions`, và `assets` đều không có field này. Không dùng `version_label`; bỏ khỏi YAML/schema/DB. `title` chỉ giữ tiêu đề chính thức của văn bản, không gộp nhãn file/OCR batch vào `title`. `checksum` là bắt buộc cho `document_versions`; không dùng `str | None` trong schema/version model.

**Cập nhật import/export và test liên quan:**

- `app/schemas/__init__.py`: export `DocumentVersionStatusFields` thay cho `DocumentVersionStatus`
- `test/schemas/documents_test.py`: import/test `DocumentVersionStatusFields`
- `test/schemas/imports_test.py`: import/test `DocumentVersionStatusFields`

**Cập nhật enum nếu YAML dùng quyết định:**

Trong `app/schemas/enums.py`, thêm `quyet_dinh` vào `DocumentType`.

---

## Bước 2: Tạo Alembic Migration Mới

Database đã có dữ liệu từ migration cũ, **không sửa migration cũ**. Tạo migration mới:

```powershell
cd chatbot/backend
alembic revision -m "migrate_10_to_9_tables"
```

Nội dung migration:

```python
"""migrate_10_to_9_tables

Revision ID: <sẽ được sinh tự động>
Revises: c6ed09e8023d
Create Date: 2026-07-04

Thay đổi:
- Xóa bảng document_version_status
- Xóa bảng document_relationships
- Xóa cột department_id khỏi documents
- Thêm issuing_authority, signer_name, ocr_status, review_status, rag_status, status_note vào document_versions
- Xóa validity_status khỏi assets
- Đổi parent_id → parent_chunk_id trong document_chunks
- Đổi page_start/page_end/token_count sang nullable trong document_chunks
- Đổi current_stage → current_step trong ingestion_jobs
- Xóa tool_name khỏi ingestion_jobs
- Thêm bảng document_recipients
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "<auto-generated>"
down_revision: Union[str, Sequence[str], None] = "c6ed09e8023d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Thêm metadata/status columns vào document_versions
    op.alter_column("document_versions", "checksum",
        type_=sa.String(64), nullable=False, schema="css")

    op.add_column("document_versions",
        sa.Column("issuing_authority", sa.String(255), nullable=True), schema="css")
    op.add_column("document_versions",
        sa.Column("signer_name", sa.String(255), nullable=True), schema="css")
    op.add_column("document_versions",
        sa.Column("ocr_status", sa.String(50), nullable=False,
                  server_default="not_started"), schema="css")
    op.add_column("document_versions",
        sa.Column("review_status", sa.String(50), nullable=False,
                  server_default="not_reviewed"), schema="css")
    op.add_column("document_versions",
        sa.Column("rag_status", sa.String(50), nullable=False,
                  server_default="not_indexed"), schema="css")
    op.add_column("document_versions",
        sa.Column("status_note", sa.Text(), nullable=True), schema="css")

    op.create_index("ix_css_document_versions_ocr_status",
        "document_versions", ["ocr_status"], schema="css")
    op.create_index("ix_css_document_versions_review_status",
        "document_versions", ["review_status"], schema="css")
    op.create_index("ix_css_document_versions_rag_status",
        "document_versions", ["rag_status"], schema="css")

    # 2. Migrate data: copy status từ document_version_status về document_versions
    #    Chạy SAU khi đã thêm cột mới và TRƯỚC khi xóa bảng cũ
    op.execute("""
        UPDATE css.document_versions dv
        SET ocr_status    = dvs.ocr_status,
            review_status = dvs.review_status,
            rag_status    = dvs.rag_status,
            status_note   = dvs.status_note
        FROM css.document_version_status dvs
        WHERE dvs.document_version_id = dv.id
    """)

    # 3. Xóa bảng document_version_status
    op.drop_table("document_version_status", schema="css")

    # 4. Xóa bảng document_relationships
    op.drop_table("document_relationships", schema="css")

    # 5. Xóa validity_status khỏi assets
    op.drop_column("assets", "validity_status", schema="css")

    # 6. Xóa department_id khỏi documents
    op.drop_constraint("documents_department_id_fkey",
        "documents", schema="css", type_="foreignkey")
    op.drop_column("documents", "department_id", schema="css")

    # 7. Thêm bảng document_recipients
    op.create_table(
        "document_recipients",
        sa.Column("document_version_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["css.document_versions.id"],
            ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["css.departments.id"]
        ),
        sa.PrimaryKeyConstraint(
            "document_version_id", "department_id", "effective_date"
        ),
        schema="css",
    )

    # 8. Đổi parent_id → parent_chunk_id trong document_chunks
    op.alter_column("document_chunks", "parent_id",
        new_column_name="parent_chunk_id", schema="css")

    # 9. Đổi page_start/page_end/token_count sang nullable
    op.alter_column("document_chunks", "page_start",
        nullable=True, schema="css")
    op.alter_column("document_chunks", "page_end",
        nullable=True, schema="css")
    op.alter_column("document_chunks", "token_count",
        nullable=True, schema="css")

    # Sửa check constraint page_range (xóa cũ, tạo mới cho phép NULL)
    op.drop_constraint("chk_document_chunks_page_range",
        "document_chunks", schema="css")
    op.create_check_constraint(
        "chk_document_chunks_page_range",
        "document_chunks",
        "page_start IS NULL OR page_end IS NULL OR page_start <= page_end",
        schema="css",
    )

    # 10. Đổi current_stage → current_step trong ingestion_jobs
    op.alter_column("ingestion_jobs", "current_stage",
        new_column_name="current_step", schema="css")

    # 11. Xóa tool_name khỏi ingestion_jobs
    op.drop_column("ingestion_jobs", "tool_name", schema="css")


def downgrade() -> None:
    # Downgrade phức tạp vì mất dữ liệu khi xóa bảng
    # Chỉ thực hiện khi thật sự cần rollback
    raise NotImplementedError(
        "Downgrade từ 9 bảng về 10 bảng không được hỗ trợ tự động. "
        "Restore từ backup nếu cần."
    )
```

---

## Bước 3: Chạy Migration

```powershell
# Kiểm tra trạng thái hiện tại
alembic current

# Chạy migration mới
alembic upgrade head

# Xác nhận kết quả
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"
```

Kết quả mong đợi — đúng 9 bảng:

```text
css.assets
css.departments
css.document_assets
css.document_chunks
css.document_recipients     ← mới
css.document_types
css.document_versions
css.documents
css.ingestion_jobs
```

Không còn:

```text
css.document_version_status    ← đã xóa
css.document_relationships     ← đã xóa
```

---

## Bước 4: Kiểm Tra Sau Migration

```powershell
# Kiểm tra status fields đã có trong document_versions
docker compose exec postgres psql -U ct239h -d ctu_student_service \
  -c "\d css.document_versions"

# Kiểm tra parent_chunk_id trong document_chunks
docker compose exec postgres psql -U ct239h -d ctu_student_service \
  -c "\d css.document_chunks"

# Kiểm tra current_step trong ingestion_jobs
docker compose exec postgres psql -U ct239h -d ctu_student_service \
  -c "\d css.ingestion_jobs"
```

---

## Bước 5: Cập Nhật Code Sử Dụng Models

Tìm và sửa tất cả chỗ trong code dùng các model/field đã thay đổi:

```powershell
# Tìm chỗ dùng DocumentVersionStatus
grep -r "DocumentVersionStatus" chatbot/backend/app --include="*.py"
or
Get-ChildItem chatbot/backend/app -Recurse -Filter *.py | Select-String -Pattern "DocumentVersionStatus"

# Tìm chỗ dùng DocumentRelationship
grep -r "DocumentRelationship" chatbot/backend/app --include="*.py"

# Tìm chỗ dùng .status (relationship cũ)
grep -r "\.status\." chatbot/backend/app --include="*.py"

# Tìm chỗ dùng current_stage
grep -r "current_stage" chatbot/backend/app --include="*.py"

# Tìm chỗ dùng tool_name trong ingestion
grep -r "tool_name" chatbot/backend/app --include="*.py"

# Tìm chỗ dùng parent_id trong chunks
grep -r "parent_id" chatbot/backend/app --include="*.py"
```

### Thay thế trong service/repository code:

| Cũ | Mới |
| --- | --- |
| `version.status.rag_status` | `version.rag_status` |
| `version.status.review_status` | `version.review_status` |
| `version.status.ocr_status` | `version.ocr_status` |
| `DocumentVersionStatus(...)` | Cập nhật trực tiếp `DocumentVersion` |
| `job.current_stage` | `job.current_step` |
| `chunk.parent_id` | `chunk.parent_chunk_id` |
| `department_id` trong `Document` | `document_recipients` |

---

## Bước 6: Cập Nhật Ingestion Repository

Luồng insert cũ (10 bảng):

```python
# Cũ — sai
session.add(DocumentVersion(...))
session.flush()
session.add(DocumentVersionStatus(
    document_version_id=version.id,
    ocr_status="done",
    review_status="approved",
    rag_status="not_indexed",
))
```

Luồng insert mới (9 bảng):

```python
# Mới — đúng
session.add(DocumentVersion(
    ...,
    ocr_status="done",
    review_status="approved",
    rag_status="not_indexed",
    status_note=None,
))
```

Thêm `document_recipients` khi cần:

```python
# Thêm phòng ban tiếp nhận
session.add(DocumentRecipient(
    document_version_id=version.id,
    department_id=dept.id,
    effective_date=date.today(),
))
```

---

## Bước 7: Cập Nhật Retrieval Filter

Cũ (join sang document_version_status):

```python
# Sai — bảng không còn tồn tại
query = query.join(DocumentVersionStatus).filter(
    DocumentVersionStatus.review_status == "approved",
    DocumentVersionStatus.rag_status == "published",
)
```

Mới (filter trực tiếp trên document_versions):

```python
# Đúng
query = query.filter(
    DocumentVersion.review_status == "approved",
    DocumentVersion.rag_status == "published",
)
```

---

## Bước 8: Chạy Test

```powershell
cd chatbot/backend
python -m pytest test/ -v
```

Test quan trọng cần pass:

- Model import không lỗi
- Insert document/version/chunks không lỗi
- Filter `review_status=approved AND rag_status=published` hoạt động
- `parent_chunk_id` self-FK đúng

---

## Checklist Hoàn Thành

- [x] `documents.py`: xóa `DocumentVersionStatus`, `DocumentRelationship`

- [x] `documents.py`: xóa `department_id` khỏi `Document`

- [x] `documents.py`: thêm status fields vào `DocumentVersion`

- [x] `documents.py`: thêm class `DocumentRecipient`

- [x] `assets.py`: xóa `validity_status`

- [x] `schemas/documents.py`: đổi schema `DocumentVersionStatus` → `DocumentVersionStatusFields`

- [x] `schemas/documents.py`: thêm `responsible_department`, `issuing_authority`, `signer_name`

- [x] `schemas/documents.py`: xóa `version_label`; không gộp nhãn version vào `title`

- [x] `schemas/enums.py`: thêm `quyet_dinh` vào `DocumentType` nếu YAML dùng loại này

- [x] `chunks.py`: đổi `parent_id` → `parent_chunk_id`

- [x] `chunks.py`: `page_start`, `page_end`, `token_count` nullable

- [x] `ingestion.py`: đổi `current_stage` → `current_step`, xóa `tool_name`

- [x] `__init__.py`: cập nhật imports

- [x] Migration mới tạo và chạy thành công

- [x] `\dt css.*` đúng 9 bảng

- [x] Không còn `document_version_status` hay `document_relationships` trong DB

- [ ] Code service/repository không còn dùng model cũ

- [ ] Test pass