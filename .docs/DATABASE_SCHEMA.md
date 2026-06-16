# Database Schema Guide

## Current phase rule

Start with 9 core tables only:

1. `departments`
2. `document_types`
3. `documents`
4. `document_versions`
5. `document_version_relationships`
6. `document_chunks`
7. `assets`
8. `document_assets`
9. `ingestion_jobs`

Do not add `procedures`, `procedure_steps`, `eligibility_rules`, `chat_history`, `RBAC`, or `audit` until the feature requires them.

## Relationship summary

```text
departments/document_types
→ documents
→ document_versions
→ document_chunks

document_versions
→ document_version_relationships
→ document_versions

document_versions
→ document_assets
→ assets

document_versions
→ ingestion_jobs
```

## Table responsibilities

| Table               | Purpose                                               |
| ------------------- | ----------------------------------------------------- |
| `departments`       | CTU unit/office managing a document                   |
| `document_types`    | Type catalog: regulation, procedure, form, faq        |
| `documents`         | Stable logical document across versions               |
| `document_versions` | Version, effective date, validity, review, RAG status |
| `document_version_relationships` | Replacement/amendment/supplement links between versions |
| `document_chunks`   | Chunk text, citation metadata, Qdrant point id        |
| `assets`            | Forms/files/download links                            |
| `document_assets`   | Relationship between document version and asset       |
| `ingestion_jobs`    | OCR/chunk/embed/index job tracking                    |

## Suggested important fields

### departments

```text
id
code
name
description
is_active
created_at
updated_at
```

### document_types

```text
id
code
name
description
is_active
created_at
updated_at
```

### documents

```text
id
document_key
title
department_id
document_type_id
domain
audience
confidentiality
created_at
updated_at
```

### document_versions

```text
id
document_id
version_key
version_label
title
code
issued_date
effective_date
expiry_date
is_latest
version_role
validity_status
collection_status
ocr_status
review_status
rag_status
source_url
source_file
source_path
file_type
canonical_markdown_path
accessed_date
language
citation_type
checksum
metadata_hash
extra_metadata
created_at
updated_at
```

`version_role` uses:

```text
base | replacement | amendment | supplement
```

Do not treat `is_latest` as a retrieval hard filter. A base version can remain valid and retrievable when it is amended or supplemented by a newer version.

### document_version_relationships

Use this table to query version governance. Keep original YAML relationship arrays in `document_versions.extra_metadata` if useful, but retrieval should use structured relationship rows.

```text
id
source_version_id
target_version_id
relation_type
created_at
updated_at
```

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

```text
id
document_version_id
parent_id
chunk_index
chunk_level
heading_path
section_title
content
page_start
page_end
token_count
checksum
qdrant_point_id
index_status
created_at
updated_at
```

### assets

```text
id
asset_key
asset_type
title
file_path
file_type
download_url
checksum
validity_status
is_latest
review_status
rag_status
created_at
updated_at
```

### document_assets

```text
document_version_id
asset_id
relation_type
required
required_when
display_order
created_at
updated_at
```

### ingestion_jobs

```text
id
document_version_id
current_stage
tool_name
total_chunks
processed_chunks
error_message
started_at
finished_at
created_by
created_at
updated_at
```

## Status enum suggestions

```text
ocr_status: not_started | processing | need_review | failed | done
review_status: not_reviewed | reviewing | need_fix | approved | rejected
validity_status: unchecked | unknown | valid | expired | replaced
version_role: base | replacement | amendment | supplement
rag_status: not_indexed | chunked | embedded | indexed | published | deactivated | failed
collection_status: collected | link_collected | downloaded | missing | failed
```

## Version governance rules

Use these rules before implementing retrieval:

```text
1. Replacement:
   - old version: validity_status = replaced, rag_status = deactivated
   - new version: version_role = replacement, relation replaces -> old version
   - retrieval must exclude the replaced old version

2. Amendment:
   - base version remains validity_status = valid if still applicable
   - amendment version uses version_role = amendment, relation amends -> base version
   - retrieval should include both base and amendment when either is relevant

3. Supplement:
   - base version remains validity_status = valid if still applicable
   - supplement version uses version_role = supplement, relation supplements -> base version
   - retrieval should include both base and supplement when either is relevant

4. is_latest:
   - ranking preference only
   - never the only condition for retrieval eligibility
```
