# 01. FastAPI App Bootstrap & Health Endpoint

**Last Updated:** 2026-07-13

```text
Tao FastAPI() instance trong app/main.py
Bat CORS cho Flutter dev va React admin dev
Warm-up embedding model luc startup
Tra ve health check don gian, khong versioned
Include router cho health (co that trong guide nay)
Danh vi tri include_router cho rag/documents/versions/ingestion (se tao o guide sau)
```

Guide này chỉ bootstrap app. Không viết logic nghiệp vụ nào — `/api/v1/rag/answer`,
`/api/v1/documents`, `/api/v1/document-versions/{id}`, `/api/v1/ingestion/jobs` đều được tạo ở các
guide khác trong bộ `api/` (đánh số sau guide này, dự kiến rải trong khoảng 05, 07, 08, 09, 10, 11,
12, 13, 14, 15 — số thứ tự chính xác do các guide đó tự chốt). `main.py` viết ở đây chỉ có nhiệm vụ
include router khi router đó tồn tại; không định nghĩa route nghiệp vụ trực tiếp trong `main.py`.

---

## 1. Trạng Thái Hiện Tại (đã đọc code, không suy đoán)

```text
app/main.py                 -> RỖNG, 0 dòng. Chưa có FastAPI() instance.
app/api/health.py           -> RỖNG, 0 dòng. Chưa có route nào.
app/api/__init__.py         -> tồn tại, rỗng.
app/api/routes/             -> tồn tại nhưng KHÔNG có file nào bên trong.
app/api/rag.py               -> CHƯA TỒN TẠI.
app/api/documents.py         -> CHƯA TỒN TẠI.
app/api/versions.py          -> CHƯA TỒN TẠI.
app/api/ingestion.py         -> CHƯA TỒN TẠI.
requirements.txt            -> KHÔNG có fastapi, KHÔNG có uvicorn, KHÔNG có httpx.
app/core/settings_loader.py -> chỉ có ChunkingSettings/RetrievalSettings, KHÔNG có
                                CORS_ORIGINS hay bất kỳ setting nào cho app FastAPI.
app/embedding/embedder.py   -> đã có get_embedding() -> NVIDIAEmbeddings, raise
                                ValueError nếu thiếu biến môi trường NVIDIA_API_KEY.
```

Vì `requirements.txt` chưa có `fastapi`/`uvicorn`, đây là việc phải làm trước khi chạy được app này,
không phải phần "tuỳ chọn".

---

## 2. File Cần Tạo/Sửa

```text
chatbot/backend/app/main.py
chatbot/backend/app/api/health.py
chatbot/backend/requirements.txt
chatbot/backend/test/api/test_health.py
```

Không sửa `app/api/__init__.py` (giữ rỗng, chỉ đóng vai trò package marker).

---

## 3. Thêm Dependency

File `chatbot/backend/requirements.txt` hiện tại chưa có dòng nào cho FastAPI. Thêm:

```text
fastapi>=0.111
uvicorn[standard]>=0.29
httpx>=0.27
```

Giải thích:

```text
fastapi   -> framework chinh, dung cho FastAPI(), APIRouter, CORSMiddleware.
uvicorn   -> ASGI server de chay app luc dev/prod (uvicorn app.main:app).
httpx     -> khong phai dependency bat buoc cua fastapi, nhung TestClient cua Starlette/FastAPI
             (tu ban fastapi hien tai) dung httpx ben trong. Thieu httpx thi import
             `from fastapi.testclient import TestClient` se loi ngay khi chay test.
```

Cài đặt (dùng venv của project, không cài global):

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" httpx
```

---

## 4. `app/api/health.py`

Health check không cần versioned, không cần prefix `/api/v1` (spec `06_API_SPEC.md` chỉ yêu cầu
prefix `/api/v1` cho route public nghiệp vụ, health check là route vận hành/monitoring riêng).

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Health check don gian cho load balancer/monitoring.

    Khong check DB, khong check Qdrant, khong check NVIDIA API o day.
    Muc tieu MVP: xac nhan process FastAPI dang song va tra response duoc.
    """
    return {"status": "ok"}
```

Lưu ý:

```text
Khong dat health check trong app/api/routes/ (thu muc nay dang rong, chua co quy uoc
ro rang cho cac guide sau dung lam gi — guide nay khong dong gia dinh vao do).
Khong them logic kiem tra DB/Qdrant vao health check trong guide nay; neu can readiness
check day du hon (DB/Qdrant/NVIDIA API), lam o guide rieng, khong lam am tham o day.
```

---

## 5. `app/main.py`

### 5.1. CORS origin cho 2 frontend dev

```text
Flutter (chatbot-ctu-app/frontend):
  - Android emulator goi ra may host qua 10.0.2.2, KHONG phai localhost.
  - Flutter web dev (flutter run -d chrome) mac dinh chay tren localhost voi port random,
    hoac co the fix port bang --web-port.
React admin (chatbot/admin-frontend):
  - Vite dev server mac dinh localhost:5173.
```

Ghi chú kỹ thuật quan trọng: CORS chỉ áp dụng cho request có header `Origin` do browser gửi.
Flutter chạy như native app (Android/iOS) gọi HTTP trực tiếp bằng package `http`, **không** gửi
`Origin` và **không** bị CORS middleware chặn — CORS chỉ liên quan khi Flutter chạy ở web
(`flutter run -d chrome`) hoặc khi debug bằng browser. Vẫn khai báo origin `10.0.2.2`/`localhost`
trong danh sách cho phép để không phải sửa lại khi có người dùng Flutter web dev, nhưng đừng hiểu
nhầm rằng thiếu CORS sẽ chặn app Android/iOS thật — vấn đề của app di động khi gọi `10.0.2.2` là
network permission (`usesCleartextTraffic`), không phải CORS.

```python
ALLOWED_ORIGINS = [
    "http://localhost:5173",   # React admin dev (Vite)
    "http://localhost:5173/",
    "http://localhost",        # Flutter web dev, khong co port co dinh
    "http://127.0.0.1:5173",
    "http://10.0.2.2",         # Flutter web dev chay qua Android emulator (hiem, nhung khai bao cho du)
    "http://10.0.2.2:8000",
]
```

Nếu cần mở rộng port Flutter web dev linh hoạt hơn (`flutter run` chọn port ngẫu nhiên mỗi lần),
có thể tạm dùng `allow_origin_regex` thay cho danh sách cố định, nhưng MVP dùng danh sách tường
minh ở trên cho dễ audit; không dùng `allow_origins=["*"]` kèm `allow_credentials=True` (FastAPI/
Starlette sẽ reject cấu hình này, và về bảo mật cũng không nên mở origin rộng cho API có thể phát
triển thêm auth sau này).

### 5.2. Warm-up embedding model lúc startup

`app/embedding/embedder.get_embedding()` đã có sẵn, tạo instance `NVIDIAEmbeddings` và raise
`ValueError` nếu thiếu `NVIDIA_API_KEY`. Gọi hàm này một lần lúc startup để:

```text
Phat hien thieu NVIDIA_API_KEY ngay khi app khoi dong, khong phai doi den request dau tien
cua user moi biet loi config.
Tao instance client som, tranh cost khoi tao lap lai/cold-start o request dau.
```

Lưu ý quan trọng: `get_embedding()` chỉ khởi tạo object client (`NVIDIAEmbeddings(...)`), **không**
tự động gọi network request tới NVIDIA API. Đây không phải "warm up" theo nghĩa gọi trước một lần
embedding thật để load model — đó là hành vi phía server NVIDIA, project này không kiểm soát được.
Ở đây "warm-up" nghĩa là warm-up việc khởi tạo Python object và phát hiện lỗi config sớm.

Dùng `lifespan` (cách khuyến nghị hiện tại của FastAPI, thay cho `@app.on_event("startup")` đã
deprecated):

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.embedding.embedder import get_embedding

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_embedding()
        logger.info("Embedding client warm-up: OK")
    except ValueError:
        # NVIDIA_API_KEY chua duoc cau hinh (vi du: chay test/dev chua set env).
        # Khong crash app luc startup vi mot so route (health check, doc DB) van
        # phai hoat dong duoc khi chua co API key.
        logger.warning(
            "Embedding client warm-up bo qua: thieu bien moi truong NVIDIA_API_KEY"
        )
    yield
```

Quyết định: không để app crash nếu thiếu `NVIDIA_API_KEY` lúc startup, vì `/health` và các route
không liên quan embedding (ví dụ `GET /api/v1/documents`) vẫn cần chạy được trong môi trường
dev/test chưa cấu hình đủ secret. Route nào thực sự cần embedding (rag/answer, ingestion) sẽ tự
raise lỗi rõ ràng khi gọi tới, không phải trách nhiệm của `main.py`.

### 5.3. Khởi tạo app và include router

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router

app = FastAPI(
    title="CTU Student Service Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check khong versioned, khong prefix /api/v1.
app.include_router(health_router)

# --- Cac router nghiep vu ben duoi CHUA TON TAI trong repo hien tai. ---
# Se duoc tao o cac guide tiep theo trong bo api/ (rag/documents/versions/ingestion).
# KHONG uncomment truoc khi file router tuong ung ton tai — uvicorn se crash ngay luc
# import voi ModuleNotFoundError neu app/api/rag.py (hoac documents.py/versions.py/
# ingestion.py) chua duoc tao.
#
# from app.api.rag import router as rag_router
# from app.api.documents import router as documents_router
# from app.api.versions import router as versions_router
# from app.api.ingestion import router as ingestion_router
#
# app.include_router(rag_router, prefix="/api/v1")
# app.include_router(documents_router, prefix="/api/v1")
# app.include_router(versions_router, prefix="/api/v1")
# app.include_router(ingestion_router, prefix="/api/v1")
```

Quy tắc khi các guide sau tạo router mới:

```text
Moi router moi (rag.py/documents.py/versions.py/ingestion.py) phai tu dinh nghia
APIRouter() rieng trong file cua no (giong pattern app/api/health.py), khong dinh
nghia route truc tiep trong main.py.
Sau khi router file ton tai, uncomment 2 dong tuong ung (import + include_router)
trong main.py that, khong copy paste toan bo main.py.
prefix="/api/v1" ap dung dung 1 lan luc include_router; router con lai KHONG tu
khai bao prefix "/api/v1" trong APIRouter(prefix=...) cua no de tranh prefix bi
lap (/api/v1/api/v1/...).
```

---

## 6. File `main.py` Hoàn Chỉnh (guide này)

Ghép lại toàn bộ nội dung thật của `app/main.py` sau guide này (không có route nghiệp vụ, chỉ có
health thật + comment placeholder cho các router tương lai):

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.embedding.embedder import get_embedding

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5173/",
    "http://localhost",
    "http://127.0.0.1:5173",
    "http://10.0.2.2",
    "http://10.0.2.2:8000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_embedding()
        logger.info("Embedding client warm-up: OK")
    except ValueError:
        logger.warning(
            "Embedding client warm-up bo qua: thieu bien moi truong NVIDIA_API_KEY"
        )
    yield


app = FastAPI(
    title="CTU Student Service Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)

# from app.api.rag import router as rag_router
# from app.api.documents import router as documents_router
# from app.api.versions import router as versions_router
# from app.api.ingestion import router as ingestion_router
#
# app.include_router(rag_router, prefix="/api/v1")
# app.include_router(documents_router, prefix="/api/v1")
# app.include_router(versions_router, prefix="/api/v1")
# app.include_router(ingestion_router, prefix="/api/v1")
```

---

## 7. Chạy Thử App

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` cần thiết để Android emulator gọi được qua `10.0.2.2:8000` (mặc định uvicorn chỉ
bind `127.0.0.1`, emulator không tới được).

---

## 8. Test/Kiểm Thử

### 8.1. Test thủ công bằng curl

```powershell
curl http://localhost:8000/health
```

Kết quả mong đợi:

```json
{"status":"ok"}
```

### 8.2. Test tự động bằng `TestClient`

File:

```text
chatbot/backend/test/api/test_health.py
```

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_has_no_api_v1_prefix():
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 404
```

Chạy:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/api/test_health.py
```

Lưu ý: `pytest.ini` hiện tại giới hạn `testpaths = test/databases`. Nếu muốn `pytest` (không có
đường dẫn) tự chạy cả `test/api`, cần sửa `testpaths` — nhưng đó là thay đổi cấu hình test chung,
ngoài phạm vi guide này; guide này chỉ đảm bảo lệnh pytest chỉ định rõ đường dẫn
(`pytest test/api/test_health.py`) chạy được.

Khởi tạo `TestClient(app)` sẽ chạy `lifespan`, tức là `get_embedding()` được gọi trong lúc test.
Nếu môi trường test không có `NVIDIA_API_KEY`, hàm raise `ValueError` và bị catch/log warning như
mục 5.2 — test không fail vì lý do này. Nếu muốn test riêng nhánh warm-up thành công, phải set
`NVIDIA_API_KEY` giả trong môi trường test và mock `NVIDIAEmbeddings`, không gọi API thật trong
unit test.

---

## 9. Lỗi Dễ Gặp

### Lỗi: `ModuleNotFoundError: No module named 'fastapi'`

Nguyên nhân:

```text
Chua cai fastapi vao venv, hoac dang chay python he thong thay vi venv project.
```

Xử lý:

```powershell
..\..\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" httpx
```

### Lỗi: `TypeError` hoặc `RuntimeError` khi import `fastapi.testclient`

Nguyên nhân:

```text
Thieu httpx trong venv (TestClient cua ban FastAPI hien tai dung httpx ben trong,
khong tu cai kem theo fastapi).
```

Xử lý:

```powershell
..\..\.venv\Scripts\python.exe -m pip install httpx
```

### Lỗi: Android emulator không gọi được `/health`

Nguyên nhân:

```text
uvicorn bind 127.0.0.1 (mac dinh) thay vi 0.0.0.0, hoac Flutter AndroidManifest
chua usesCleartextTraffic cho HTTP dev.
```

Xử lý:

```text
Chay uvicorn voi --host 0.0.0.0.
Cau hinh usesCleartextTraffic o phia Flutter (ngoai pham vi guide backend nay).
```

### Lỗi: Uncomment router mới nhưng app crash `ModuleNotFoundError: No module named 'app.api.rag'`

Nguyên nhân:

```text
Router file (app/api/rag.py v.v.) chua duoc guide sau tao that, nhung da uncomment
dong import trong main.py.
```

Xử lý:

```text
Chi uncomment sau khi guide tuong ung (tao app/api/rag.py/documents.py/versions.py/
ingestion.py) da xong.
```

---

## 10. Done Khi

- [ ] `requirements.txt` có `fastapi`, `uvicorn[standard]`, `httpx`.
- [ ] `app/api/health.py` có `router = APIRouter(...)` và `GET /health` trả `{"status": "ok"}`.
- [ ] `app/main.py` tạo `FastAPI()` instance thật, không còn rỗng.
- [ ] `CORSMiddleware` được add với origin cho cả React admin dev (`localhost:5173`) và Flutter dev
      (`10.0.2.2`, `localhost`).
- [ ] `lifespan` gọi `get_embedding()` một lần lúc startup, và không crash app nếu thiếu
      `NVIDIA_API_KEY` (chỉ log warning).
- [ ] `app.include_router(health_router)` không có prefix `/api/v1`.
- [ ] Các router rag/documents/versions/ingestion **chưa** được include (vì file chưa tồn tại),
      chỉ để dạng comment placeholder rõ ràng trong `main.py`.
- [ ] `uvicorn app.main:app --host 0.0.0.0 --port 8000` chạy được, `curl http://localhost:8000/health`
      trả đúng JSON.
- [ ] `test/api/test_health.py` pass.

---

## 11. Phụ Thuộc / Thứ Tự Làm Trước

```text
Khong phu thuoc guide nao khac de chay duoc health check (health.py doc lap hoan
toan, khong dung DB/Qdrant/embedding).
lifespan warm-up phu thuoc app/embedding/embedder.py (Guide 14_PART_G_EMBEDDING_GUIDE.md)
da co san get_embedding() — da xac nhan file nay khong rong, co the dung ngay.
main.py se can sua tiep (uncomment import/include_router) sau khi cac guide tao
app/api/rag.py, app/api/documents.py, app/api/versions.py, app/api/ingestion.py
hoan thanh — cac guide do dua vao Guide 16_PART_I_RETRIEVAL_GUIDE.md (retrieval),
Guide 18_PART_K_RAG_ANSWER_CHAIN_GUIDE.md (answer_question()), Guide
12_PART_E_POSTGRES_INGESTION_REPOSITORY_GUIDE.md (repository ghi DB) da co san logic,
nhung ban than cac router FastAPI (app/api/rag.py v.v.) van CHUA duoc viet — day la
viec cua cac guide sau trong bo api/, khong phai guide nay.
```
