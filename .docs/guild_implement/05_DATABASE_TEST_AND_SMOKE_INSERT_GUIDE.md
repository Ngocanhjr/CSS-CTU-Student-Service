# 05. Huong Dan Tao DB Test Va Smoke Test SQLAlchemy Models

**Last Updated:** 2026-06-19

File nay noi tiep sau `04_ALEMBIC_MIGRATION_GUIDE.md`.

Sau khi `alembic upgrade head` thanh cong, buoc tiep theo la xac nhan SQLAlchemy models co the insert/query du lieu that vao PostgreSQL. Nen lam viec nay tren database test rieng de khong lam ban database dev.

## Muc Tieu

Sau guide nay can dat duoc:

```text
co database test rieng: ctu_student_service_test
database test co schema css
database test da chay alembic upgrade head
pytest co the insert du lieu qua SQLAlchemy models
test khong lam ban database dev ctu_student_service
```

## Vi Sao Can DB Test Rieng

Database dev hien tai:

```text
ctu_student_service
```

nen dung cho app chay thu, debug API, va du lieu dang phat trien.

Database test rieng:

```text
ctu_student_service_test
```

chi dung cho automated test.

Ly do:

```text
test co the insert/update/delete thoai mai
khong lam ban du lieu dev
khong bi loi trung unique key do test cu de lai
co the drop/recreate khi can
co the chay CI/local test an toan hon
```

## Nguyen Tac

Khong de test ghi truc tiep vao DB dev:

```text
postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service
```

Test phai dung DB test:

```text
postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test
```

Trong PowerShell, override `DATABASE_URL` truoc khi chay migration/test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Ghi chu:

```text
load_dotenv() mac dinh khong override env var da co san.
Vi vay bien $env:DATABASE_URL trong PowerShell se uu tien hon gia tri trong .env.
```

Khong chay test file truc tiep bang:

```powershell
python test/databases/test_database_models.py
```

Lenh do se dat import root thanh `test/databases`, nen Python co the khong thay package `app`.

Hay chay bang pytest tu thu muc `chatbot/backend`, vi repo da co `pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = test
```

## Buoc 1: Tao Database Test

Chay tai:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
```

Tao DB test:

```powershell
docker compose exec postgres createdb -U ct239h ctu_student_service_test
```

Neu bao database da ton tai thi khong sao. Co the kiem tra danh sach DB:

```powershell
docker compose exec postgres psql -U ct239h -d postgres -c "\l"
```

## Buoc 2: Tao Schema `css` Trong DB Test

Chay:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
```

Kiem tra:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dn"
```

Mong doi thay:

```text
css
```

## Buoc 3: Chay Migration Vao DB Test

Chay tai:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
```

Set `DATABASE_URL` sang DB test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Chay migration:

```powershell
..\..\.venv\Scripts\alembic.exe upgrade head
```

Kiem tra revision:

```powershell
..\..\.venv\Scripts\alembic.exe current
```

Mong doi thay revision moi nhat, vi du:

```text
42bc821c519a
```

Kiem tra bang:

```powershell
cd ..
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dt css.*"
```

## Buoc 4: Chuan Bi Test File

File nen tao:

```text
chatbot/backend/test/databases/test_database_models.py
```

Muc tieu cua test:

```text
insert Department
insert DocumentType
insert Document
insert DocumentVersion (status fields nam truc tiep tren version)
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

Guide nay dung `commit + cleanup` tren DB test. Sau nay co the nang cap sang fixture transaction rollback.

## Buoc 5: Pattern Test Toi Thieu

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
                signer="",
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
                validity_status="valid",
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

## Buoc 6: Cleanup Du Lieu Test

Neu dung DB test rieng, co 2 cach cleanup.

### Cach A: Drop/Recreate DB Test Khi Can

Dung khi test DB bi ban:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
docker compose exec postgres dropdb -U ct239h ctu_student_service_test
docker compose exec postgres createdb -U ct239h ctu_student_service_test
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
cd backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\alembic.exe upgrade head
```

### Cach B: Xoa Du Lieu Theo Test Key

Dung khi chi can xoa du lieu smoke test:

```sql
DELETE FROM css.documents WHERE document_key = 'test-document';
DELETE FROM css.assets WHERE asset_key = 'test-asset';
DELETE FROM css.departments WHERE code = 'TEST';
DELETE FROM css.document_types WHERE code = 'guide';
```

Neu FK co `ON DELETE CASCADE`, xoa `documents` se keo theo versions/chunks/recipients/jobs lien quan. Status nam truc tiep tren `document_versions`.

## Buoc 7: Chay Test

Chay tai:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
```

Set DB test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Chay pytest:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/databases/test_database_models.py
```

Neu test pass, co nghia:

```text
SQLAlchemy session dung duoc
model mapping dung duoc
foreign key dung duoc
relationship toi thieu dung duoc
migration tao schema du de insert du lieu core
```

## Loi Thuong Gap

### 1. Test van ghi vao DB dev

Trieu chung:

```text
du lieu test xuat hien trong ctu_student_service
```

Nguyen nhan:

```text
chua set $env:DATABASE_URL truoc khi chay pytest
```

Kiem tra nhanh:

```powershell
echo $env:DATABASE_URL
```

### 2. Relation does not exist

Vi du:

```text
relation "css.documents" does not exist
```

Nguyen nhan:

```text
DB test chua chay alembic upgrade head
hoac DATABASE_URL dang tro sai database
```

### 3. UniqueViolation

Vi du:

```text
duplicate key value violates unique constraint
```

Nguyen nhan:

```text
test truoc da commit du lieu va chua cleanup
```

Cach xu ly:

```text
xoa data theo test key
hoac drop/recreate DB test
hoac doi sang transaction rollback fixture
```

### 4. MissingGreenlet

Nguyen nhan thuong gap:

```text
lazy-load relationship sai ngu canh async
truy cap relationship sau khi session da dong
```

Trong smoke test dau tien, uu tien query truc tiep bang `select(...)` thay vi dua vao lazy relationship.

## Khi Nao Dung Rollback Fixture

Sau khi smoke test dau tien chay duoc, nen refactor test sang fixture rollback:

```text
moi test mo transaction
insert du lieu
assert ket qua
rollback cuoi test
```

Loi ich:

```text
DB test luon sach
khong can cleanup bang tay
test chay lai nhieu lan khong bi duplicate key
```

Nhung o buoc dau, `commit + cleanup` de debug de hon vi co the mo DB ra xem du lieu that.

## Definition Of Done

Hoan thanh guide 05 khi:

```text
ctu_student_service_test ton tai
schema css ton tai trong DB test
alembic current tren DB test hien revision head
\dt css.* tren DB test thay du bang core
test_database_models.py insert/query duoc cac model core
khong co du lieu test bi ghi vao DB dev
```
