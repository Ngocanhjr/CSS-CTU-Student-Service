# 04. Hướng Dẫn Sửa Và Chạy Alembic Migration

**Last Updated:** 2026-07-10

File này nối tiếp sau `03_SQLALCHEMY_9_TABLES_GUIDE.md`.

Mục tiêu của guide 04 là sửa cấu hình Alembic, tạo migration đầu tiên, chạy migration vào PostgreSQL schema `css`, và kiểm tra DB có đủ bảng core.

## Mục Tiêu

Sau guide này cần đạt được:

```text
alembic.ini dung format INI
alembic/env.py load duoc Base.metadata
SQLAlchemy models import duoc
alembic revision --autogenerate tao duoc migration file
alembic upgrade head tao bang trong schema css
alembic current khong loi
```

## Lỗi Hiện Tại

Nếu chạy Alembic đang gặp lỗi:

```text
MissingSectionHeaderError: File contains no section headers.
file: 'alembic.ini', line: 1
'from dotenv import load_dotenv\n'
```

nguyên nhân là `alembic.ini` đang bị viết như file Python:

```python
from dotenv import load_dotenv
load_dotenv()
sqlalchemy.url = os.getenv("DATABASE_URL")
```

`alembic.ini` không chạy Python code. Nó phải là file INI, có section như:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://...
```

Việc load `.env` phải nằm trong `alembic/env.py`, không nằm trong `alembic.ini`.

## Điều Kiện Trước Khi Làm

Chạy tại root project:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service
```

Kiểm tra virtual environment có Alembic:

```powershell
.\.venv\Scripts\python.exe -c "import sqlalchemy, alembic; print(sqlalchemy.__version__); print(alembic.__version__)"
```

Nếu lệnh này lỗi, cài dependency trước:

```powershell
.\.venv\Scripts\python.exe -m pip install -r chatbot\backend\requirements.txt
```

Kiểm tra PostgreSQL đang chạy:

```powershell
cd chatbot
docker compose ps
```

Nếu `postgres` chưa chạy:

```powershell
docker compose up -d postgres
```

## Bước 1: Sửa `app/databases/base.py`

File:

```text
chatbot/backend/app/databases/base.py
```

`DeclarativeBase` phải import từ `sqlalchemy.orm`, không phải từ `sqlalchemy`.

Suggested pattern:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


metadata = MetaData(schema="css")


class Base(DeclarativeBase):
    metadata = metadata
```

Lý do:

```text
SQLAlchemy 2.x dat DeclarativeBase trong sqlalchemy.orm.
Base.metadata can co schema="css" de Alembic autogenerate table vao css.<table>.
```

Test nhanh:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -c "from app.databases.base import Base; print(Base.metadata.schema)"
```

Mong đợi:

```text
css
```

## Bước 2: Sửa `app/databases/__init__.py`

File:

```text
chatbot/backend/app/databases/__init__.py
```

Hiện tại cần tránh import sai tên như `SessionLocal`, `get_db` nếu `session.py` chỉ có `AsyncSessionLocal`, `get_session`.

Suggested pattern:

```python
from app.databases.base import Base
from app.databases.session import AsyncSessionLocal, engine, get_session

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "engine",
    "get_session",
]
```

Lý do:

```text
Alembic import app.databases.models.
Neu app.databases.__init__ import sai symbol, Alembic se fail truoc khi thay metadata.
```

Nếu muốn giảm side effect cho Alembic, cách tốt hơn là trong `alembic/env.py` import trực tiếp:

```python
from app.databases.base import Base
import app.databases.models  # noqa: F401
```

Không cần import `app.databases` package root nếu package root tạo engine quá sớm.

## Bước 3: Tạo Lại `alembic.ini` Đúng Format

File:

```text
chatbot/backend/alembic.ini
```

Nội dung tối thiểu:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
path_separator = os
sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Ghi chú:

```text
sqlalchemy.url o day chi la placeholder.
URL thuc te se duoc set trong env.py tu bien moi truong DATABASE_URL.
```

## Bước 4: Sửa `alembic/env.py`

File:

```text
chatbot/backend/alembic/env.py
```

Với `DATABASE_URL=postgresql+asyncpg://...`, nên dùng async Alembic env.

Suggested pattern:

```python
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.databases.base import Base
import app.databases.models  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set")

config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Tại sao cần `include_schemas=True`:

```text
Model dung MetaData(schema="css").
Neu khong include_schemas=True, Alembic co the generate/compare schema khong dung nhu mong doi.
```

## Bước 5: Đảm Bảo Schema `css` Tồn Tại

Nếu database đã tạo trước khi có init script, cần tạo schema thủ công:

```powershell
cd chatbot
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
```

Kiểm tra:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dn"
```

Mong đợi thấy schema:

```text
css
```

Ghi chú:

```text
Script trong database/postgres/init chi chay khi volume Postgres duoc tao lan dau.
Neu da co db/postgres volume tu truoc, them init script sau do se khong tu chay lai.
```

## Bước 6: Kiểm Tra Import Model Trước Khi Tạo Migration

Chạy:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -c "from app.databases.base import Base; import app.databases.models; print(sorted(Base.metadata.tables.keys()))"
```

Mong đợi thấy danh sách table có schema `css`, ví dụ:

```text
['css.assets', 'css.departments', 'css.document_assets', ...]
```

Nếu lỗi:

```text
ImportError: cannot import name 'DeclarativeBase' from 'sqlalchemy'
```

quay lại Bước 1.

Nếu lỗi:

```text
ImportError: cannot import name 'SessionLocal'
```

quay lại Bước 2.

## Bước 7: Tạo Migration Đầu Tiên

Chạy:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\alembic.exe revision --autogenerate -m "create core rag tables"
```

Sau lệnh này, Alembic sẽ tạo file trong:

```text
chatbot/backend/alembic/versions/
```

Mở file migration và kiểm tra:

```text
schema="css"
op.create_table(...) co du table core
foreign key tro toi css.<table>.id
unique constraint cho document_key/version_key/asset_key
document_assets co composite primary key
document_recipients co composite primary key (document_version_id, department_id, effective_date)
```

Nếu migration bị rỗng:

```text
upgrade() pass
downgrade() pass
```

thì Alembic chưa thấy metadata. Kiểm tra lại:

```text
alembic/env.py da import app.databases.models chua
Base.metadata.tables co table chua
```

## Bước 8: Chạy Migration

Chạy:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\alembic.exe upgrade head
```

Nếu gặp lỗi schema:

```text
schema "css" does not exist
```

quay lại Bước 5.

Nếu gặp lỗi connection:

```text
Connection refused
```

kiểm tra:

```powershell
cd chatbot
docker compose ps
docker compose logs postgres --tail 100
```

Nếu gặp lỗi auth:

```text
password authentication failed
```

kiểm tra `chatbot/.env` và `DATABASE_URL`.

## Bước 9: Kiểm Tra Kết Quả Trong PostgreSQL

Chạy:

```powershell
cd chatbot
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"
```

Mong đợi thấy các bảng core (9 bảng, status fields nằm trực tiếp trên document_versions, không có bảng document_version_status/document_version_relationships riêng — xem 19_MIGRATE_10_TO_9_TABLES_GUIDE.md):

```text
css.departments
css.document_types
css.documents
css.document_versions
css.document_recipients
css.document_chunks
css.assets
css.document_assets
css.ingestion_jobs
```

Kiểm tra revision hiện tại:

```powershell
cd backend
..\..\.venv\Scripts\alembic.exe current
```

Mong đợi thấy revision id của migration vừa tạo.

## Bước 10: Smoke Test Insert Tối Thiểu

Sau khi migration thành công, cần có smoke test insert data theo thứ tự:

```text
Department
DocumentType
Document
DocumentVersion
  - ocr_status
  - review_status
  - rag_status
  - status_note
DocumentRecipient
Asset
DocumentAsset
DocumentChunk parent
DocumentChunk child
IngestionJob
```

`DocumentVersionStatus` chỉ là tên schema Pydantic ở các guide schema cũ; nó không phải SQLAlchemy model hoặc bảng PostgreSQL. Status workflow nằm trực tiếp trên `DocumentVersion`.

Không cần test Qdrant trong guide 04. Guide này chỉ xác nhận PostgreSQL schema và SQLAlchemy mapping.

## Common Mistakes Cần Tránh

- Viết Python code trong `alembic.ini`.
- Quên `[alembic]` section trong `alembic.ini`.
- Import `DeclarativeBase` từ `sqlalchemy` thay vì `sqlalchemy.orm`.
- Import `app.databases` làm side effect tạo engine quá sớm khi Alembic chỉ cần models.
- Quên import `app.databases.models` trong `alembic/env.py`.
- Quên `include_schemas=True` khi model dùng schema `css`.
- Tạo migration khi `Base.metadata.tables` đang rỗng.
- Cho `DATABASE_URL` trong `.env` trỏ tới sai host khi chạy ngoài Docker.
- Nghĩ rằng init SQL trong `docker-entrypoint-initdb.d` sẽ chạy lại trên volume Postgres đã tồn tại.
- Sửa model sau khi generate migration nhưng không generate lại migration.

## Debug Checklist

Khi migration lỗi, kiểm tra theo thứ tự này:

```text
1. alembic.ini co section [alembic] khong?
2. env.py co load DATABASE_URL khong?
3. DATABASE_URL co trong chatbot/.env khong?
4. PostgreSQL container co dang chay khong?
5. Schema css da ton tai chua?
6. Base.metadata.tables co du table khong?
7. env.py co import app.databases.models khong?
8. Migration generated co create_table khong?
9. alembic_version co nam dung database khong?
```

Lệnh debug nhanh:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -c "from app.databases.base import Base; import app.databases.models; print(Base.metadata.schema); print(sorted(Base.metadata.tables.keys()))"
..\..\.venv\Scripts\alembic.exe history
..\..\.venv\Scripts\alembic.exe current
```

python -c "from app.databases.base import Base; import app.databases.models; print(Base.metadata.schema); print(sorted(Base.metadata.tables.keys()))"
alembic history
alembic current

## Definition Of Done

Hoàn thành guide 04 khi:

```text
alembic.ini doc duoc bang configparser
app.databases.models import duoc
Base.metadata.tables co du table core
schema css ton tai trong PostgreSQL
alembic revision --autogenerate tao migration khong rong
alembic upgrade head thanh cong
\dt css.* thay du bang core
alembic current hien revision moi nhat
```
