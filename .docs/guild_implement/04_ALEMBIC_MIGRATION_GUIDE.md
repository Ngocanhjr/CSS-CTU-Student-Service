# 04. Huong Dan Sua Va Chay Alembic Migration

**Last Updated:** 2026-06-19

File nay noi tiep sau `03_SQLALCHEMY_9_TABLES_GUIDE.md`.

Muc tieu cua guide 04 la sua cau hinh Alembic, tao migration dau tien, chay migration vao PostgreSQL schema `css`, va kiem tra DB co du bang core.

## Muc Tieu

Sau guide nay can dat duoc:

```text
alembic.ini dung format INI
alembic/env.py load duoc Base.metadata
SQLAlchemy models import duoc
alembic revision --autogenerate tao duoc migration file
alembic upgrade head tao bang trong schema css
alembic current khong loi
```

## Loi Hien Tai

Neu chay Alembic dang gap loi:

```text
MissingSectionHeaderError: File contains no section headers.
file: 'alembic.ini', line: 1
'from dotenv import load_dotenv\n'
```

nguyen nhan la `alembic.ini` dang bi viet nhu file Python:

```python
from dotenv import load_dotenv
load_dotenv()
sqlalchemy.url = os.getenv("DATABASE_URL")
```

`alembic.ini` khong chay Python code. No phai la file INI, co section nhu:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://...
```

Viec load `.env` phai nam trong `alembic/env.py`, khong nam trong `alembic.ini`.

## Dieu Kien Truoc Khi Lam

Chay tai root project:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service
```

Kiem tra virtual environment co Alembic:

```powershell
.\.venv\Scripts\python.exe -c "import sqlalchemy, alembic; print(sqlalchemy.__version__); print(alembic.__version__)"
```

Neu lenh nay loi, cai dependency truoc:

```powershell
.\.venv\Scripts\python.exe -m pip install -r chatbot\backend\requirements.txt
```

Kiem tra PostgreSQL dang chay:

```powershell
cd chatbot
docker compose ps
```

Neu `postgres` chua chay:

```powershell
docker compose up -d postgres
```

## Buoc 1: Sua `app/databases/base.py`

File:

```text
chatbot/backend/app/databases/base.py
```

`DeclarativeBase` phai import tu `sqlalchemy.orm`, khong phai tu `sqlalchemy`.

Suggested pattern:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


metadata = MetaData(schema="css")


class Base(DeclarativeBase):
    metadata = metadata
```

Ly do:

```text
SQLAlchemy 2.x dat DeclarativeBase trong sqlalchemy.orm.
Base.metadata can co schema="css" de Alembic autogenerate table vao css.<table>.
```

Test nhanh:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -c "from app.databases.base import Base; print(Base.metadata.schema)"
```

Mong doi:

```text
css
```

## Buoc 2: Sua `app/databases/__init__.py`

File:

```text
chatbot/backend/app/databases/__init__.py
```

Hien tai can tranh import sai ten nhu `SessionLocal`, `get_db` neu `session.py` chi co `AsyncSessionLocal`, `get_session`.

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

Ly do:

```text
Alembic import app.databases.models.
Neu app.databases.__init__ import sai symbol, Alembic se fail truoc khi thay metadata.
```

Neu muon giam side effect cho Alembic, cach tot hon la trong `alembic/env.py` import truc tiep:

```python
from app.databases.base import Base
import app.databases.models  # noqa: F401
```

Khong can import `app.databases` package root neu package root tao engine qua som.

## Buoc 3: Tao Lai `alembic.ini` Dung Format

File:

```text
chatbot/backend/alembic.ini
```

Noi dung toi thieu:

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

Ghi chu:

```text
sqlalchemy.url o day chi la placeholder.
URL thuc te se duoc set trong env.py tu bien moi truong DATABASE_URL.
```

## Buoc 4: Sua `alembic/env.py`

File:

```text
chatbot/backend/alembic/env.py
```

Voi `DATABASE_URL=postgresql+asyncpg://...`, nen dung async Alembic env.

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

Tai sao can `include_schemas=True`:

```text
Model dung MetaData(schema="css").
Neu khong include_schemas=True, Alembic co the generate/compare schema khong dung nhu mong doi.
```

## Buoc 5: Dam Bao Schema `css` Ton Tai

Neu database da tao truoc khi co init script, can tao schema thu cong:

```powershell
cd chatbot
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
```

Kiem tra:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dn"
```

Mong doi thay schema:

```text
css
```

Ghi chu:

```text
Script trong database/postgres/init chi chay khi volume Postgres duoc tao lan dau.
Neu da co db/postgres volume tu truoc, them init script sau do se khong tu chay lai.
```

## Buoc 6: Kiem Tra Import Model Truoc Khi Tao Migration

Chay:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -c "from app.databases.base import Base; import app.databases.models; print(sorted(Base.metadata.tables.keys()))"
```

Mong doi thay danh sach table co schema `css`, vi du:

```text
['css.assets', 'css.departments', 'css.document_assets', ...]
```

Neu loi:

```text
ImportError: cannot import name 'DeclarativeBase' from 'sqlalchemy'
```

quay lai Buoc 1.

Neu loi:

```text
ImportError: cannot import name 'SessionLocal'
```

quay lai Buoc 2.

## Buoc 7: Tao Migration Dau Tien

Chay:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\alembic.exe revision --autogenerate -m "create core rag tables"
```

Sau lenh nay, Alembic se tao file trong:

```text
chatbot/backend/alembic/versions/
```

Mo file migration va kiem tra:

```text
schema="css"
op.create_table(...) co du table core
foreign key tro toi css.<table>.id
unique constraint cho document_key/version_key/asset_key
document_assets co composite primary key
document_version_status dung document_version_id la primary key neu model da chot nhu vay
```

Neu migration bi rong:

```text
upgrade() pass
downgrade() pass
```

thi Alembic chua thay metadata. Kiem tra lai:

```text
alembic/env.py da import app.databases.models chua
Base.metadata.tables co table chua
```

## Buoc 8: Chay Migration

Chay:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\alembic.exe upgrade head
```

Neu gap loi schema:

```text
schema "css" does not exist
```

quay lai Buoc 5.

Neu gap loi connection:

```text
Connection refused
```

kiem tra:

```powershell
cd chatbot
docker compose ps
docker compose logs postgres --tail 100
```

Neu gap loi auth:

```text
password authentication failed
```

kiem tra `chatbot/.env` va `DATABASE_URL`.

## Buoc 9: Kiem Tra Ket Qua Trong PostgreSQL

Chay:

```powershell
cd chatbot
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"
```

Mong doi thay cac bang core:

```text
css.departments
css.document_types
css.documents
css.document_versions
css.document_version_status
css.document_version_relationships
css.document_chunks
css.assets
css.document_assets
css.ingestion_jobs
```

Kiem tra revision hien tai:

```powershell
cd backend
..\..\.venv\Scripts\alembic.exe current
```

Mong doi thay revision id cua migration vua tao.

## Buoc 10: Smoke Test Insert Toi Thieu

Sau khi migration thanh cong, can co smoke test insert data theo thu tu:

```text
Department
DocumentType
Document
DocumentVersion
DocumentVersionStatus
Asset
DocumentAsset
DocumentChunk parent
DocumentChunk child
IngestionJob
```

Khong can test Qdrant trong guide 04. Guide nay chi xac nhan PostgreSQL schema va SQLAlchemy mapping.

## Common Mistakes Can Tranh

- Viet Python code trong `alembic.ini`.
- Quen `[alembic]` section trong `alembic.ini`.
- Import `DeclarativeBase` tu `sqlalchemy` thay vi `sqlalchemy.orm`.
- Import `app.databases` lam side effect tao engine qua som khi Alembic chi can models.
- Quen import `app.databases.models` trong `alembic/env.py`.
- Quen `include_schemas=True` khi model dung schema `css`.
- Tao migration khi `Base.metadata.tables` dang rong.
- Cho `DATABASE_URL` trong `.env` tro toi sai host khi chay ngoai Docker.
- Nghi rang init SQL trong `docker-entrypoint-initdb.d` se chay lai tren volume Postgres da ton tai.
- Sua model sau khi generate migration nhung khong generate lai migration.

## Debug Checklist

Khi migration loi, kiem tra theo thu tu nay:

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

Lenh debug nhanh:

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

Hoan thanh guide 04 khi:

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

