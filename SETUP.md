# CTU Student Service — Setup

Hướng dẫn chạy PostgreSQL, Qdrant, FastAPI và admin frontend trên Windows PowerShell.

## 1. Yêu cầu

- Docker Desktop.
- Python 3.10 trở lên.
- Node.js 18 trở lên.
- Tài khoản Cloudflare có Workers AI và R2.
- API key của một endpoint OpenAI-compatible để chạy query rewrite và sinh câu trả lời.

GPU và TEI local không bắt buộc; embedding hiện gọi Cloudflare Workers AI.

## 2. Tạo cấu hình

Tại thư mục gốc:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay toàn bộ giá trị `change-me`. Các nhóm bắt buộc để chạy đầy đủ:

- PostgreSQL: `POSTGRES_*`, `DATABASE_URL`.
- Qdrant: `QDRANT_URL`, `QDRANT_COLLECTION`.
- Embedding: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`.
- Object storage: `R2_*`.
- RAG answer: `LLM_API_KEY`; `LLM_BASE_URL` và `LLM_MODEL` có giá trị mặc định nhưng nên khai báo rõ.

`JINA_API_KEY` là tùy chọn. Khi bỏ trống, hệ thống giữ thứ hạng hybrid RRF.

## 3. Chạy PostgreSQL và Qdrant

```powershell
docker compose up -d postgres qdrant
docker compose ps
```

Compose bind-mount dữ liệu vào `infrastructure/docker/db/`. `docker compose down` không xóa dữ liệu này.

## 4. Cài và chạy backend

```powershell
Set-Location backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

Nếu PowerShell chặn script activate, có thể gọi interpreter trực tiếp:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Kiểm tra:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/database
```

OpenAPI UI: `http://127.0.0.1:8000/docs`.

## 5. Cài và chạy admin frontend

Mở terminal khác tại thư mục gốc:

```powershell
Set-Location admin-frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:5174`. Vite proxy `/api` đến `http://127.0.0.1:8000` theo `admin-frontend/vite.config.js`.

## 6. Kiểm tra workflow

1. Upload canonical Markdown và chọn phòng ban nguồn.
2. Review metadata/nội dung rồi approve.
3. Tạo và duyệt chunk preview.
4. Chạy index; theo dõi ingestion job đến khi `completed`.
5. Publish tài liệu.
6. Gọi `POST /api/v1/rag/answer` hoặc dùng ứng dụng hỏi đáp.

Chỉ tài liệu có `review_status=approved` và `rag_status=published` được dùng để trả lời sinh viên.

## 7. Chạy kiểm tra

```powershell
Set-Location backend
python -m pytest -q

Set-Location ..\admin-frontend
npm run build
```

Nếu `dist` đang được Vite preview hoặc tiến trình khác giữ file, dừng tiến trình đó trước khi build lại.

## 8. Dừng dịch vụ

```powershell
Set-Location ..
docker compose down
```

Không dùng `docker compose down -v` nếu muốn giữ dữ liệu local.
