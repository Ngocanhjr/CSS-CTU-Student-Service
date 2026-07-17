# 05. Đặc Tả Database

**Version:** 3.0  
**Last Updated:** 2026-07-04  
**Status:** Final

> Deployable PostgreSQL DDL, Qdrant collection/payload, cross-store lifecycle, and retrieval
> eligibility are defined normatively in `10_POSTGRES_QDRANT_RETRIEVAL_CONTRACT.md`. That file
> overrides this overview wherever physical details differ.

## 1. Database Overview

- **RDBMS:** PostgreSQL 17
- **Schema source of truth:** latest owner-approved ERD
- **Current table count:** 9

Final tables:

1. `departments`
2. `document_types`
3. `documents`
4. `document_versions`
5. `document_chunks`
6. `ingestion_jobs`
7. `document_recipients`
8. `document_assets`
9. `assets`

Removed from current schema:

```text
version_status_history
document_version_status
document_version_relationships
collection_status
```

## 2. Table Specifications

### departments

```sql
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);
```

### document_types

```sql
CREATE TABLE document_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

### documents

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_key VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    domain VARCHAR(100),
    audience JSONB,
    document_type_id INTEGER REFERENCES document_types(id)
);
```

`documents` does not store `department_id`.

### document_versions

```sql
CREATE TABLE document_versions (
    id SERIAL PRIMARY KEY,
    version_key VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    code VARCHAR(100),
    issued_date DATE,
    is_latest BOOLEAN DEFAULT FALSE,
    source_url TEXT,
    source_path TEXT,
    canonical_markdown_path TEXT,
    file_type VARCHAR(50),
    language VARCHAR(10) DEFAULT 'vi',
    issuing_authority VARCHAR(255),
    signer_name VARCHAR(255),
    checksum VARCHAR(64),
    extra_metadata JSONB,
    accessed_date DATE,
    ocr_status VARCHAR(50) DEFAULT 'not_started',
    review_status VARCHAR(50) DEFAULT 'not_reviewed',
    rag_status VARCHAR(50) DEFAULT 'not_indexed',
    status_note TEXT,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE
);
```

Current status belongs directly in `document_versions`, not in `extra_metadata`.

### document_chunks

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    parent_chunk_id INTEGER REFERENCES document_chunks(id),
    chunk_key VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_type VARCHAR(20) NOT NULL,
    section_title TEXT,
    heading_path TEXT,
    content TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    token_count INTEGER,
    checksum VARCHAR(64),
    qdrant_point_id VARCHAR(255),
    index_status VARCHAR(50) DEFAULT 'not_indexed',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    UNIQUE(document_version_id, chunk_key),
    UNIQUE(document_version_id, chunk_index)
);
```

### ingestion_jobs

```sql
CREATE TABLE ingestion_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50),
    status VARCHAR(50),
    current_step VARCHAR(100),
    total_chunks INTEGER,
    processed_chunks INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE
);
```

### document_recipients

```sql
CREATE TABLE document_recipients (
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES departments(id),
    effective_date DATE NOT NULL,
    PRIMARY KEY (document_version_id, department_id, effective_date)
);
```

> **Ý nghĩa `effective_date`:** ngày phòng ban tiếp nhận văn bản (ngày nhận được tài liệu).
>
> **Lý do `effective_date` nằm trong PRIMARY KEY:** cùng một version có thể được gửi lại
> cho cùng một phòng ban vào một ngày khác (ví dụ: gửi lại sau khi có cập nhật nhỏ, hoặc
> gửi chính thức sau khi đã gửi nháp). Nếu PK chỉ là `(document_version_id, department_id)`
> thì lần gửi thứ hai sẽ vi phạm khóa chính. `effective_date` cho phép lưu đầy đủ lịch sử
> các lần tiếp nhận.

### assets

```sql
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    asset_key VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    url TEXT,
    checksum VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### document_assets

```sql
CREATE TABLE document_assets (
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,
    required_when TEXT,
    display_order INTEGER DEFAULT 0,
    PRIMARY KEY (document_version_id, asset_id, relation_type)
);
```

## 3. Status Enums

```text
ocr_status:    not_started | processing | need_review | failed | done
review_status: not_reviewed | reviewing | need_fix | approved | rejected
rag_status:    not_indexed | chunked | embedded | indexed | published | deactivated | failed
index_status:  not_indexed | indexed | deactivated | failed
```

## 4. Domain Values

`documents.domain` sử dụng soft enum — các giá trị gợi ý dưới đây khớp với `Domain` trong
`backend/app/schemas/enums.py`. Không nên dùng giá trị tùy tiện ngoài danh sách này.

```text
hoc_vu              -- Học vụ, đăng ký môn, lịch thi
hoc_phi             -- Học phí, miễn giảm, hỗ trợ
dao_tao             -- Chương trình đào tạo, quy chế
nghien_cuu_khoa_hoc -- Nghiên cứu khoa học
hop_tac_quoc_te     -- Hợp tác quốc tế, học bổng nước ngoài
hoc_bong            -- Học bổng trong nước
sinh_vien           -- Công tác sinh viên, KTX, hoạt động SV
```

Source of truth: `backend/app/schemas/enums.py` → `Domain`

## 5. Asset Type Values

`assets.asset_type` sử dụng soft enum — các giá trị khớp với `AssetType` trong
`backend/app/schemas/enums.py`:

```text
form        -- Biểu mẫu cần điền hoặc tải về
template    -- Mẫu tài liệu
guide       -- File hướng dẫn
attachment  -- File đính kèm khác
```

`document_assets.relation_type` sử dụng `DocumentAssetRelationType`:

```text
required_form  -- Biểu mẫu bắt buộc
reference      -- Tài liệu tham khảo
supplement     -- File bổ sung
guide          -- Hướng dẫn sử dụng
```

Source of truth: `backend/app/schemas/enums.py` → `AssetType`, `DocumentAssetRelationType`

## 4. RAG Rules

A version may be indexed when:

```text
ocr_status = done
review_status = approved
```

After successful chunking, embedding, and Qdrant upsert:

```text
rag_status: indexed -> published
```

Student retrieval filter:

```text
review_status = approved
rag_status = published
```

`is_latest` is only a ranking preference.
