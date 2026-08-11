# note.md — Working Note: Implementation Progress

> **Nguồn chính thức:**
>
> - Schema: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`
> - Implementation order: `chatbot/.docs/IMPLEMENTATION_ORDER.md`
> - Backend structure: `chatbot/.docs/BACKEND_STRUCTURE.md`

---
Test connection cloud qdrant
python -c "from dotenv import load_dotenv; load_dotenv(); from app.vectorstore.qdrant_client import get_qdrant_client; c=get_qdrant_client(); print([x.name for x in c.get_collections().collections])"
---


---

## Docker / PostgreSQL

```bash
#Lệnh mở command line psql
docker compose exec postgres psql -U ct239h -d ctu_student_service
#thoát
\q

# Tạo schema css nếu chưa có
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"

# Kiểm tra schema
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dn"

# Kiểm tra bảng trong schema css
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"

#Tạo databases test
docker compose exec postgres createdb -U ct239h ctu_student_service_test
#Tạo schemas test
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"
#drop
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "DROP SCHEMA css CASCADE; CREATE SCHEMA css;"
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "DROP SCHEMA css CASCADE; CREATE SCHEMA css;"

#Trong DB, xóa dấu Alembic cũ:
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "DROP TABLE IF EXISTS alembic_version;"


#trong schemas
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "DROP TABLE IF EXISTS css.alembic_version;"

#tạo migration baseline mới
..\..\.venv\Scripts\alembic.exe revision --autogenerate -m "create core rag tables"
..\..\.venv\Scripts\alembic.exe revision --autogenerate -m "create core rag tables"
..\..\.venv\Scripts\alembic.exe current
..\..\.venv\Scripts\alembic.exe upgrade head
# Xác nhận kết quả
docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"
```

---

## Activate venv (Windows)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Run tests

```bash
python -m pytestS
```

---

## Quy ước key và id

```text
Trong PostgreSQL:
- id                    → SERIAL PRIMARY KEY, khóa kỹ thuật nội bộ
- document_id           → FK nội bộ
- document_version_id   → FK nội bộ
- asset_id              → FK nội bộ
- parent_chunk_id       → self-FK trong document_chunks

Trong YAML / Pydantic / RAG payload:
- document_key          → business key ổn định của tài liệu
- version_key           → business key ổn định của version
- asset_key             → business key ổn định của asset
- chunk_key             → business key ổn định của chunk
- parent_chunk_key      → business key của parent chunk
```

Không dùng `document_id` / `version_id` trong Pydantic metadata. Dùng `document_key` / `version_key`.

---

## Object mapping trong code

```text
Pydantic Chunk
    ↓ chuyển đổi
LangChain Document
    ↓
Embedding (BGE-M3) / Qdrant upsert

Pydantic Chunk
    ↓ chuyển đổi
SQLAlchemy DocumentChunk
    ↓
PostgreSQL insert (css.document_chunks)
```

---

## Checklist triển khai

- [x] 1\. PostgreSQL chạy được

  - Container healthy
  - Kết nối được `ctu_student_service`
  - Schema `css` tồn tại

- [x] 2\. Xác định draft fields cho chunk

  - `document_key`, `version_key`
  - `chunk_key`, `parent_chunk_key`
  - `parent_chunk_id`, `chunk_type`
  - `content`, `heading_path`, `section_title`
  - `page_start`, `page_end`
  - `chunk_index`, `token_count`

- [x] 3\. Tạo Chunk Pydantic model

  - Validate field bắt buộc
  - Validate page và chunk_index
  - Phân biệt `chunk_type = parent` / `child`

- [ ] 4\. Viết Markdown chunker

  - Đọc heading Markdown bằng `MarkdownHeaderTextSplitter`
  - Nhận diện `<!-- page: N -->`
  - Tạo parent chunk theo section
  - Chia child chunk theo kích thước (300–600 tokens)
  - Giữ metadata kế thừa (`heading_path`, `section_title`)

- [ ] 5\. Preview chunk từ file OCR thật

  - In ra JSON hoặc Markdown
  - Kiểm tra không mất nội dung
  - Kiểm tra `heading_path`
  - Kiểm tra `page_start` / `page_end`
  - Kiểm tra chunk quá ngắn hoặc quá dài

- [x] 6\. Chốt schema fields

  - Field lưu trong PostgreSQL → `document_chunks`
  - Field lưu trong Qdrant payload
  - Field chỉ dùng tạm trong pipeline

- [x] 7\. Tạo SQLAlchemy models cho 9 bảng chốt:

  - `departments`
  - `document_types`
  - `documents`
  - `document_versions`
  - `document_chunks`
  - `ingestion_jobs`
  - `document_recipients`
  - `document_assets`
  - `assets`

  > Không tạo `document_version_status` hay `document_version_relationships` — hai bảng này đã bị loại.

- [ ] 8\. Tạo và chạy Alembic migration

  - `alembic revision --autogenerate`
  - `alembic upgrade head`
  - Kiểm tra bảng trong `css.*`

- [ ] 9\. Insert metadata và chunks vào PostgreSQL

  - Insert `documents`
  - Insert `document_versions`
  - Insert `document_recipients` (quan hệ version ↔ phòng ban)
  - Insert parent / child chunks vào `document_chunks`
  - `document_versions.rag_status = not_indexed`

- [ ] 10\. Embed child chunks

  - Dùng `BAAI/bge-m3`
  - Chỉ embed `chunk_type = 'child'`, không embed parent
  - Lưu `embedding_model` và `embedding_version` trong log

- [ ] 11\. Upsert vào Qdrant

  - Vector của child chunk
  - Payload gồm `chunk_key`, `parent_chunk_key`, `postgres_chunk_id` (để join nhanh)
  - Payload gồm `document_key`, `version_key`, `review_status`, `rag_status`, `is_latest`
  - Không dùng Qdrant là nguồn metadata chính

- [ ] 12\. Cập nhật trạng thái sau indexing

  - Thành công: `document_versions.rag_status = published`
  - Thất bại: `document_versions.rag_status = failed`
  - Cập nhật `document_chunks.index_status` tương ứng
  - Lưu `error_message` trong `ingestion_jobs`

---

## Pydantic schemas cần tạo

```text
app/schemas/enums.py       → OcrStatus, ReviewStatus, RagStatus, IndexStatus, AssetValidityStatus
app/schemas/documents.py   → Document, DocumentVersion
app/schemas/assets.py      → Asset, DocumentAsset
app/schemas/chunks.py      → DocumentChunk (parent + child)
app/schemas/rag.py         → RagRequest, RagResponse, Citation, RelatedAsset
```