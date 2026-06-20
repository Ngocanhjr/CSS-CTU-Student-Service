`docker compose exec postgres psql -U ct239h -d ctu_student_service -c "CREATE SCHEMA IF NOT EXISTS css AUTHORIZATION ct239h;"`
nếu không có schema hoặc đã tạo postgres trước đó
`docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dn"`
kiểm tra schema

docker compose exec postgres psql -U ct239h -d ctu_student_service -c "\dt css.*"

# Run

`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1`

python -m pytest

- [x] PostgreSQL chạy được
- [x] Chunk Pydantic model
  - app/schemas/enums.py
  - app/schemas/documents.py
  - app/schemas/assets.py
  - app/schemas/chunks.py
  - app/schemas/rag.py re-export nếu cần
- [ ] Markdown chunker
- [ ] Preview chunk từ file OCR thật
- [x] Chốt schema fields
- [x] SQLAlchemy models
- [ ] Alembic migration chạy được
- [ ] Insert metadata/chunks vào PostgreSQL
- [ ] Embed child chunks
- [ ] Upsert Qdrant

---

- [x] 1. PostgreSQL chạy được
  - Container healthy
  - Kết nối được ctu_student_service
  - Schema `css` tồn tại

## Quy ước key và id

```text
Trong PostgreSQL:
- id là khóa kỹ thuật nội bộ.
- document_id, document_version_id, asset_id là foreign key nội bộ.

Trong YAML/Pydantic/RAG payload:
- document_key là mã ổn định của tài liệu.
- version_key là mã ổn định của version.
- asset_key là mã ổn định của asset.
```

Không dùng `document_id` / `version_id` trong Pydantic metadata nếu đã chọn quy ước `*_key`.

- [x] 2. Xác định draft fields cho chunk
  - document_key
  - version_key
  - chunk_id
  - parent_chunk_id
  - chunk_type
  - content
  - heading_path
  - page_start
  - page_end
  - chunk_index
  - token_count

- [x] 3. Tạo Chunk Pydantic model
  - Validate field bắt buộc
  - Validate page và chunk_index
  - Phân biệt parent/child chunk

    ```bash
    Pydantic Chunk
        ↓ chuyển đổi
    LangChain Document
        ↓
    Embedding / Qdrant
    ```

    - Pydantic Chunk: cấu trúc dữ liệu chuẩn của hệ thống.
    - LangChain Document: định dạng truyền dữ liệu vào LangChain.
    - SQLAlchemy DocumentChunk: định dạng lưu PostgreSQL.

- [ ] 4. Viết Markdown chunker
  - Đọc heading Markdown
  - Nhận diện <!-- page: N -->
  - Tạo parent chunk theo section
  - Chia child chunk theo kích thước
  - Giữ metadata kế thừa

- [ ] 5. Preview chunk từ file OCR thật
  - In ra JSON hoặc Markdown
  - Kiểm tra mất nội dung
  - Kiểm tra heading_path
  - Kiểm tra page_start/page_end
  - Kiểm tra chunk quá ngắn hoặc quá dài

- [ ] 6. Chốt schema fields
  - Field lưu trong PostgreSQL
  - Field lưu trong Qdrant payload
  - Field chỉ dùng tạm trong pipeline

- [ ] 7. Tạo SQLAlchemy models
  - documents
  - document_versions
  - document_version_status
  - document_version_relationships
  - document_chunks
  - assets
  - document_assets
  - ingestion_jobs

- [ ] 8. Tạo và chạy Alembic migration
  - alembic revision --autogenerate
  - alembic upgrade head
  - Kiểm tra bảng trong css.\*

- [ ] 9. Insert metadata và chunks vào PostgreSQL
  - Insert document
  - Insert document version
  - Insert/update document version status
  - Insert parent/child chunks
  - document_version_status.rag_status = not_indexed

- [ ] 10. Embed child chunks
  - Dùng thống nhất BAAI/bge-m3
  - Không embed parent chunk ở giai đoạn đầu
  - Lưu embedding_model và embedding_version

- [ ] 11. Upsert vào Qdrant
  - Vector của child chunk
  - Payload có thể chứa PostgreSQL IDs để join nhanh
  - Payload nên chứa stable keys (`document_key`, `version_key`, `chunk_id`) để trace/audit
  - Không xem Qdrant là nguồn metadata chính

- [ ] 12. Cập nhật trạng thái sau indexing
  - Thành công: document_version_status.rag_status = indexed/published
  - Thất bại: document_version_status.rag_status = failed
  - Lưu error_message hoặc ingestion job log

### departments

- [ ] id
- [ ] code
- [ ] name
- [ ] description
- [ ] is_active
- [ ] created_at
- [ ] updated_at

### document_types

- [ ] id
- [ ] code
- [ ] name
- [ ] description
- [ ] is_active
- [ ] created_at
- [ ] updated_at

### documents

- [x] id
- [ ] document_key
- [x] title
- [x] department_id
- [x] document_type_id
- [x] domain
- [x] audience
- [ ] created_at
- [ ] updated_at

### document_versions

- [ ] id
- [x] document_id
- [ ] title
- [x] version_key
- [x] version_label
- [x] version_role
- [x] code
- [x] issued_date
- [x] effective_date
- [x] expiry_date
- [x] is_latest
- [x] source_url
- [x] source_file
- [x] source_path
- [x] file_type
- [ ] canonical_markdown_path
- [x] accessed_date
- [x] language
- [x] citation_type
- [x] checksum
- [ ] metadata_hash
- [ ] extra_metadata
- [ ] created_at
- [ ] updated_at

`version_role` uses:

```text
base | replacement | amendment | supplement
```

Do not treat `is_latest` as a retrieval hard filter. A base version can remain valid and retrievable when it is amended or supplemented by a newer version.

### document_version_status

Bảng này lưu snapshot trạng thái hiện tại của một dòng `document_versions`. Giữ các field này ngoài `document_versions` để không trộn định danh/version với trạng thái workflow.

- [ ] document_version_id
- [x] validity_status
- [x] collection_status
- [x] ocr_status
- [x] review_status
- [x] rag_status
- [x] status_note
- [ ] updated_by
- [ ] created_at
- [ ] updated_at

Giá trị mặc định:

```text
validity_status   = unchecked
collection_status = collected
ocr_status        = not_started
review_status     = not_reviewed
rag_status        = not_indexed
```

Điều kiện publish:

```text
ocr_status = done
review_status = approved
validity_status = valid
rag_status = published
```

### document_version_relationships

Use this table to query version governance. Keep original YAML relationship arrays in `document_versions.extra_metadata` if useful, but retrieval should use structured relationship rows.

- [ ] id
- [ ] source_version_id
- [ ] target_version_id
- [ ] relation_type
- [ ] created_at
- [ ] updated_at

Recommended relation direction:

```text
replacement version --replaces--> old version
amendment version   --amends--> old/base version
supplement version  --supplements--> old/base version
old/base version    --replaced_by/amended_by/supplemented_by--> newer version
```

Recommended SQL indexes:

```sql
CREATE INDEX idx_version_relationships_source
ON document_version_relationships(source_version_id, relation_type);

CREATE INDEX idx_version_relationships_target
ON document_version_relationships(target_version_id, relation_type);
```

### document_chunks

- [x] id
- [ ] document_version_id
- [ ] parent_id
- [x] chunk_index
- [ ] chunk_level
- [ ] heading_path
- [ ] section_title
- [ ] content
- [ ] page_start
- [ ] page_end
- [x] token_count
- [ ] checksum ?
- [ ] qdrant_point_id
- [ ] index_status
- [ ] created_at
- [ ] updated_at

### assets

- [ ] id
- [x] asset_key
- [x] asset_type
- [x] title
- [x] file_path
- [x] file_type
- [x] download_url
- [x] checksum
- [x] validity_status
- [x] is_latest
- [x] review_status
- [x] rag_status
- [ ] created_at
- [ ] updated_at

### document_assets

- [x] document_version_id
- [x] asset_id
- [x] relation_type
- [x] required
- [x] required_when
- [x] display_order
- [ ] created_at
- [ ] updated_at

### ingestion_jobs

- [ ] id
- [ ] document_version_id
- [ ] job_type
- [ ] status
- [ ] current_stage
- [ ] tool_name
- [ ] total_chunks
- [ ] processed_chunks
- [ ] error_message
- [ ] started_at
- [ ] finished_at
- [ ] created_by
- [ ] created_at
- [ ] updated_at

`ingestion_jobs.status` chỉ là trạng thái chạy job, ví dụ `pending`, `running`, `done`, `failed`, hoặc `cancelled`. Trạng thái workflow hiện tại của tài liệu phải nằm trong `document_version_status`.
