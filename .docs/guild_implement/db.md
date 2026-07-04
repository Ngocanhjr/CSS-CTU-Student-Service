# Database and Schema Sync Rules

Tai lieu nay quy dinh cach dong bo giua:

- Pydantic schemas: `chatbot/backend/app/schemas`
- SQLAlchemy database models: `chatbot/backend/app/databases/models`
- Alembic migrations: `chatbot/backend/alembic/versions`

Muc tieu la giu API/ingestion dung stable key de de trace, con database dung primary key va foreign key noi bo de bao toan toan ven du lieu.

## 1. Nguyen tac chinh

Schema khong nen phu thuoc vao database id sinh tu dong.

- Schema/input/output dung stable business keys: `document_key`, `version_key`, `asset_key`, `chunk_key`, `parent_chunk_key`.
- Database dung `id` lam primary key noi bo.
- Database dung cac cot FK noi bo nhu `document_id`, `document_version_id`, `asset_id`, `parent_chunk_id`.
- Service/repository layer chiu trach nhiem resolve stable key sang database id khi ghi DB.

Khong dua `id` noi bo vao metadata ingestion neu khong can thiet. Metadata nen uu tien key on dinh de co the trace, re-ingest, upsert, va debug qua nhieu moi truong DB.

## 2. Quy uoc dat ten

Dung `_key` cho dinh danh on dinh ngoai DB:

```text
document_key
version_key
asset_key
chunk_key
parent_chunk_key
```

Dung `_id` cho khoa noi bo trong DB:

```text
id
document_id
document_version_id
asset_id
parent_chunk_id
```

Neu mot truong la FK toi bang khac trong SQLAlchemy model, ten nen la `_id`. Neu mot truong xuat hien trong schema ingestion/API va duoc tao truoc khi insert DB, ten nen la `_key`.

## 3. Rule dong bo schema va DB

Moi entity co stable key phai co constraint duy nhat trong DB:

| Entity | Schema key | DB internal id | DB unique rule |
| --- | --- | --- | --- |
| Document | `document_key` | `documents.id` | `documents.document_key` unique |
| Document version | `version_key` | `document_versions.id` | `document_versions.version_key` unique |
| Asset | `asset_key` | `assets.id` | `assets.asset_key` unique |
| Chunk | `chunk_key` | `document_chunks.id` | unique theo version |

Moi schema field bat buoc phai co cot tuong ung trong DB, tru cac field chi dung de resolve quan he.

Vi du:

- `document_key` trong schema dung de tim `documents.id`.
- `version_key` trong schema dung de tim `document_versions.id`.
- `parent_chunk_key` trong schema dung de tim parent `document_chunks.id`.
- Cac field resolve-only nay co the khong luu truc tiep trong bang con neu FK noi bo da du de join nguoc.

## 4. Document rules

Schema document dung `document_key` lam dinh danh nghiep vu on dinh.

Database:

- `documents.id` la primary key.
- `documents.document_key` la unique, indexed, nullable false.
- Cac bang con khong can lap lai `document_key` neu da join duoc qua `document_versions.document_id`.

Khi ingest:

1. Nhan `document_key` tu metadata/schema.
2. Upsert hoac tim `documents` bang `document_key`.
3. Dung `documents.id` cho cac FK noi bo.

## 5. Document version rules

Schema version dung `version_key` de dai dien cho mot phien ban tai lieu.

Database:

- `document_versions.id` la primary key.
- `document_versions.document_id` FK toi `documents.id`.
- `document_versions.version_key` unique, indexed, nullable false.

Khi ingest:

1. Resolve `document_key` thanh `document_id`.
2. Upsert hoac tim `document_versions` bang `version_key`.
3. Dam bao `version_key` thuoc dung `document_id`.

Khong gan chunk truc tiep vao `document_key` neu khong co `version_key`, vi chunk phu thuoc vao noi dung cua tung version.

## 6. Asset rules

Schema asset dung `asset_key`.

Database:

- `assets.id` la primary key.
- `assets.asset_key` unique, indexed, nullable false.
- Bang lien ket `document_assets` dung `document_version_id` va `asset_id`.

Khi ingest relation asset:

1. Resolve `document_key` va `version_key` thanh `document_version_id`.
2. Resolve `asset_key` thanh `asset_id`.
3. Ghi relation bang FK noi bo.

Neu schema relation chi co `document_key` ma khong co `version_key`, can co rule ro rang de chon version, vi asset relation trong DB dang gan vao document version.

## 7. Chunk rules

Chunk parent va child deu la record trong cung bang `document_chunks`.

Database dung self-FK:

```text
document_chunks.id
document_chunks.parent_chunk_id -> document_chunks.id
```

Schema khong nen dung `parent_chunk_id`, vi client/chunker chua biet DB id. Schema nen dung:

```text
chunk_key: str
parent_chunk_key: str | None
chunk_type: parent | child
```

Rule bat buoc:

- Parent chunk: `parent_chunk_key` phai null.
- Child chunk: `parent_chunk_key` phai co gia tri.
- Parent va child cung nam trong `document_chunks`.
- `parent_chunk_id` trong DB phai tro toi mot chunk cung `document_version_id`.
- `chunk_key` phai on dinh trong pham vi mot `document_version`.

Nen co cot DB:

```text
document_chunks.chunk_key
```

Va constraint:

```text
UNIQUE(document_version_id, chunk_key)
```

Khong nen chi dua vao `chunk_index`, vi `chunk_index` tot cho thu tu, nhung khong phai dinh danh on dinh de resolve parent-child hay sync voi vector store.

## 8. Chunk insert flow

Flow khuyen nghi khi ghi chunks:

1. Validate schema `Chunk`.
2. Resolve `version_key` thanh `document_version_id`.
3. Insert hoac upsert tat ca parent chunks truoc, theo `chunk_key`.
4. Tao map `{chunk_key: id}` cho parent chunks trong cung `document_version_id`.
5. Insert child chunks, resolve `parent_chunk_key` thanh `parent_chunk_id`.
6. Luu `chunk_key` trong DB de ho tro re-ingest, upsert, audit, va Qdrant payload.

Neu child chunk tham chieu parent khong ton tai, ingestion phai fail som thay vi tao record mo coi.

## 9. Qdrant/vector payload rule

Vector payload nen dung stable keys:

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

Co the them DB id cho debug noi bo, nhung khong duoc xem DB id la dinh danh chinh cua vector payload.

`qdrant_point_id` nen co tinh on dinh, vi du sinh tu `version_key + chunk_key`, de upsert khong tao duplicate vectors.

## 10. Alembic migration rule

Moi thay doi SQLAlchemy model lien quan den cot, FK, index, constraint phai co Alembic migration tuong ung.

Checklist khi them/sua field:

- Cap nhat Pydantic schema neu field di qua API/ingestion.
- Cap nhat SQLAlchemy model neu field can luu DB.
- Cap nhat Alembic migration.
- Cap nhat tests schema validation.
- Cap nhat tests database model/constraint neu field anh huong FK, unique, hoac check constraint.

Khong chi sua model ma bo qua migration.

## 11. Contract hien tai can canh giac

Tai thoi diem viet rule nay, can dac biet dong bo cac diem sau:

- `schemas/chunks.py` dang dung `chunk_key` va `parent_chunk_key`.
- `databases/models/chunks.py` dang dung `parent_chunk_id` self-FK, dung huong.
- `databases/models/chunks.py` nen bo sung `chunk_key` va unique `(document_version_id, chunk_key)`.
- Tests cu co the con dung `chunk_key` hoac `parent_chunk_key`; nen doi sang `chunk_key` va `parent_chunk_key` o schema layer.
- `DocumentAssetRelation` nen co `version_key` neu relation trong DB tiep tuc gan vao `document_version_id`.

## 12. Quyet dinh thiet ke

Thiet ke duoc chap nhan:

```text
Schema boundary:
document_key, version_key, chunk_key, parent_chunk_key

Database boundary:
documents.id
document_versions.id
document_chunks.id
document_chunks.parent_chunk_id
```

Ket luan:

- Parent hay child deu la chunk, nen luu chung bang `document_chunks`.
- `parent_chunk_id` la FK noi bo dung de bao toan quan he trong DB.
- `parent_chunk_key` la contract dung o schema/API/ingestion.
- Can luu `chunk_key` trong DB de resolve, upsert, va trace on dinh.
