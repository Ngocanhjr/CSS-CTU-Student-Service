# Spec Maintenance Log

File này gom các ghi chú tiến độ/changelog cũ để tránh nhiều file log rời rạc.

## 2026-06-10

### Is latest rule

- `is_latest` là ranking preference, không phải hard filter.
- Student RAG hard filter hiện tại:

```text
review_status = approved
AND rag_status = published
```

- Không loại version cũ chỉ vì `is_latest = false`.
- Khi nhiều version cùng phù hợp, ưu tiên `is_latest = true`.

### Spec generation session

Các spec chính trong `chatbot/.docs/spec/ctu-service/` được tạo để làm bộ tài liệu chính:

```text
00_INDEX.md
01_PROJECT_OVERVIEW.md
02_REQUIREMENTS.md
03_SYSTEM_ARCHITECTURE.md
04_MODULE_SPEC.md
05_DATABASE_SPEC.md
06_API_SPEC.md
07_RAG_SPEC.md
08_OCR_INGESTION_SPEC.md
09_FRONTEND_SPEC.md
11_IMPLEMENTATION_PLAN.md
SPEC_MAINTENANCE_LOG.md
```

### Diagram cleanup

- Mermaid TODO markers đã được dọn ở các diagram cũ.
- Excalidraw files nếu phát sinh lỗi binding thì rebuild từ Mermaid/source spec.

## 2026-07-04

### Source of truth

- Chọn `spec/ctu-service/*.md` làm bộ tài liệu chính.
- Các file trùng ở ngoài `spec/ctu-service` đã được xóa để giảm lan man.

### Final schema notes

- Schema hiện tại có 9 bảng.
- Không dùng `version_status_history`, `document_version_status`, `document_version_relationships`, `collection_status`.
- Không dùng `validity_status` trong `document_versions`.
- `assets.validity_status` vẫn được giữ cho asset/form/link.

### Current MVP stack

- Frontend: Flutter.
- Backend: FastAPI.
- OCR/parser: LlamaParse only.
- Retrieval: hybrid dense + sparse + RRF.
- API prefix: `/api/v1`.

### Security/governance consolidation

- `10_SECURITY_AND_GOVERNANCE.md` đã được gom vào `02_REQUIREMENTS.md`.
- Chỉ giữ lại rule MVP: roles/permissions, retrieval governance, secrets, validation, audit, backup.

### Open decisions moved from `12_OPEN_QUESTIONS.md`

Các mục dưới đây vẫn chưa cần chốt để chạy MVP, nhưng nên quyết định trước production:

| Area | Current MVP stance | Open decision |
|---|---|---|
| LLM provider | TBD | Chọn OpenAI, Anthropic, Gemini, hoặc local LLM |
| FastAPI runtime | FastAPI | Chốt Uvicorn/Hypercorn, SQLAlchemy/SQLModel, Alembic config |
| Flutter state management | TBD | Chọn Riverpod hoặc BLoC |
| Storage paths | Local filesystem | Chốt cấu trúc `storage/raw`, `storage/ocr_output`, `storage/canonical`, `storage/assets` |
| Deployment | Docker Compose local | Chọn VPS/cloud/on-prem sau MVP |
| Authentication | Simple username/password | Chốt CTU SSO sau MVP nếu cần |
| Evaluation | Manual/golden set planned | Chốt golden question set và metrics |
| Chat history | TBD | Chốt thời gian lưu và privacy rule |
| Monitoring | File logs | Chốt production stack sau MVP |

Các mục đã chốt và không còn là open question:

- Embedding MVP: `BAAI/bge-m3`.
- OCR/parser MVP: LlamaParse only.
- Retrieval MVP: hybrid dense + sparse + RRF.
- HNSW tuning: post-MVP.
- Document version retrieval: không hard filter `is_latest`.

## Remaining Maintenance

- Chỉ cập nhật log này khi có quyết định tài liệu quan trọng.
- Không tạo thêm file `PROGRESS`, `COMPLETION_*`, `FIXES_*`, `OPEN_QUESTIONS`, hoặc changelog rời nếu nội dung có thể ghi vào file này.
