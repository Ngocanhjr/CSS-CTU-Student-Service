# 05. Hướng Dẫn Tạo DB Test Và Smoke Test SQLAlchemy Models

**Last Updated:** 2026-06-19

File này nối tiếp sau `04_ALEMBIC_MIGRATION_GUIDE.md`.

Sau khi `alembic upgrade head` thành công, bước tiếp theo là xác nhận SQLAlchemy models có thể insert/query dữ liệu thật vào PostgreSQL. Nên làm việc này trên database test riêng để không làm bẩn database dev.

## Mục Tiêu

Sau guide này cần đạt được:

```text
co database test rieng: ctu_student_service_test
database test co schema css
database test da chay alembic upgrade head
pytest co the insert du lieu qua SQLAlchemy models
test khong lam ban database dev ctu_student_service
```

## Vì Sao Cần DB Test Riêng

Database dev hiện tại:

```text
ctu_student_service
```

nên dùng cho app chạy thử, debug API, và dữ liệu đang phát triển.

Database test riêng:

```text
ctu_student_service_test
```

chỉ dùng cho automated test.

Lý do:

```text
test co the insert/update/delete thoai mai
khong lam ban du lieu dev
khong bi loi trung unique key do test cu de lai
co the drop/recreate khi can
co the chay CI/local test an toan hon
```

## Nguyên Tắc

Không để test ghi trực tiếp vào DB dev:

```text
postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service
```

Test phải dùng DB test:

```text
postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test
```

Trong PowerShell, override `DATABASE_URL` trước khi chạy migration/test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Ghi chú:

```text
load_dotenv() mac dinh khong override env var da co san.
Vi vay bien $env:DATABASE_URL trong PowerShell se uu tien hon gia tri trong .env.
```

Không chạy test file trực tiếp bằng:

```powershell
python test/databases/test_database_models.py
```

Lệnh đó sẽ đặt import root thành `test/databases`, nên Python có thể không thấy package `app`.

Hãy chạy bằng pytest từ thư mục `chatbot/backend`, vì repo đã có `pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = test
```

## Bước 1: Tạo Database Test

Chạy tại:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
```

Tạo DB test:

```powershell
docker compose exec postgres createdb -U ct239h ctu_student_service_test
```

Nếu báo database đã tồn tại thì không sao. Có thể kiểm tra danh sách DB:

```powershell
docker compose exec postgres psql -U ct239h -d postgres -c "\l"
```

## Bước 2: Tạo Schema `css` Trong DB Test

Chạy:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
```

Kiểm tra:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dn"
```

Mong đợi thấy:

```text
css
```

## Bước 3: Chạy Migration Vào DB Test

Chạy tại:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
```

Set `DATABASE_URL` sang DB test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Chạy migration:

```powershell
..\..\.venv\Scripts\alembic.exe upgrade head
```

Kiểm tra revision:

```powershell
..\..\.venv\Scripts\alembic.exe current
```

Mong đợi thấy revision mới nhất, ví dụ:

```text
42bc821c519a
```

Kiểm tra bảng:

```powershell
cd ..
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dt css.*"
```

## Bước 4: Chuẩn Bị Test File

File nên tạo:

```text
chatbot/backend/test/databases/test_database_models.py
```

Mục tiêu của test:

```text
insert Department
insert DocumentType
insert Document
insert DocumentVersion (status fields nam truc tiep tren version, khong co bang DocumentVersionStatus rieng)
insert DocumentRecipient
insert Asset
insert DocumentAsset
insert DocumentChunk parent
insert DocumentChunk child
insert IngestionJob
commit duoc
query lai duoc
cleanup duoc
```

Guide này dùng `commit + cleanup` trên DB test. Sau này có thể nâng cấp sang fixture transaction rollback.

## Bước 5: Pattern Test Tối Thiểu

Suggested pattern:

```python
import os
from datetime import date
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv
from sqlalchemy import delete, select

from app.databases.models import (
    Asset,
    Department,
    Document,
    DocumentAsset,
    DocumentChunk,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
    IngestionJob,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    raise RuntimeError(
        "Refusing to run database smoke tests unless DATABASE_URL points to "
        "ctu_student_service_test"
    )

from app.databases.session import AsyncSessionLocal  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def cleanup_test_data(session):
    await session.execute(delete(Document).where(Document.document_key == "test-document"))
    await session.execute(delete(Asset).where(Asset.asset_key == "test-asset"))
    await session.execute(delete(Department).where(Department.code == "TEST"))
    await session.execute(delete(DocumentType).where(DocumentType.code == "guide"))
    await session.commit()


async def test_insert_core_database_models():
    async with AsyncSessionLocal() as session:
        await cleanup_test_data(session)
        now = datetime.now(timezone.utc)

        department = Department(
            code="TEST",
            name="Phong Test",
            description="Only for database smoke test",
            updated_at=now,
        )
        document_type = DocumentType(
            code="guide",
            name="Huong dan test",
            description="Only for database smoke test",
            updated_at=now,
        )

        try:
            session.add_all([department, document_type])
            await session.flush()

            document = Document(
                document_key="test-document",
                title="Test Document",
                document_type_id=document_type.id,
                domain="test",
                audience=["student"],
            )
            session.add(document)
            await session.flush()

            # Status fields (ocr/review/rag) nam truc tiep tren document_versions.
            version = DocumentVersion(
                document_id=document.id,
                version_key="test-document-v1",
                title="Test Document V1",
                code="TEST-001",
                issued_date=date(2026, 6, 19),
                is_latest=True,
                source_url="",
                source_path="test/test.md",
                canonical_markdown_path="test/test.md",
                file_type="md",
                language="vi",
                issuing_authority="Phong Test",
                signer_name="",
                checksum="test-checksum",
                accessed_date=date(2026, 6, 19),
                ocr_status="done",
                review_status="approved",
                rag_status="published",
                updated_at=now,
            )
            session.add(version)
            await session.flush()

            recipient = DocumentRecipient(
                document_version_id=version.id,
                department_id=department.id,
                effective_date=date(2026, 6, 19),
            )

            asset = Asset(
                asset_key="test-asset",
                title="Test Asset",
                asset_type="form",
                url="",
                checksum=None,
            )

            session.add_all([recipient, asset])
            await session.flush()

            document_asset = DocumentAsset(
                document_version_id=version.id,
                asset_id=asset.id,
                relation_type="reference",
                required_when=None,
                display_order=0,
            )

            parent_chunk = DocumentChunk(
                document_version_id=version.id,
                chunk_key="test-document-v1::p::0001",
                chunk_index=0,
                chunk_type="parent",
                heading_path="Root",
                section_title="Root",
                content="Parent content",
                page_start=1,
                page_end=1,
                token_count=2,
                index_status="not_indexed",
            )

            session.add_all([document_asset, parent_chunk])
            await session.flush()

            child_chunk = DocumentChunk(
                document_version_id=version.id,
                parent_chunk_id=parent_chunk.id,
                chunk_key="test-document-v1::c::0001",
                chunk_index=1,
                chunk_type="child",
                heading_path="Root > Child",
                section_title="Child",
                content="Child content",
                page_start=1,
                page_end=1,
                token_count=2,
                qdrant_point_id="test-point-1",
                index_status="not_indexed",
            )

            job = IngestionJob(
                document_version_id=version.id,
                job_type="smoke_test",
                status="done",
                current_step="database",
                processed_chunks=1,
                created_by="pytest",
            )

            session.add_all([child_chunk, job])
            await session.commit()

            result = await session.execute(
                select(Document).where(Document.document_key == "test-document")
            )
            assert result.scalar_one().title == "Test Document"
        finally:
            await session.rollback()
            await cleanup_test_data(session)
```

## Bước 6: Cleanup Dữ Liệu Test

Nếu dùng DB test riêng, có 2 cách cleanup.

### Cách A: Drop/Recreate DB Test Khi Cần

Dùng khi test DB bị bẩn:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
docker compose exec postgres dropdb -U ct239h ctu_student_service_test
docker compose exec postgres createdb -U ct239h ctu_student_service_test
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
cd backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\alembic.exe upgrade head
```

### Cách B: Xóa Dữ Liệu Theo Test Key

Dùng khi chỉ cần xóa dữ liệu smoke test:

```sql
DELETE FROM css.documents WHERE document_key = 'test-document';
DELETE FROM css.assets WHERE asset_key = 'test-asset';
DELETE FROM css.departments WHERE code = 'TEST';
DELETE FROM css.document_types WHERE code = 'guide';
```

Nếu FK có `ON DELETE CASCADE`, xóa `documents` sẽ kéo theo versions/chunks/recipients/jobs liên quan. Status nằm trực tiếp trên `document_versions`.

## Bước 7: Chạy Test

Chạy tại:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
```

Set DB test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Chạy pytest:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/databases/test_database_models.py
```

Nếu test pass, có nghĩa:

```text
SQLAlchemy session dung duoc
model mapping dung duoc
foreign key dung duoc
relationship toi thieu dung duoc
migration tao schema du de insert du lieu core
```

## Lỗi Thường Gặp

### 1. Test vẫn ghi vào DB dev

Triệu chứng:

```text
du lieu test xuat hien trong ctu_student_service
```

Nguyên nhân:

```text
chua set $env:DATABASE_URL truoc khi chay pytest
```

Kiểm tra nhanh:

```powershell
echo $env:DATABASE_URL
```

### 2. Relation does not exist

Ví dụ:

```text
relation "css.documents" does not exist
```

Nguyên nhân:

```text
DB test chua chay alembic upgrade head
hoac DATABASE_URL dang tro sai database
```

### 3. UniqueViolation

Ví dụ:

```text
duplicate key value violates unique constraint
```

Nguyên nhân:

```text
test truoc da commit du lieu va chua cleanup
```

Cách xử lý:

```text
xoa data theo test key
hoac drop/recreate DB test
hoac doi sang transaction rollback fixture
```

### 4. MissingGreenlet

Nguyên nhân thường gặp:

```text
lazy-load relationship sai ngu canh async
truy cap relationship sau khi session da dong
```

Trong smoke test đầu tiên, ưu tiên query trực tiếp bằng `select(...)` thay vì dựa vào lazy relationship.

## Khi Nào Dùng Rollback Fixture

Sau khi smoke test đầu tiên chạy được, nên refactor test sang fixture rollback:

```text
moi test mo transaction
insert du lieu
assert ket qua
rollback cuoi test
```

Lợi ích:

```text
DB test luon sach
khong can cleanup bang tay
test chay lai nhieu lan khong bi duplicate key
```

Nhưng ở bước đầu, `commit + cleanup` dễ debug dễ hơn vì có thể mở DB ra xem dữ liệu thật.

## Definition Of Done

Hoàn thành guide 05 khi:

```text
ctu_student_service_test ton tai
schema css ton tai trong DB test
alembic current tren DB test hien revision head
\dt css.* tren DB test thay du bang core
test_database_models.py insert/query duoc cac model core
khong co du lieu test bi ghi vao DB dev
```