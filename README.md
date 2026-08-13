# CTU Student Service Chatbot

Hệ thống quản trị tài liệu và hỏi đáp RAG cho dịch vụ sinh viên Trường Đại học Cần Thơ.

## Thành phần

- `backend/`: FastAPI, PostgreSQL, Qdrant, ingestion và RAG.
- `admin-frontend/`: React/Vite để upload, review, index, publish và quản lý tài liệu.
- `chatbot-ctu-app/`: ứng dụng hỏi đáp dành cho người dùng cuối (nếu được checkout cùng workspace).
- `compose.yaml`: PostgreSQL và Qdrant chạy local.

OCR không chạy trong repository này. Admin upload canonical Markdown đã được xử lý và có thể đính kèm file nguồn.

## Luồng tài liệu

```text
Upload Markdown + metadata
→ Review/approve
→ Preview parent/child chunks
→ Index PostgreSQL + Cloudflare Workers AI + Qdrant
→ Publish
→ RAG chỉ truy xuất tài liệu approved + published
```

PostgreSQL là nguồn chuẩn cho metadata và nội dung chunk. Qdrant chỉ lưu vector child chunk cùng payload cấu trúc.

## Bắt đầu nhanh

Xem [SETUP.md](SETUP.md) để cấu hình `.env`, chạy hạ tầng, migration, backend và admin frontend.

```powershell
Copy-Item .env.example .env
docker compose up -d postgres qdrant
```

Sau khi backend chạy:

- Health: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Admin frontend: `http://127.0.0.1:5174`

## API chính

| Nhóm | Endpoint |
| --- | --- |
| Health | `GET /health`, `GET /api/v1/health/database` |
| Reference data | `GET /api/v1/reference/document-types`, `/departments`, `/enums` |
| Ingestion | `POST /api/v1/admin/canonical-markdown`, metadata preview, review, chunk preview và index job |
| Documents | `GET/PUT/DELETE /api/v1/versions/{id}` và quản lý assets |
| Lifecycle | `POST /api/v1/versions/{id}/publish`, `/unpublish`, `/deindex` |
| RAG | `POST /api/v1/rag/answer` |

Chi tiết backend nằm tại [backend/README.md](backend/README.md).

## Kiểm tra

```powershell
Set-Location backend
python -m pytest -q

Set-Location ..\admin-frontend
npm run build
```

Không commit `.env`, API key, database password hoặc credential R2.
