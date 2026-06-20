conti# 05. Đặc Tả Database

**Version:** 1.0  
**Last Updated:** 2026-06-16  
**Status:** Final

---

## Mục Lục

1. [Database Overview](#database-overview)
2. [Entity Relationship Diagram](#entity-relationship-diagram)
3. [Core Tables (Phase 1 MVP)](#core-tables-phase-1-mvp)
4. [Table Specifications](#table-specifications)
5. [Status Enum Definitions](#status-enum-definitions)
6. [Indexes và Constraints](#indexes-và-constraints)
7. [Document Governance Rules](#document-governance-rules)

---

## Database Overview

### Database System
- **RDBMS:** PostgreSQL 17 (pined — xem `compose.yaml`)
- **Extensions:** pg_trgm (trigram similarity), btree_gin (multi-column GIN index)
- **Character Encoding:** UTF-8
- **Connection Pool:** SQLAlchemy async engine

### Core Tables (Phase 1 MVP)

Chỉ implement 8 tables trong MVP:

1. **`departments`** — CTU phòng ban quản lý tài liệu
2. **`document_types`** — Loại tài liệu (noi_quy, quy_trinh, bieu_mau, hoi_dap)
3. **`documents`** — Logical document (stable across versions)
4. **`document_versions`** — Version cụ thể với status fields
5. **`document_chunks`** — Parent-child chunks với Qdrant point IDs
6. **`assets`** — Forms, templates, downloadable files
7. **`document_assets`** — Relationship giữa document version và assets
8. **`ingestion_jobs`** — OCR/chunking/embedding job tracking

### Future Tables (Phase 2+)

Chưa implement trong MVP:
- `procedures`, `procedure_steps` — Procedure workflow (sau khi RAG hoạt động)
- `eligibility_rules` — Business rules cho procedures
- `users`, `roles`, `permissions` — Full RBAC (hiện dùng simple auth)
- `chat_sessions`, `chat_messages` — Chat history persistence
- `citations` — Citation tracking và analytics
- `audit_logs` — Audit trail cho governance

---

## Entity Relationship Diagram

📊 **[Xem ERD chi tiết: ../../diagrams/mermaid/erd.mmd](../../diagrams/mermaid/erd.mmd)**

### High-Level Relationships

```text
departments ──┐
              ├──→ documents ──→ document_versions ──┬──→ document_chunks
document_types┘                                      │
                                                     ├──→ document_assets ──→ assets
                                                     │
                                                     └──→ ingestion_jobs
```

---

## Core Tables (Phase 1 MVP)

### Table Responsibilities

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `departments` | CTU unit/office (Phòng Đào Tạo, Học Vụ, CTSV, etc.) | code, name, is_active |
| `document_types` | Document type catalog | code (noi_quy, quy_trinh, bieu_mau, hoi_dap) |
| `documents` | Stable logical document identity | document_key, title, department, type |
| `document_versions` | Specific version với dates, status | version_key, effective_date, is_latest, status fields |
| `document_chunks` | Parent-child chunks với page markers | parent_id, content, page_start, qdrant_point_id |
| `assets` | Forms/templates/downloads | asset_key, file_path, download_url |
| `document_assets` | Links document version → assets | relation_type (required_form, reference, supplement) |
| `ingestion_jobs` | Job tracking (OCR, chunking, indexing) | current_stage, error_message, timestamps |

---

## Table Specifications

### 1. departments

**Purpose:** Danh mục các phòng ban CTU quản lý tài liệu

```sql
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `id` — Primary key
- `code` — Unique code (ví dụ: "pdt", "hoc_vu", "ctsv", "thu_vien")
- `name` — Tên phòng ban (ví dụ: "Phòng Đào Tạo", "Phòng Học Vụ")
- `description` — Mô tả vai trò của phòng ban
- `is_active` — Phòng ban còn hoạt động không (soft delete)

**Indexes:**
```sql
CREATE INDEX idx_departments_code ON departments(code);
CREATE INDEX idx_departments_is_active ON departments(is_active);
```

**Sample Data:**
```sql
INSERT INTO departments (code, name, description) VALUES
('pdt', 'Phòng Đào Tạo', 'Quản lý quy chế đào tạo, chương trình học'),
('hoc_vu', 'Phòng Học Vụ', 'Quản lý thời khóa biểu, thi cử, điểm'),
('ctsv', 'Phòng Công Tác Sinh Viên', 'Quản lý học bổng, kỷ luật, hoạt động sinh viên'),
('thu_vien', 'Thư Viện', 'Quản lý quy định mượn/trả sách');
```

---

### 2. document_types

**Purpose:** Danh mục loại tài liệu

```sql
CREATE TABLE document_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `code` — Unique code: "noi_quy", "quy_trinh", "bieu_mau", "hoi_dap" (khớp với `DocumentType` enum trong `enums.py`)
- `name` — Tên hiển thị: "Nội Quy", "Quy Trình", "Biểu Mẫu", "Hỏi Đáp"

**Sample Data:**
```sql
INSERT INTO document_types (code, name, description) VALUES
('noi_quy',   'Nội Quy',  'Văn bản quy định, quy chế chính thức'),
('quy_trinh', 'Quy Trình','Hướng dẫn quy trình xử lý thủ tục'),
('bieu_mau',  'Biểu Mẫu', 'Mẫu đơn, form cần điền'),
('hoi_dap',   'Hỏi Đáp',  'Câu hỏi thường gặp');
```

### documents
**Purpose:** _[Logical document (stable across versions)]_

**Fields:**
- `id`, `document_key`, `title`, `department_id`, `document_type_id`
- `domain`, `audience`, `confidentiality`
- `created_at`, `updated_at`

**Relationships:**
- `department_id` → `departments.id`
- `document_type_id` → `document_types.id`

**Indexes:** _[document_key, department_id, document_type_id, confidentiality]_

---

### document_versions
**Purpose:** _[Version-specific metadata, status, dates]_

**Fields:**
- `id`, `document_id`, `version_key`, `version_label`, `title`, `code`
- `issued_date`, `effective_date`, `expiry_date`
- `is_latest`, `version_role`, `validity_status`, `collection_status`, `ocr_status`, `review_status`, `rag_status`
- `source_url`, `source_file`, `source_path`, `file_type`, `canonical_markdown_path`
- `language`, `citation_type`
- `checksum`, `metadata_hash`, `extra_metadata`
- `created_at`, `updated_at`

No `priority` or `chunking_strategy` field is stored on `document_versions` for the MVP. Retrieval ranking owns priority, and chunking is a fixed service-level behavior.

**Relationships:**
- `document_id` → `documents.id`
- Version replacement/amendment/supplement links are stored in `document_version_relationships`.

**Indexes:** _[document_id, is_latest, validity_status, review_status, rag_status, effective_date, expiry_date]_

**Status Enums:**
- `ocr_status`: _[not_started | processing | need_review | failed | done]_
- `review_status`: _[not_reviewed | reviewing | need_fix | approved | rejected]_
- `validity_status`: _[unchecked | unknown | valid | expired | replaced]_
- `rag_status`: _[not_indexed | chunked | embedded | indexed | published | deactivated | failed]_
- `collection_status`: _[collected | link_collected | downloaded | missing | failed]_

---

### document_chunks
**Purpose:** _[Chunk text, citation metadata, Qdrant point ID]_

**Fields:**
- `id`, `document_version_id`, `parent_id`, `chunk_index`, `chunk_level`
- `heading_path`, `section_title`, `content`
- `page_start`, `page_end`, `token_count`, `checksum`
- `qdrant_point_id`, `index_status`
- `created_at`, `updated_at`

**Relationships:**
- `document_version_id` → `document_versions.id`
- `parent_id` → `document_chunks.id` (self-reference for parent-child)

**Indexes:** _[document_version_id, parent_id, qdrant_point_id, index_status]_

---

### assets
**Purpose:** _[Forms, biểu mẫu, attachments]_

**Fields:**
- `id`, `asset_key`, `asset_type`, `title`, `file_path`, `file_type`, `download_url`
- `checksum`, `validity_status`, `is_latest`, `review_status`, `rag_status`
- `created_at`, `updated_at`

**Indexes:** _[asset_key, asset_type, validity_status, is_latest]_

---

### document_assets
**Purpose:** _[Many-to-many relationship: document_versions ↔ assets]_

**Fields:**
- `document_version_id`, `asset_id`, `relation_type`
- `required`, `required_when`, `display_order`
- `created_at`, `updated_at`

**Primary Key:** _[document_version_id, asset_id]_

**Relationships:**
- `document_version_id` → `document_versions.id`
- `asset_id` → `assets.id`

---

### ingestion_jobs
**Purpose:** _[Track OCR/chunk/embed/index job progress]_

**Fields:**
- `id`, `document_version_id`, `current_stage`, `tool_name`
- `total_chunks`, `processed_chunks`, `error_message`
- `started_at`, `finished_at`, `created_by`
- `created_at`, `updated_at`

**Relationships:**
- `document_version_id` → `document_versions.id`

**Indexes:** _[document_version_id]_

---

## Document Governance Rules

### Production RAG Hard Filter
_[Mô tả 6 conditions: approved, valid, published, public, effective_date, expiry_date]_

Publish eligibility also requires `ocr_status = 'done'`; there is no `ocr_status = 'not_required'` value.

### Version Management Rules
_[is_latest usage, replaced documents, expired documents]_

### Metadata Validation Rules
_[Required fields, business rules, date logic]_

---

## Migration Strategy
_[Alembic cho SQLAlchemy, migration files, rollback plan]_

---

**Status:** Skeleton — Cần điền chi tiết fields và constraints  
**Priority:** P0 (Critical for MVP)



---

### 3. documents

**Purpose:** Logical document (stable identity across versions)

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    document_key VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    document_type_id INTEGER REFERENCES document_types(id),
    domain VARCHAR(100),
    audience VARCHAR(100),
    confidentiality VARCHAR(50) DEFAULT 'public',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `document_key` — Unique identifier (e.g., "quy-che-dao-tao-2024")
- `title` — Tên tài liệu chính (không đổi qua versions)
- `department_id` — FK: Phòng ban quản lý
- `document_type_id` — FK: Loại tài liệu
- `domain` — Lĩnh vực (e.g., "dao_tao", "hoc_vu", "hoc_bong")
- `audience` — Đối tượng (e.g., "sinh_vien", "giang_vien", "admin")
- `confidentiality` — Enum: "public", "internal", "restricted"

**Indexes:**
```sql
CREATE INDEX idx_documents_key ON documents(document_key);
CREATE INDEX idx_documents_department ON documents(department_id);
CREATE INDEX idx_documents_type ON documents(document_type_id);
CREATE INDEX idx_documents_confidentiality ON documents(confidentiality);
```

---

### 4. document_versions

**Purpose:** Specific version của document với dates và governance status

```sql
CREATE TABLE document_versions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    version_key VARCHAR(255) UNIQUE NOT NULL,
    version_label VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    code VARCHAR(100),
    issued_date DATE,
    effective_date DATE NOT NULL,
    expiry_date DATE,
    
    is_latest BOOLEAN DEFAULT FALSE,
    version_role VARCHAR(50) DEFAULT 'base',
    validity_status VARCHAR(50) DEFAULT 'unchecked',
    collection_status VARCHAR(50) DEFAULT 'collected',
    ocr_status VARCHAR(50) DEFAULT 'not_started',
    review_status VARCHAR(50) DEFAULT 'not_reviewed',
    rag_status VARCHAR(50) DEFAULT 'not_indexed',
    
    source_url TEXT,
    source_file TEXT,
    source_path TEXT,
    file_type VARCHAR(50),
    canonical_markdown_path TEXT,
    
    accessed_date DATE,
    language VARCHAR(10) DEFAULT 'vi',
    citation_type VARCHAR(50) DEFAULT 'page',
    
    checksum VARCHAR(64),
    metadata_hash VARCHAR(64),
    extra_metadata JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Key Fields:**

**Identity:**
- `version_key` — Unique identifier (e.g., "quy-che-dao-tao-2024-v1.0")
- `version_label` — Human-readable version (e.g., "1.0", "2.1")
- `title` — Tên version cụ thể (có thể khác với document.title)
- `code` — Mã văn bản chính thức (e.g., "QĐ 123/2024/ĐHCT")

**Dates:**
- `issued_date` — Ngày ban hành
- `effective_date` — Ngày có hiệu lực (required)
- `expiry_date` — Ngày hết hiệu lực (NULL = vô thời hạn)

**Governance Status:**
- `is_latest` — Version mới nhất của document (chỉ 1 version có TRUE)
- `version_role` — Enum: "base", "replacement", "amendment", "supplement"
- `validity_status` — Enum: "unchecked", "unknown", "valid", "expired", "replaced"
- `collection_status` — Enum: "link_collected", "collected", "downloaded", "missing", "failed"
- `ocr_status` — Enum: "not_started", "processing", "need_review", "done", "failed"
- `review_status` — Enum: "not_reviewed", "reviewing", "need_fix", "approved", "rejected"
- `rag_status` — Enum: "not_indexed", "chunked", "embedded", "indexed", "published", "deactivated", "failed"

**Source Tracking:**
- `source_url` — URL gốc (nếu download từ web)
- `source_file` — Tên file gốc (PDF, DOCX)
- `source_path` — Đường dẫn file gốc trong storage
- `canonical_markdown_path` — Đường dẫn Markdown đã review trong `01_Dataset/`

**Citation Config:**
- `citation_type` — "page" (default), "section", "paragraph"

**Version Management:**
- `version_role` — Vai trò của version: base, replacement, amendment, supplement
- Version relationships live in `document_version_relationships`, not a single self-reference column.
- `checksum` — SHA256 của file gốc
- `metadata_hash` — Hash của YAML metadata (detect changes)

**Indexes:**
```sql
CREATE INDEX idx_docver_document ON document_versions(document_id);
CREATE INDEX idx_docver_version_key ON document_versions(version_key);
CREATE INDEX idx_docver_is_latest ON document_versions(is_latest);
CREATE INDEX idx_docver_dates ON document_versions(effective_date, expiry_date);
CREATE INDEX idx_docver_status ON document_versions(review_status, validity_status, rag_status);
CREATE INDEX idx_docver_confidentiality ON document_versions USING btree ((SELECT confidentiality FROM documents WHERE id = document_versions.document_id));
```

---

### 5. document_version_relationships

**Purpose:** Structured version links for replacement, amendment, and supplement retrieval logic.

```sql
CREATE TABLE document_version_relationships (
    id SERIAL PRIMARY KEY,
    source_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    target_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(source_version_id, target_version_id, relation_type)
);
```

**Fields:**
- `source_version_id` — Newer/source version, for example amendment or supplement.
- `target_version_id` — Target/base version.
- `relation_type` — Enum: "replaces", "replaced_by", "amends", "amended_by", "supplements", "supplemented_by".

**Retrieval rule:**
- `replaces`: use replacement and exclude replaced old version when old version has `validity_status = "replaced"`.
- `amends` / `supplements`: include both valid base version and valid amendment/supplement.
- `is_latest` remains ranking preference only.

**Indexes:**
```sql
CREATE INDEX idx_docver_rel_source ON document_version_relationships(source_version_id, relation_type);
CREATE INDEX idx_docver_rel_target ON document_version_relationships(target_version_id, relation_type);
```

---

### 6. document_chunks

**Purpose:** Parent-child chunks với page markers và Qdrant point IDs

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES document_chunks(id),
    
    chunk_index INTEGER NOT NULL,
    chunk_level VARCHAR(20) DEFAULT 'child',
    heading_path TEXT,
    section_title TEXT,
    content TEXT NOT NULL,
    
    page_start INTEGER,
    page_end INTEGER,
    token_count INTEGER,
    checksum VARCHAR(64),
    
    qdrant_point_id VARCHAR(255),
    embedding_status VARCHAR(50) DEFAULT 'pending',
    index_status VARCHAR(50) DEFAULT 'not_indexed',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(document_version_id, chunk_index)
);
```

**Fields:**

**Hierarchy:**
- `parent_id` — FK: Parent chunk (NULL for parent-level chunks)
- `chunk_level` — Enum: "parent", "child"

**Structure:**
- `chunk_index` — Sequential index trong document version (0, 1, 2, ...)
- `heading_path` — Heading hierarchy (e.g., "Chương 1 > Điều 3 > Khoản 2")
- `section_title` — Tiêu đề của parent section
- `content` — Chunk text (include page markers for citation)

**Citation:**
- `page_start` — Start page number
- `page_end` — End page number (nếu span multiple pages)
- `token_count` — Token count (để check context limit)

**Indexing:**
- `qdrant_point_id` — UUID của point trong Qdrant
- `embedding_status` — Enum: "pending", "embedded", "failed", "skipped" (khớp `EmbeddingStatus` trong `enums.py`)
- `index_status` — Enum: "not_indexed", "indexed", "deactivated", "failed" (khớp `QdrantStatus` trong `enums.py`)

**Indexes:**
```sql
CREATE INDEX idx_chunks_version ON document_chunks(document_version_id);
CREATE INDEX idx_chunks_parent ON document_chunks(parent_id);
CREATE INDEX idx_chunks_qdrant ON document_chunks(qdrant_point_id);
CREATE INDEX idx_chunks_embedding_status ON document_chunks(embedding_status);
CREATE INDEX idx_chunks_index_status ON document_chunks(index_status);
CREATE INDEX idx_chunks_content_fts ON document_chunks USING gin(to_tsvector('simple', content));
```




---

### 7. assets

**Purpose:** Forms, templates, downloadable files

```sql
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    asset_key VARCHAR(255) UNIQUE NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    
    file_path TEXT,
    file_type VARCHAR(50),
    download_url TEXT,
    checksum VARCHAR(64),
    
    validity_status VARCHAR(50) DEFAULT 'valid',
    is_latest BOOLEAN DEFAULT TRUE,
    review_status VARCHAR(50) DEFAULT 'approved',
    rag_status VARCHAR(50) DEFAULT 'published',
    
    effective_date DATE,
    expiry_date DATE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `asset_key` — Unique identifier (e.g., "don-xin-hoc-bong-2024")
- `asset_type` — Enum: "form", "template", "guide", "attachment"
- `file_path` — Path trong storage
- `download_url` — Public download URL
- `validity_status`, `review_status`, `rag_status` — Governance fields (similar to document_versions)

**Indexes:**
```sql
CREATE INDEX idx_assets_key ON assets(asset_key);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_status ON assets(validity_status, rag_status);
```

---

### 8. document_assets

**Purpose:** Many-to-many relationship giữa document_versions và assets

```sql
CREATE TABLE document_assets (
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    
    relation_type VARCHAR(50) DEFAULT 'related',
    required BOOLEAN DEFAULT FALSE,
    required_when TEXT,
    display_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (document_version_id, asset_id)
);
```

**Fields:**
- `relation_type` — Enum: "required_form", "reference", "supplement", "guide"
- `required` — Asset bắt buộc cho procedure không
- `required_when` — Điều kiện khi nào asset required (text hoặc JSON)
- `display_order` — Thứ tự hiển thị trong UI

**Indexes:**
```sql
CREATE INDEX idx_docassets_version ON document_assets(document_version_id);
CREATE INDEX idx_docassets_asset ON document_assets(asset_id);
```

---

### 9. ingestion_jobs

**Purpose:** Track OCR/chunking/embedding/indexing jobs

```sql
CREATE TABLE ingestion_jobs (
    id SERIAL PRIMARY KEY,
    document_version_id INTEGER REFERENCES document_versions(id) ON DELETE CASCADE,
    
    current_stage VARCHAR(100),
    tool_name VARCHAR(100),
    
    total_chunks INTEGER,
    processed_chunks INTEGER DEFAULT 0,
    error_message TEXT,
    
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_by VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `current_stage` — Human-readable current step (e.g., "Running PaddleOCR", "Embedding chunks")
- `tool_name` — Tool used (e.g., "ocr-pvl", "langchain", "bge-m3")
- `total_chunks`, `processed_chunks` — Progress tracking
- `error_message` — Error details nếu failed

**Indexes:**
```sql
CREATE INDEX idx_jobs_version ON ingestion_jobs(document_version_id);
CREATE INDEX idx_jobs_created_at ON ingestion_jobs(created_at DESC);
```

---

## Status Enum Definitions

### ocr_status

| Value | Meaning |
|-------|---------|
| `not_started` | Chưa bắt đầu OCR |
| `processing` | Đang chạy OCR |
| `need_review` | OCR xong, cần human review |
| `done` | OCR/parser extraction completed and validated |
| `failed` | OCR failed |

`ocr_status` intentionally has no `not_required` value. Native Markdown/text inputs should still become `done` after parser validation.

### review_status

| Value | Meaning |
|-------|---------|
| `not_reviewed` | Chưa review |
| `reviewing` | Đang review |
| `need_fix` | Cần sửa lại |
| `approved` | Đã approved |
| `rejected` | Rejected (không dùng) |

### validity_status

| Value | Meaning |
|-------|---------|
| `unchecked` | Chưa kiểm tra hiệu lực |
| `unknown` | Đã kiểm tra nhưng chưa xác định được |
| `valid` | Valid và có hiệu lực |
| `expired` | Hết hiệu lực |
| `replaced` | Đã bị thay thế toàn bộ |

### rag_status

| Value | Meaning |
|-------|---------|
| `not_indexed` | Chưa index |
| `chunked` | Đã chunk nhưng chưa embed |
| `embedded` | Đã embed nhưng chưa upsert Qdrant |
| `indexed` | Đã index vào Qdrant |
| `published` | Published và searchable |
| `deactivated` | Deactivated (soft delete from Qdrant) |
| `failed` | Indexing failed |

### collection_status

| Value | Meaning |
|-------|---------|
| `collected` | Đã thu thập file |
| `link_collected` | Chỉ thu thập link |
| `downloaded` | Đã download file |
| `missing` | File missing |
| `failed` | Download failed |

---

## Indexes và Constraints

### Composite Indexes

```sql
-- Fast lookup: published documents với filters
CREATE INDEX idx_published_docs ON document_versions(
    review_status, validity_status, rag_status, effective_date, expiry_date
) WHERE review_status = 'approved' 
    AND validity_status = 'valid' 
    AND rag_status = 'published';

-- Fast lookup for version ranking only, not a hard retrieval filter
CREATE INDEX idx_latest_valid ON document_versions(document_id, is_latest)
WHERE is_latest = TRUE AND validity_status = 'valid';

-- Full-text search on chunks
CREATE INDEX idx_chunks_fts ON document_chunks 
USING gin(to_tsvector('simple', content));
```

### Constraints

```sql
-- Only one is_latest per document
CREATE UNIQUE INDEX idx_one_latest_per_doc 
ON document_versions(document_id) 
WHERE is_latest = TRUE;

-- effective_date must be before or equal to expiry_date
ALTER TABLE document_versions 
ADD CONSTRAINT chk_dates_order 
CHECK (expiry_date IS NULL OR effective_date <= expiry_date);

-- chunk_level must be 'parent' or 'child'
ALTER TABLE document_chunks 
ADD CONSTRAINT chk_chunk_level 
CHECK (chunk_level IN ('parent', 'child'));
```

---

## Document Governance Rules

### Publish Eligibility

Document version chỉ được publish (rag_status = 'published') khi:

```sql
ocr_status = 'done'
AND review_status = 'approved'
AND validity_status = 'valid'
AND (SELECT confidentiality FROM documents WHERE id = document_id) = 'public'
AND effective_date <= CURRENT_DATE
AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
```

### Retrieval Filter

RAG service chỉ retrieve chunks từ documents thỏa:

```sql
review_status = 'approved'
AND validity_status = 'valid'
AND rag_status = 'published'
AND (SELECT confidentiality FROM documents WHERE id = document_id) = 'public'
AND effective_date <= CURRENT_DATE
AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
```

**Note:** `is_latest` là **ranking preference**, không phải hard filter. Older valid documents vẫn searchable, especially when they are amended or supplemented.

### Version Management

Khi publish version mới:

1. Set `is_latest = FALSE` cho versions cũ nếu version mới là version ưu tiên.
2. Set `is_latest = TRUE` cho version mới nếu phù hợp.
3. Nếu version mới thay thế toàn bộ bản cũ:
   - Insert relationship `relation_type = 'replaces'`.
   - Set old version `validity_status = 'replaced'`.
   - Set old version `rag_status = 'deactivated'`.
4. Nếu version mới chỉ sửa đổi/bổ sung một phần:
   - Insert relationship `relation_type = 'amends'` hoặc `relation_type = 'supplements'`.
   - Keep base version `validity_status = 'valid'` if still applicable.
   - Retrieval must include both base and amendment/supplement when relevant.

---

## References

- **Architecture:** `03_SYSTEM_ARCHITECTURE.md`
- **Module Spec:** `04_MODULE_SPEC.md`
- **ERD Diagram:** `../../diagrams/mermaid/erd.mmd`
- **Implementation:** `.docs/DATABASE_SCHEMA.md`

---

**Next:** [06. Đặc Tả API →](06_API_SPEC.md)
