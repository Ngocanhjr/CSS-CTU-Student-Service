# CTU Student Service — Setup

Hướng dẫn này chạy backend FastAPI, PostgreSQL, Qdrant và admin frontend React.
OCR/LlamaParse không chạy trong repository này; backend chỉ nhận canonical Markdown đã xử lý.

## 1. Yêu cầu

- Docker Desktop
- Python 3.10+
- Node.js 18+
- NVIDIA GPU + Docker GPU support nếu chạy service TEI để embedding/indexing

## 2. Tạo cấu hình môi trường

Tại thư mục gốc:

```powershell
Copy-Item .env.example .env
```

Mở `.env`, thay các giá trị placeholder. Thêm `DATABASE_URL` vì backend và Alembic cần biến này:

```dotenv
POSTGRES_DB=ctu_student_service
POSTGRES_USER=ctu_user
POSTGRES_PASSWORD=use_a_strong_password
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://ctu_user:use_a_strong_password@localhost:5432/ctu_student_service

QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_COLLECTION=ctu_chunks_bge_m3
QDRANT_API_KEY=

TEI_PORT=8080
TEI_BASE_URL=http://localhost:8080
TEI_API_KEY=use_a_long_random_value
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BATCH_SIZE=4
```

`QDRANT_API_KEY` để trống với `compose.yaml` hiện tại vì Qdrant local chưa cấu hình API key.

## 3. Chạy hạ tầng

Chạy PostgreSQL và Qdrant:

```powershell
docker compose up -d postgres qdrant
docker compose ps
```

Chạy TEI khi cần embedding/indexing. Service này dùng `gpus: all`:

```powershell
docker compose pull tei
docker compose up -d tei
```

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

Kiểm tra API ở terminal khác:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Kết quả mong đợi:

```json
{"status":"ok"}
```

## 5. Cài và chạy admin frontend

```powershell
Set-Location admin-frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:5174`. Vite proxy `/api` tới backend tại `http://127.0.0.1:8000`.

## 6. Kiểm tra nhanh

```powershell
Set-Location backend
pytest -q

Set-Location ..\admin-frontend
npm run build
```

Database smoke test chỉ chạy khi `DATABASE_URL` trỏ đến database riêng có hậu tố
`/ctu_student_service_test`.

## 7. Dừng dịch vụ

```powershell
docker compose down
```

`docker compose down` không xóa dữ liệu bind-mount trong `infrastructure/docker/db/`.
