# db_note.md — Working Note: Database Schema (9 Bảng Chốt)

> **Nguồn chính thức:**
> - Schema đầy đủ: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`
> - Quick reference: `chatbot/.docs/DATABASE_SCHEMA.md`

---

## Quy ước key và id

```text
Trong PostgreSQL:
- id          → SERIAL PRIMARY KEY, khóa kỹ thuật nội bộ
- *_id        → Foreign key nội bộ (document_id, document_version_id, asset_id, department_id, document_type_id, parent_chunk_id)

Trong YAML / Pydantic / RAG payload:
- *_key       → Business key ổn định (document_key, version_key, chunk_key, parent_chunk_key, asset_key)
```

Không dùng `document_id` / `version_id` trong Pydantic metadata — dùng `document_key` / `version_key`.

---

## 9 Bảng Chốt

### 1. departments

```text
id            SERIAL PRIMARY KEY
code          VARCHAR(50) UNIQUE NOT NULL
name          VARCHAR(255) NOT NULL
description   TEXT
is_active     BOOLEAN DEFAULT TRUE
```

### 2. document_types

```text
id            SERIAL PRIMARY KEY
code          VARCHAR(50) UNIQUE NOT NULL   -- noi_quy | quy_trinh | bieu_mau | hoi_dap
name          VARCHAR(255) NOT NULL
is_active     BOOLEAN DEFAULT TRUE
```

### 3. documents

```text
id                SERIAL PRIMARY KEY
document_key      VARCHAR(255) UNIQUE NOT NULL
title             VARCHAR(500) NOT NULL
domain            VARCHAR(100)
audience          JSONB
document_type_id  INTEGER REFERENCES document_types(id)
```

> `documents` KHÔNG có `department_id`.
> Quan hệ document ↔ department thể hiện qua bảng `document_recipients`.

### 4. document_versions

```text
id                        SERIAL PRIMARY KEY
version_key               VARCHAR(255) UNIQUE NOT NULL
title                     VARCHAR(500) NOT NULL
code                      VARCHAR(100)
issued_date               DATE
is_latest                 BOOLEAN DEFAULT FALSE
source_url                TEXT
source_path               TEXT
canonical_markdown_path   TEXT
file_type                 VARCHAR(50)
language                  VARCHAR(10) DEFAULT 'vi'
issuing_authority         VARCHAR(255)
signer                    VARCHAR(255)
checksum                  VARCHAR(64)
extra_metadata            JSONB
accessed_date             DATE
ocr_status                VARCHAR(50) DEFAULT 'not_started'
review_status             VARCHAR(50) DEFAULT 'not_reviewed'
rag_status                VARCHAR(50) DEFAULT 'not_indexed'
status_note               TEXT
document_id               INTEGER REFERENCES documents(id) ON DELETE CASCADE
```

> Status (`ocr_status`, `review_status`, `rag_status`) nằm **trực tiếp** trong bảng này.
> Không có bảng `document_version_status` riêng biệt.
> Không có `effective_date`, `expiry_date`, `version_role`, `version_label`, `citation_type`, `collection_status` trong schema chốt.

### 5. document_chunks

```text
id                  SERIAL PRIMARY KEY
parent_chunk_id     INTEGER REFERENCES document_chunks(id)   -- self-FK, NULL nếu là parent chunk
chunk_key           VARCHAR(255) NOT NULL
chunk_index         INTEGER NOT NULL
chunk_type          VARCHAR(20) NOT NULL                      -- 'parent' | 'child'
section_title       TEXT
heading_path        TEXT
content             TEXT NOT NULL
page_start          INTEGER
page_end            INTEGER
token_count         INTEGER
checksum            VARCHAR(64)
qdrant_point_id     VARCHAR(255)
index_status        VARCHAR(50) DEFAULT 'not_indexed'
created_at          TIMESTAMP DEFAULT NOW()
updated_at          TIMESTAMP DEFAULT NOW()
document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE

UNIQUE(document_version_id, chunk_key)
UNIQUE(document_version_id, chunk_index)
```

> Dùng `parent_chunk_id` (không phải `parent_id`).
> Dùng `chunk_type` (không phải `chunk_level`).

### 6. ingestion_jobs

```text
id                   SERIAL PRIMARY KEY
job_type             VARCHAR(50)
status               VARCHAR(50)          -- pending | running | done | failed | cancelled
current_step         VARCHAR(100)         -- uploaded | parsing | parsed | chunking | embedding | indexing | published | failed
total_chunks         INTEGER
processed_chunks     INTEGER DEFAULT 0
error_message        TEXT
started_at           TIMESTAMP
finished_at          TIMESTAMP
created_by           VARCHAR(100)
created_at           TIMESTAMP DEFAULT NOW()
updated_at           TIMESTAMP DEFAULT NOW()
document_version_id  INTEGER REFERENCES document_versions(id) ON DELETE CASCADE
```

> Dùng `current_step` (không phải `current_stage`).
> Không có `tool_name` trong schema chốt.

### 7. document_recipients

```text
document_version_id  INTEGER REFERENCES document_versions(id) ON DELETE CASCADE
department_id        INTEGER REFERENCES departments(id)
effective_date       DATE NOT NULL

PRIMARY KEY (document_version_id, department_id, effective_date)
```

> **Ý nghĩa `effective_date`:** ngày phòng ban tiếp nhận văn bản.
>
> **Lý do nằm trong PK:** cùng một version có thể được gửi lại cho cùng phòng ban vào
> ngày khác (gửi lại sau cập nhật, hoặc gửi chính thức sau khi đã gửi nháp). `effective_date`
> cho phép lưu đầy đủ lịch sử các lần tiếp nhận mà không vi phạm khóa chính.
>
> Bảng trung gian M:N giữa `document_versions` và `departments`.

### 8. assets

```text
id               SERIAL PRIMARY KEY
asset_key        VARCHAR(255) UNIQUE NOT NULL
title            VARCHAR(500) NOT NULL
asset_type       VARCHAR(50) NOT NULL    -- FORM_LINK | VIDEO_LINK | WEB_LINK | ...
url              TEXT
checksum         VARCHAR(64)
validity_status  VARCHAR(50) DEFAULT 'valid'   -- valid | invalid | expired
created_at       TIMESTAMP DEFAULT NOW()
```

### 9. document_assets

```text
document_version_id  INTEGER REFERENCES document_versions(id) ON DELETE CASCADE
asset_id             INTEGER REFERENCES assets(id) ON DELETE CASCADE
relation_type        VARCHAR(50) NOT NULL
required_when        TEXT
display_order        INTEGER DEFAULT 0

PRIMARY KEY (document_version_id, asset_id, relation_type)
```

---

## Status Enums

```text
ocr_status:
  not_started | processing | need_review | failed | done

review_status:
  not_reviewed | reviewing | need_fix | approved | rejected

rag_status:
  not_indexed | chunked | embedded | indexed | published | deactivated | failed

index_status (document_chunks):
  not_indexed | indexed | deactivated | failed

validity_status (assets):
  valid | invalid | expired
```

---

## Bảng đã bị loại khỏi schema

```text
document_version_status      → đã xóa, status nằm trong document_versions
document_version_relationships → đã xóa
collection_status            → đã xóa
version_status_history       → đã xóa
```

---

## Điều kiện publish

```text
ocr_status    = done
review_status = approved
```

Sau khi Qdrant upsert thành công:

```text
rag_status = published
```

## Student retrieval filter

```text
review_status = approved
rag_status    = published
```

`is_latest` là ranking preference, không phải hard filter.

---

## Chunk key format

```text
Parent: <version_key>::p::<index>    ví dụ: quy-che-2024-v1::p::0001
Child:  <version_key>::c::<index>    ví dụ: quy-che-2024-v1::c::0001
```
