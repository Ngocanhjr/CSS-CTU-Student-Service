# Guild Implement Checklist

File này dùng để theo dõi từng guide làm gì, guide nào đã xong, guide nào còn phải quay lại.

Quy ước trạng thái:

- `[x]` Đã xong hoặc đã chốt ở mức tài liệu/schema chính.
- `[~]` Đang làm hoặc cần rà lại khi code đổi.
- `[ ]` Chưa làm.

## Trạng Thái Tổng Quan

- [x] Chốt schema 9 bảng.

- [x] Bỏ `validity_status` khỏi DB/YAML metadata chính.

- [x] Dùng `signer_name`, không dùng `signer`.

- [x] Dùng `responsible_department` dạng `list[str]` trong YAML/schema, map sang `document_recipients`.

- [x] Bỏ `version_label` khỏi YAML/schema/DB.

- [x] Chốt `checksum` bắt buộc cho `document_versions`, `String(64), nullable=False`.

- [x] Chốt `assets` chỉ giữ `asset_key`, `title`, `asset_type`, `url`, `checksum`, `created_at`.

- [x] Chốt `document_assets` PK gồm `document_version_id`, `asset_id`, `relation_type`.

- [x] Chốt runtime settings dùng default trong `settings_loader.py`, không dùng `or 900` rải rác.

- [x] Baseline Alembic mới cho DB trống đã tạo, cần xác nhận `upgrade head` và đủ 9 bảng.

- [ ] Postgres ingestion repository theo schema 9 bảng.

- [ ] Chunking nối với runtime settings.

- [ ] Pre-chunk structural parsing trước chunking.

- [ ] Pipeline end-to-end.

- [ ] Qdrant/vectorstore/retrieval/RAG answer chain.

## Checklist Theo Guide

| Trạng thái | Guide                                               | Làm gì                         | Ghi chú                                                                                            |
| ---------- | --------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------- |
| \[x\]      | `00_ENUM_GUILD.md`                                  | Quy ước enum/schema value      | Rà lại nếu thêm enum mới.                                                                          |
| \[x\]      | `01_RAG_SCHEMA_IMPLEMENTATION_GUIDE.md`             | Schema metadata tổng quan      | Đã chốt bỏ field cũ, dùng `signer_name`, `responsible_department` list.                            |
| \[\~\]     | `02_SCHEMA_EXPORT_TEST_VALIDATOR_GUIDE.md`          | Test/export schema             | Cần chạy lại sau khi schema ổn.                                                                    |
| \[x\]      | `03_SQLALCHEMY_9_TABLES_GUIDE.md`                   | SQLAlchemy models 9 bảng       | Đã chốt contract chính.                                                                            |
| \[x\]      | `04_ALEMBIC_MIGRATION_GUIDE.md`                     | Alembic setup/migration        | Với DB trống dùng baseline mới; xác nhận migration mới trước khi tiếp tục.                         |
| \[x\]      | `05_DATABASE_TEST_AND_SMOKE_INSERT_GUIDE.md`        | Smoke insert DB                | Làm sau khi `alembic upgrade head` pass.                                                           |
| \[\~\]     | `06_GiaiDoanTiepTheo.md`                            | Roadmap tổng                   | Có thể cập nhật sau khi xong DB baseline.                                                          |
| \[\~\]     | `07_DETAILED_RAG_INGESTION_IMPLEMENTATION_GUIDE.md` | Ingestion pipeline tổng thể    | Là orchestration, làm sau Guide 9/10/12 cơ bản.                                                    |
| \[\~\]     | `08_PART_A_DB_SCHEMA_CONTRACT_GUIDE.md`             | DB/schema contract             | Đã chốt 9 bảng và nullable chính.                                                                  |
| \[x\]      | `09_PART_B_MARKDOWN_READER_GUIDE.md`                | Markdown reader/frontmatter    | Làm trước repository để có `DocumentMetadata` sạch từ YAML/body.                                   |
| \[ x\]     | `09A_PRE_CHUNK_PARSING_NORMALIZATION_GUIDE.md`      | Pre-chunk structural parsing   | Làm sau Guide 9, trước Guide 10 để page/heading/item/table/code đúng trước chunk.                  |
| \[ \]      | `10_PART_C_HEADING_AWARE_CHUNKER_GUIDE.md`          | Heading-aware chunker          | Làm sau Guide 9 để biến body thành parent/child chunks.                                            |
| \[ x\]     | `10A_PART_C_PAGE_MARKER_HELPER_GUIDE.md`            | Page marker helper             | Làm cùng chunking nếu cần page range.                                                              |
| \[ \]      | `10B_PART_C_PAGE_AWARE_CHUNKER_DECISIONS.md`        | Quyết định page-aware chunking | Rà khi xử lý page markers.                                                                         |
| \[ \]      | `11_PART_D_CHUNK_PREVIEW_GUIDE.md`                  | Preview chunks                 | Làm sau chunker cơ bản.                                                                            |
| \[ \]      | `12_PART_E_POSTGRES_INGESTION_REPOSITORY_GUIDE.md`  | Repository ghi PostgreSQL      | Làm sau Guide 9/10 để có metadata + chunks làm input thật.                                         |
| \[ \]      | `13_PART_F_PIPELINE_ORCHESTRATION_GUIDE.md`         | Orchestration pipeline         | Làm sau reader/chunker/repository.                                                                 |
| \[ \]      | `14_PART_G_EMBEDDING_GUIDE.md`                      | Embedding                      | Làm sau chunks ổn.                                                                                 |
| \[ \]      | `14A_EMBEDDING_RETRIEVAL_SMOKE_TEST_GUIDE.md`       | Smoke embedding/retrieval      | Làm sau Qdrant insert/search.                                                                      |
| \[ \]      | `15_PART_H_QDRANT_VECTORSTORE_GUIDE.md`             | Qdrant vectorstore             | Làm sau embedding model/payload ổn.                                                                |
| \[ \]      | `16_PART_I_RETRIEVAL_GUIDE.md`                      | Retrieval                      | Làm sau Qdrant search pass.                                                                        |
| \[ \]      | `17_PART_J_E2E_TEST_AND_SMOKE_GUIDE.md`             | E2E smoke                      | Làm sau pipeline + DB + Qdrant pass.                                                               |
| \[ \]      | `18_PART_K_RAG_ANSWER_CHAIN_GUIDE.md`               | Answer chain                   | Làm cuối sau retrieval.                                                                            |
| \[\~\]     | `19_MIGRATE_10_TO_9_TABLES_GUIDE.md`                | Migrate 10 bảng sang 9 bảng    | Đã cập nhật cho schema chốt. Với DB trống, dùng baseline mới thay vì migrate diff.                 |
| \[x\]      | `20_DOCKER_POSTGRES_QDRANT_RESET_GUIDE.md`          | Reset Docker/Postgres/Qdrant   | Đã dùng khi reset DB trống.                                                                        |
| \[x\]      | `21_RUNTIME_SETTINGS_GUIDE.md`                      | Runtime settings               | Đã thống nhất theo code: `child_chunk_size=1000`, `child_chunk_overlap=100`, `get_rag_settings()`. |
| \[\~\]     | `db.md`                                             | Ghi chú DB/key mapping         | Rà lại sau khi baseline DB pass.                                                                   |

## Việc Nên Làm Tiếp

- [x] 1\. Xác nhận DB baseline:

```cmd
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\alembic.exe upgrade head
..\..\.venv\Scripts\alembic.exe current
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dt css.*"
```

- [x] 2\. Nếu có đúng 9 bảng, làm `05_DATABASE_TEST_AND_SMOKE_INSERT_GUIDE.md`.

- [ ] 3\. Làm `09_PART_B_MARKDOWN_READER_GUIDE.md` để đọc Markdown, tách frontmatter/body, parse `DocumentMetadata`.

- [ ] 4\. Làm `09A_PRE_CHUNK_PARSING_NORMALIZATION_GUIDE.md` để page-aware structural parsing trước khi chunk.

- [ ] 5\. Làm `10_PART_C_HEADING_AWARE_CHUNKER_GUIDE.md`, kèm `10A`/`10B` nếu cần page marker/page-aware logic.

- [ ] 6\. Làm `12_PART_E_POSTGRES_INGESTION_REPOSITORY_GUIDE.md` để ghi `DocumentMetadata` + chunks vào PostgreSQL.

- [ ] 7\. Khi reader/chunker/repository ổn, quay lại `07_DETAILED_RAG_INGESTION_IMPLEMENTATION_GUIDE.md` và `13_PART_F_PIPELINE_ORCHESTRATION_GUIDE.md` để nối pipeline.

- [ ] 8\. Khi pipeline ghi DB ổn, làm embedding/vectorstore/retrieval theo `14` -&gt; `15` -&gt; `16` -&gt; `17` -&gt; `18`.

## YAML Metadata Chốt

Ví dụ tối thiểu:

```yaml
document_key: qd-3266
title: "Quy định công tác học vụ dành cho sinh viên trình độ đại học hình thức chính quy"
document_type: quyet_dinh
domain: hoc_vu
audience:
  - sinh_vien
responsible_department:
  - PDT
version_key: qd-3266-2024
code: "3266/QĐ-ĐHCT"
issued_date: 2024-01-01
issuing_authority: "Trường Đại học Cần Thơ"
signer_name: "Trần Trung Tính"
is_latest: true
source_url: ""
source_path: ""
canonical_markdown_path: ""
file_type: md
language: vi
checksum: "sha256-hex-64-chars"
```

Quy tắc:

- `responsible_department` luôn là list: `[]`, `[PDT]`, hoặc dạng nhiều dòng.
- Không dùng `validity_status`.
- Không dùng `version_label`.
- Không dùng `signer`, dùng `signer_name`.
- `checksum` của `document_versions` bắt buộc.-

## Reconciliation Checklist — Structural Chunking/Retrieval

- [ ] `PageBlock.content` bắt đầu sau marker và kết thúc trước marker kế tiếp.
- [ ] Page marker, HTML comment, OCR page-number artifact và `---` sát page boundary không thành Child/embedding.
- [ ] Mỗi Markdown heading mở Parent mới; không merge qua heading boundary.
- [ ] Parent heading-only có `heading_content` Child hoặc `context_only_reason`.
- [ ] `Chương I` + tên chương liên tiếp giữ derived heading context.
- [ ] Heading bất thường sinh canonical Markdown warning, không tự demote.
- [ ] Table/code luôn là atomic Child riêng; table dài split theo row và lặp header; code dài split theo dòng, giữ fence và logical_code_key.
- [ ] `legal_unit_type` chỉ gán khi có legal context; general list dùng `none`.
- [ ] Warning không block publish mặc định; error mới block.
- [ ] `Chunk.metadata` được phân biệt với metadata đã persist PostgreSQL.
- [ ] Qdrant payload có title/source_file/source_url, logical/parent item key, logical_item_keys cho bullet group, split info, chunk order, marker và level.
- [ ] Embedding chỉ prepend ancestor item labels, không lặp current item.
- [ ] Retrieval expansion hỗ trợ parent/child/sibling/split, deduplicate, source-order và context budget.
- [ ] Hydration không truy cập `chunk.parent_chunk_key`; fallback qua `parent_chunk_id`/parent row.
- [ ] QueryDecision chạy trước retrieval; greeting/clarification khác no-result và không gọi Qdrant/LLM.
- [ ] Golden test `test_3266.md` bao phủ toàn bộ contract trên.
