# 12. Part E - Hướng Dẫn Implement PostgreSQL Ingestion Repository

**Last Updated:** 2026-07-04

File này tách chi tiết từ guide 07, phần E.

Mục tiêu:

```text
Nhận DocumentMetadata + list[Chunk]
upsert document/version (status fields nằm trực tiếp trong document_versions)
insert parent/child chunks vào PostgreSQL
trả về DB ids để pipeline tiếp tục embed/upsert Qdrant
```

Repository không parse Markdown, không chunk, không embed.

Schema áp dụng: **9 bảng** — departments, document_types, documents, document_versions,
document_chunks, ingestion_jobs, document_recipients, document_assets, assets.

Không có bảng `document_version_status` hay `document_version_relationships`.
Các field `ocr_status`, `review_status`, `rag_status`, `status_note` nằm trực tiếp trong
bảng `document_versions`.

---

## 1. File Cần Tạo

```text
chatbot/backend/app/ingestion/repository.py
chatbot/backend/test/ingestion/test_ingestion_repository.py
```

Phụ thuộc:

```text
app.databases.models
app.schemas.documents.DocumentMetadata
app.schemas.chunks.Chunk
```

---

## 2. Dataclass Kết Quả

Trong `repository.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SavedChunk:
    chunk_key: str
    db_chunk_id: int
    parent_chunk_key: str | None
    db_parent_chunk_id: int | None
    chunk_type: str


@dataclass(frozen=True)
class SavedDocumentVersion:
    document_id: int
    document_version_id: int
    saved_chunks: list[SavedChunk]
```

Ghi nhớ:

```text
chunk_key là stable key do chunker tạo và được lưu vào DocumentChunk.chunk_key.
db_chunk_id là DocumentChunk.id, chỉ dùng làm internal PostgreSQL id/postgres_chunk_id.
```

---

## 3. Public API

Suggested pattern:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chunks import Chunk
from app.schemas.documents import DocumentMetadata


async def save_document_with_chunks(
    session: AsyncSession,
    *,
    metadata: DocumentMetadata,
    chunks: list[Chunk],
) -> SavedDocumentVersion:
    ...
```

Function này nên chạy trong một transaction do caller quản lý:

```python
async with AsyncSessionLocal() as session:
    async with session.begin():
        result = await save_document_with_chunks(session, metadata=metadata, chunks=chunks)
```

---

## 4. Helper Department

DB model:

```text
Department(code, name)
```

Metadata:

```text
department: str
```

Helper:

```python
def normalize_department(value: str) -> tuple[str, str]:
    cleaned = (value or "").strip()
    lowered = cleaned.lower()

    if cleaned.upper() == "CTSV" or "cong tac sinh vien" in lowered:
        return "CTSV", cleaned or "Phòng Công tác Sinh viên"

    if cleaned.upper() == "PDT" or "dao tao" in lowered:
        return "PDT", cleaned or "Phòng Đào tạo"

    if not cleaned:
        return "UNKNOWN", "Unknown"

    code = cleaned.upper().replace(" ", "_")[:20]
    return code, cleaned
```

Upsert:

```python
from sqlalchemy import select

from app.databases.models import Department


async def get_or_create_department(session: AsyncSession, department: str) -> Department:
    code, name = normalize_department(department)
    result = await session.execute(select(Department).where(Department.code == code))
    row = result.scalar_one_or_none()

    if row:
        if row.name != name and name != "Unknown":
            row.name = name
        return row

    row = Department(code=code, name=name)
    session.add(row)
    await session.flush()
    return row
```

---

## 5. Helper Document Type

```python
DOCUMENT_TYPE_NAMES = {
    "noi_quy": "Nội quy",
    "quy_trinh": "Quy trình",
    "bieu_mau": "Biểu mẫu",
    "hoi_dap": "Hỏi đáp",
    "unknown": "Unknown",
}


async def get_or_create_document_type(session: AsyncSession, code: str) -> DocumentType:
    result = await session.execute(select(DocumentType).where(DocumentType.code == code))
    row = result.scalar_one_or_none()
    if row:
        return row

    row = DocumentType(code=code, name=DOCUMENT_TYPE_NAMES.get(code, code))
    session.add(row)
    await session.flush()
    return row
```

---

## 6. Upsert Document

```python
async def upsert_document(
    session: AsyncSession,
    *,
    metadata: DocumentMetadata,
    document_type_id: int,
) -> Document:
    result = await session.execute(
        select(Document).where(Document.document_key == metadata.document_key)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = Document(
            document_key=metadata.document_key,
            title=metadata.title,
            document_type_id=document_type_id,
            domain=metadata.domain,
            audience=metadata.audience,
        )
        session.add(row)
    else:
        row.title = metadata.title or row.title
        row.document_type_id = document_type_id
        row.domain = metadata.domain
        row.audience = metadata.audience

    await session.flush()
    return row
```

Lưu ý:

```text
Không tạo document mới nếu document_key đã tồn tại.
documents KHÔNG có department_id (theo spec 05). Quan hệ phòng ban nằm ở
document_recipients (theo document_version + effective_date) và được gán riêng,
không lấy từ YAML metadata.
```

---

## 7. Upsert Document Version

Status fields (`ocr_status`, `review_status`, `rag_status`, `status_note`) nằm **trực tiếp**
trong bảng `document_versions` — không có bảng `document_version_status` riêng.

Tại bước save chunks, set `rag_status = "chunked"` — không set final `"published"` trước khi
Qdrant xong.

```python
async def upsert_document_version(
    session: AsyncSession,
    *,
    metadata: DocumentMetadata,
    document_id: int,
) -> DocumentVersion:
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.version_key == metadata.version_key)
    )
    row = result.scalar_one_or_none()

    if row and row.document_id != document_id:
        raise ValueError(
            f"version_key {metadata.version_key} already belongs to another document"
        )

    if row is None:
        row = DocumentVersion(
            document_id=document_id,
            version_key=metadata.version_key,
            title=metadata.title,
        )
        session.add(row)

    row.title = metadata.title
    row.code = metadata.code
    row.issued_date = metadata.issued_date
    row.is_latest = metadata.is_latest
    row.source_url = metadata.source_url
    row.source_path = metadata.source_path or ""
    row.file_type = metadata.file_type
    row.canonical_markdown_path = metadata.canonical_markdown_path
    row.language = metadata.language
    row.issuing_authority = metadata.issuing_authority
    row.signer = metadata.signer
    row.accessed_date = metadata.accessed_date
    row.checksum = metadata.checksum

    # Status fields nằm trực tiếp trong document_versions (không có bảng riêng)
    row.ocr_status = metadata.ocr_status
    row.review_status = metadata.review_status
    row.rag_status = "chunked"   # Set chunked tại đây; pipeline sau sẽ nâng lên published
    row.status_note = "Metadata and chunks saved"

    row.extra_metadata = metadata.model_dump(mode="json")

    await session.flush()
    return row
```

Lưu ý:

```text
extra_metadata lưu full metadata để audit.
Nhưng các field quan trọng vẫn có cột riêng.
rag_status được set = "chunked" tại bước này.
Sau khi Qdrant embed xong, pipeline cập nhật rag_status = "published" riêng.
```

---

## 8. Replace Old Chunks

MVP đơn giản:

```text
Delete chunks cũ của document_version trước khi insert chunks mới.
```

Code:

```python
from sqlalchemy import delete


async def delete_existing_chunks(session: AsyncSession, document_version_id: int) -> None:
    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_version_id == document_version_id)
    )
    await session.flush()
```

Cần nhớ:

```text
Nếu chunks cũ đã có Qdrant points, cần delete/deactivate points trước hoặc sau.
Trong MVP test database thì delete thẳng được.
```

---

## 9. Insert Parent/Child Chunks

Phần này quan trọng nhất.

Trước khi insert, cần đảm bảo:

```text
chunk.chunk_key là stable key do chunker tạo.
chunk.chunk_index là global sequential index trong version.
chunk.chunk_type chỉ là "parent" hoặc "child".
Không có 2 chunks cùng chunk_index trong cùng list.
Child chunk.parent_chunk_key phải trỏ tới stable key của parent chunk.
DB lưu parent relation bằng DocumentChunk.parent_chunk_id, không lưu parent_chunk_key làm FK.
```

```python
async def insert_chunks(
    session: AsyncSession,
    *,
    document_version_id: int,
    chunks: list[Chunk],
) -> list[SavedChunk]:
    parent_chunks = [chunk for chunk in chunks if chunk.chunk_type == "parent"]
    child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]

    draft_to_db_id: dict[str, int] = {}
    saved: list[SavedChunk] = []

    for chunk in parent_chunks:
        row = DocumentChunk(
            document_version_id=document_version_id,
            chunk_key=chunk.chunk_key,
            chunk_index=chunk.chunk_index,
            chunk_type="parent",
            heading_path=chunk.heading_path,
            section_title=chunk.heading_path[-1] if chunk.heading_path else "",
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            token_count=chunk.token_count,
            index_status="not_indexed",
        )
        session.add(row)
        await session.flush()

        draft_to_db_id[chunk.chunk_key] = row.id
        saved.append(
            SavedChunk(
                chunk_key=chunk.chunk_key,
                db_chunk_id=row.id,
                parent_chunk_key=None,
                db_parent_chunk_id=None,
                chunk_type="parent",
            )
        )

    for chunk in child_chunks:
        if not chunk.parent_chunk_key:
            raise ValueError(f"Child chunk {chunk.chunk_key} has no parent")

        parent_db_id = draft_to_db_id.get(chunk.parent_chunk_key)
        if parent_db_id is None:
            raise ValueError(
                f"Child chunk {chunk.chunk_key} references unknown parent "
                f"{chunk.parent_chunk_key}"
            )

        row = DocumentChunk(
            document_version_id=document_version_id,
            chunk_key=chunk.chunk_key,
            parent_chunk_id=parent_db_id,   # dùng parent_chunk_id, không phải parent_id
            chunk_index=chunk.chunk_index,
            chunk_type="child",
            heading_path=chunk.heading_path,
            section_title=chunk.heading_path[-1] if chunk.heading_path else "",
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            token_count=chunk.token_count,
            index_status="not_indexed",
        )
        session.add(row)
        await session.flush()

        draft_to_db_id[chunk.chunk_key] = row.id
        saved.append(
            SavedChunk(
                chunk_key=chunk.chunk_key,
                db_chunk_id=row.id,
                parent_chunk_key=chunk.parent_chunk_key,
                db_parent_chunk_id=parent_db_id,
                chunk_type="child",
            )
        )

    return saved
```

---

## 10. Main Save Function

Thứ tự insert đúng theo schema 9 bảng:

1. Upsert document_type
2. Upsert document
3. Upsert document_version (gồm cả status fields — **không có bước upsert status riêng**)
4. Delete old chunks
5. Insert parent chunks trước, child chunks sau

```python
async def save_document_with_chunks(
    session: AsyncSession,
    *,
    metadata: DocumentMetadata,
    chunks: list[Chunk],
) -> SavedDocumentVersion:
    document_type = await get_or_create_document_type(session, metadata.document_type)

    document = await upsert_document(
        session,
        metadata=metadata,
        document_type_id=document_type.id,
    )
    version = await upsert_document_version(
        session,
        metadata=metadata,
        document_id=document.id,
    )
    # Không gọi upsert_document_version_status riêng —
    # status fields đã được set trong upsert_document_version ở trên.
    # document_recipients (phòng ban tiếp nhận) gán riêng theo version + effective_date,
    # không lấy từ YAML metadata.

    await delete_existing_chunks(session, version.id)
    saved_chunks = await insert_chunks(
        session,
        document_version_id=version.id,
        chunks=chunks,
    )

    return SavedDocumentVersion(
        document_id=document.id,
        document_version_id=version.id,
        saved_chunks=saved_chunks,
    )
```

---

## 11. Test Repository

File:

```text
chatbot/backend/test/ingestion/test_ingestion_repository.py
```

Test phải chỉ chạy với DB test như guide 05.

```python
import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import select

from app.databases.models import DocumentChunk
from app.databases.session import AsyncSessionLocal
from app.ingestion.repository import save_document_with_chunks

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    raise RuntimeError("Refusing to run ingestion repository tests outside test DB")

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_save_document_with_chunks(sample_metadata, sample_chunks):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await save_document_with_chunks(
                session,
                metadata=sample_metadata,
                chunks=sample_chunks,
            )

        async with AsyncSessionLocal() as verify_session:
            rows = await verify_session.execute(
                select(DocumentChunk).where(
                    DocumentChunk.document_version_id == result.document_version_id
                )
            )
            chunks = rows.scalars().all()

        assert result.document_version_id > 0
        assert chunks
        assert any(chunk.chunk_type == "parent" for chunk in chunks)
        # Kiểm tra child chunk dùng parent_chunk_id (không phải parent_id)
        assert any(chunk.chunk_type == "child" and chunk.parent_chunk_id for chunk in chunks)
```

Lưu ý:

```text
Cần fixture cleanup test data để tránh unique conflict.
Có thể copy pattern cleanup từ test_database_models.py.
```

---

## 12. Lệnh Test

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_ingestion_repository.py
```

---

## 13. Done Khi

- [ ] Upsert document_type được.
- [ ] Upsert document theo `document_key` (KHÔNG có `department_id`).
- [ ] `document_recipients` gán theo version + effective_date (không lấy từ YAML metadata).
- [ ] Upsert version theo `version_key`.
- [ ] Status fields (`ocr_status`, `review_status`, `rag_status`) được set trực tiếp trong `DocumentVersion`.
- [ ] `rag_status` sau save chunks là `"chunked"`.
- [ ] Parent chunks insert trước.
- [ ] Child chunks có `parent_chunk_id` (không phải `parent_id`).
- [ ] `SavedChunk.db_chunk_id` chính là `DocumentChunk.id`.
- [ ] `SavedChunk.db_parent_chunk_id` chính là `DocumentChunk.parent_chunk_id`.
- [ ] Test repository pass trên DB test.

---

## 14. Lỗi Dễ Gặp

### Lỗi: child references unknown parent

Nguyên nhân:

```text
Chunker tạo parent_chunk_key sai hoặc repository insert child trước parent.
```

Xử lý:

```text
Insert parent chunks trước, tạo map chunk_key -> DB id, sau đó mới insert child.
```

### Lỗi: unique constraint chunk_index

Nguyên nhân:

```text
Ingest lại cùng version nhưng chưa xóa chunks cũ.
Hoặc chunker reset chunk_index riêng cho parent/child làm parent và child cùng index.
```

Xử lý:

```text
delete_existing_chunks trước khi insert chunks mới.
Đảm bảo chunker tạo chunk_index global sequential cho cả parent và child.
```

### Lỗi: AttributeError parent_id không tồn tại

Nguyên nhân:

```text
Code cũ dùng DocumentChunk.parent_id — field này không tồn tại trong schema 9 bảng.
```

Xử lý:

```text
Dùng DocumentChunk.parent_chunk_id (đúng tên cột trong schema).
```

### Lỗi: test ghi vào DB dev

Nguyên nhân:

```text
DATABASE_URL đang trỏ vào ctu_student_service.
```

Xử lý:

```text
Guard DATABASE_URL.endswith("/ctu_student_service_test").
```
