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
