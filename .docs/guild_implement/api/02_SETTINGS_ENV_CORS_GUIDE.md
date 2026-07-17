# 02. Settings, .env và CORS cho API

**Last Updated:** 2026-07-13

```text
Muc tieu file nay:
- Bo sung bien moi truong va cach doc settings rieng cho API layer (FastAPI app,
  CORS, LLM provider cho rag_chain).
- KHONG dong vao ChunkingSettings/RetrievalSettings trong app/core/settings_loader.py
  (2 dataclass nay da chot, giu nguyen).
- Cap nhat chatbot/.env.example them bien moi, khong xoa bien cu.
```

---

## 0. Trang Thai Thuc Te Truoc Khi Sua

Da doc truc tiep code, xac nhan:

```text
chatbot/backend/app/main.py               -> RONG (0 dong), chua co FastAPI().
chatbot/backend/app/api/health.py         -> RONG (0 dong), chua co route.
chatbot/backend/app/api/__init__.py       -> RONG.
chatbot/backend/app/api/routes/           -> thu muc rong, chua co file router nao.
chatbot/backend/app/core/settings_loader.py
    -> chi co ChunkingSettings, RetrievalSettings, AppSettings, get_rag_settings().
    -> KHONG co field nao cho CORS/API key/LLM provider.
chatbot/backend/app/vectorstore/qdrant_client.py
    -> doc os.getenv("QDRANT_URL", "http://localhost:6333") va
       os.getenv("QDRANT_API_KEY") truc tiep trong ham get_qdrant_client(),
       khong qua dataclass settings nao ca.
chatbot/backend/app/embedding/embedder.py
    -> doc os.getenv("NVIDIA_API_KEY") va
       os.getenv("NVIDIA_EMBEDDING_MODEL", "baai/bge-m3") truc tiep trong
       ham get_embedding(), cung khong qua dataclass settings.
chatbot/backend/app/llm/prompts.py
    -> DA CO, dung ChatPromptTemplate.from_template(template) voi bien
       {context} va {question} (dang single-template, khong phai
       from_messages system/human nhu Guide 18 mo ta o muc thiet ke).
       Day la code THAT dang ton tai, guide nay khong doi lai file do.
chatbot/backend/app/llm/rag_chain.py      -> RONG.
chatbot/backend/app/llm/generator.py      -> RONG.
chatbot/backend/requirements.txt
    -> KHONG co fastapi, uvicorn, langchain-nvidia-ai-endpoints (goi
       langchain_nvidia_ai_endpoints da duoc import trong embedder.py
       nhung package chua nam trong requirements.txt), KHONG co
       python-jose/passlib (khong can, guide nay khong lam auth).
chatbot/.env.example (hien tai)
    -> co TZ, POSTGRES_DB/USER/PASSWORD/PORT, QDRANT_HTTP_PORT,
       QDRANT_GRPC_PORT, QDRANT_API_KEY, QDRANT_LOG_LEVEL,
       QDRANT_TELEMETRY_DISABLED.
    -> KHONG co CORS_ORIGINS, KHONG co LLM_PROVIDER/LLM_API_KEY,
       KHONG co QDRANT_URL, KHONG co NVIDIA_API_KEY/NVIDIA_EMBEDDING_MODEL
       (2 bien NVIDIA nay dang ton tai trong chatbot/.env thuc te nhung
       chua duoc dua vao .env.example).
```

Ket luan: day la phan **hoan toan moi**, khong phai sua lai settings da chot.

---

## 1. File Can Tao/Sua

```text
chatbot/backend/app/core/api_settings.py      (MOI - tao)
chatbot/backend/app/main.py                    (SUA - dang rong, them FastAPI + CORS)
chatbot/backend/app/api/health.py              (SUA - dang rong, them route /health)
chatbot/backend/.env.example                   (KHONG co file rieng trong backend, dung file goc)
chatbot/.env.example                           (SUA - them bien moi)
chatbot/backend/requirements.txt               (SUA - them fastapi, uvicorn, langchain-nvidia-ai-endpoints)
chatbot/backend/test/core/test_api_settings.py (MOI - tao, test doc bien env)
```

Ghi chu: `app/main.py` va `app/api/health.py` duoc dong cham o day chi de wiring
CORS/settings hoat dong duoc, khong thay the cho mot guide rieng ve routing
(neu sau nay co guide rieng cho `/api/v1/...`, guide do se mo rong tiep tren
skeleton nay).

---

## 2. Hai Lua Chon Thiet Ke Va Khuyen Nghi

### Lua chon A — them dataclass `ApiSettings` trong `settings_loader.py`

Uu diem: nhat quan voi `ChunkingSettings`/`RetrievalSettings` da co, co the load tu
YAML (`runtime.yaml`) giong 2 dataclass do.

Nhuoc diem: `ChunkingSettings`/`RetrievalSettings` la tham so tuning nghiep vu
(chunk size, top_k) — on dinh, it doi theo moi truong deploy. Con CORS origins,
API key la **cau hinh theo moi truong** (dev/staging/prod khac nhau, cung mot
YAML commit vao git khong nen chua secret). Neu nhet vao `runtime.yaml`, se lo
API key trong file YAML checked-in git.

### Lua chon B — doc `os.getenv()` truc tiep, gom vao 1 module rieng `api_settings.py`

Giong cach `qdrant_client.py` va `embedder.py` dang lam (`os.getenv(...)` ngay
trong ham can dung). Uu diem: nhat quan voi pattern code THAT hien co, khong
dua secret vao file YAML commit git, `.env` da co san cho pattern nay
(`python-dotenv` da la dependency, `embedder.py` da goi
`load_dotenv(find_dotenv())`).

### Khuyen nghi

**Chon Lua chon B**, nhung khong rai `os.getenv()` ngay trong `main.py` nhu
guide de xuat ban dau — gom vao 1 file `app/core/api_settings.py` co ham
`get_api_settings()` (dung `lru_cache` giong `get_rag_settings()` de doc mot
lan). Ly do gom vao 1 ham thay vi rai truc tiep trong `main.py`:

```text
- main.py se con them logging/exception handler/router sau nay, de rai them
  os.getenv() vao do se kho test (test main.py phai import ca ung dung).
- get_api_settings() co the mock/override de test rieng, khong phai boot
  FastAPI app.
- Van giu dung tinh than "doc os.getenv() truc tiep", chi khac la co 1 diem
  tap trung thay vi rai o nhieu file.
```

---

## 3. `app/core/api_settings.py` (File Moi)

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:5173"


def _split_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(frozen=True)
class CorsSettings:
    allow_origins: list[str] = field(
        default_factory=lambda: _split_origins(DEFAULT_CORS_ORIGINS)
    )


@dataclass(frozen=True)
class LlmSettings:
    provider: str = "nvidia"
    api_key: str | None = None
    chat_model: str = "meta/llama-3.1-8b-instruct"


@dataclass(frozen=True)
class ApiSettings:
    cors: CorsSettings
    llm: LlmSettings


def _load_cors_settings() -> CorsSettings:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return CorsSettings(allow_origins=_split_origins(raw))


def _load_llm_settings() -> LlmSettings:
    provider = os.getenv("LLM_PROVIDER", "nvidia").strip().lower()
    api_key = os.getenv("LLM_API_KEY") or None
    chat_model = os.getenv("LLM_CHAT_MODEL", "meta/llama-3.1-8b-instruct")
    return LlmSettings(provider=provider, api_key=api_key, chat_model=chat_model)


@lru_cache
def get_api_settings() -> ApiSettings:
    settings = ApiSettings(
        cors=_load_cors_settings(),
        llm=_load_llm_settings(),
    )
    _validate_api_settings(settings)
    return settings


def _validate_api_settings(settings: ApiSettings) -> None:
    if not settings.cors.allow_origins:
        raise ValueError("CORS_ORIGINS phai co it nhat 1 origin")
    if settings.llm.provider not in {"nvidia", "openai"}:
        raise ValueError(
            f"LLM_PROVIDER khong ho tro: {settings.llm.provider!r} "
            "(chi ho tro 'nvidia' hoac 'openai')"
        )
```

Luu y:

```text
- lru_cache lam get_api_settings() chi doc os.getenv() 1 lan trong tien trinh.
  Trong test, muon doi env roi doc lai phai goi get_api_settings.cache_clear().
- allow_origins la list[str] de truyen truc tiep vao
  CORSMiddleware(allow_origins=...).
- api_key khong co default — thieu API key phai that bai ro rang khi thuc su
  goi LLM, khong fallback gia tri gia.
- LLM_PROVIDER validate whitelist ngay tai settings, khong de rag_chain.py
  tu xu ly chuoi tuy y.
```

---

## 4. Quyet Dinh LLM Provider Cho `rag_chain.py`

Du an dang dung `NVIDIAEmbeddings` (`langchain_nvidia_ai_endpoints`) cho
embedding, doc `NVIDIA_API_KEY`. Cho phan sinh cau tra loi (chat/generation),
co 2 huong:

```text
A) Dung tiep NVIDIA NIM chat endpoint qua
   langchain_nvidia_ai_endpoints.ChatNVIDIA — nhat quan 1 provider,
   dung chung NVIDIA_API_KEY da co san, khong them SDK moi.
B) Dung OpenAI-compatible endpoint qua langchain_openai.ChatOpenAI
   (hoac base_url tuy chinh) — pho bien hon nhung them 1 dependency
   moi (langchain-openai) va 1 API key rieng.
```

Guide nay **de xuat huong A (ChatNVIDIA)** de nhat quan voi embedder.py, giam
so luong provider/API key phai quan ly. Tuy nhien day la **quyet dinh nghiep
vu can nguoi dung/chu du an chot chinh thuc** truoc khi Guide 18
(`rag_chain.py`) implement thuc — vi lien quan chi phi, rate limit, model
chat cu the (vd `meta/llama-3.1-8b-instruct` hay model khac tren NVIDIA NIM
catalog).

`ApiSettings.llm.provider` trong guide nay chi la **cau hinh de LLM_PROVIDER
switch duoc giua "nvidia"/"openai" sau nay**, chua tu dong nghia la da chon
xong. Khi Guide 18 implement `rag_chain.py`, code khoi tao LLM nen doc qua
`get_api_settings().llm` thay vi doc `os.getenv()` rieng, vi du:

```python
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.core.api_settings import get_api_settings


def get_chat_llm() -> ChatNVIDIA:
    settings = get_api_settings().llm
    if settings.provider != "nvidia":
        raise ValueError(
            f"get_chat_llm() hien chi ho tro provider 'nvidia', dang la {settings.provider!r}"
        )
    if not settings.api_key:
        raise ValueError("LLM_API_KEY environment variable is not set.")
    return ChatNVIDIA(model=settings.chat_model, api_key=settings.api_key)
```

Ham `get_chat_llm()` nen dat trong `app/llm/generator.py` (file dang rong,
duoc du kien lam noi khoi tao LLM client), khong dat trong
`app/core/api_settings.py` — `api_settings.py` chi doc cau hinh, khong import
`langchain_nvidia_ai_endpoints`.

`langchain-nvidia-ai-endpoints` da duoc import trong `embedder.py` nhung
**chua co trong `requirements.txt`** — can them (xem muc 6).

---

## 5. `app/main.py` (Dang Rong — Them FastAPI + CORS)

File hien tai 0 dong. Noi dung de xuat toi thieu de wiring CORS va health
check hoat dong duoc:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.api_settings import get_api_settings

api_settings = get_api_settings()

app = FastAPI(title="CTU Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
```

Luu y:

```text
- allow_credentials=True chi hop le khi allow_origins KHONG chua "*".
  Neu CORS_ORIGINS=* trong .env, phai doi allow_credentials=False, khong
  duoc de nguyen True (browser se tu choi request that).
- Guide nay chi wiring health router de main.py chay duoc; router
  /api/v1/rag, /api/v1/documents, /api/v1/ingestion se duoc them boi guide
  rieng khac (chua ton tai trong .docs/guild_implement/api/ luc viet guide
  nay).
```

Ham kiem tra allow_credentials/wildcard nen dat truc tiep trong
`_validate_api_settings()` da co o muc 3, bo sung:

```python
def _validate_api_settings(settings: ApiSettings) -> None:
    if not settings.cors.allow_origins:
        raise ValueError("CORS_ORIGINS phai co it nhat 1 origin")
    if settings.cors.allow_origins == ["*"]:
        raise ValueError(
            "CORS_ORIGINS=* khong dung duoc voi allow_credentials=True; "
            "hay khai bao danh sach origin cu the."
        )
    if settings.llm.provider not in {"nvidia", "openai"}:
        raise ValueError(
            f"LLM_PROVIDER khong ho tro: {settings.llm.provider!r} "
            "(chi ho tro 'nvidia' hoac 'openai')"
        )
```

---

## 6. `app/api/health.py` (Dang Rong — Them Route)

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}
```

Route nay khong prefix `/api/v1` — health check thuong dat o root de load
balancer/monitoring goi truc tiep, tach biet voi API nghiep vu
(`/api/v1/...` theo spec goc).

---

## 7. Cap Nhat `requirements.txt`

`chatbot/backend/requirements.txt` hien tai KHONG co `fastapi`, `uvicorn`,
va KHONG co `langchain-nvidia-ai-endpoints` (du `embedder.py` da import
`langchain_nvidia_ai_endpoints`). Them:

```text
fastapi>=0.110
uvicorn[standard]>=0.29
langchain-nvidia-ai-endpoints>=0.1
```

Khong them `python-jose`, `passlib`, hay bat ky lib auth nao — guide nay
khong lam auth/JWT.

---

## 8. Cap Nhat `chatbot/.env.example`

File hien tai:

```env
# Timezone
TZ=Asia/Ho_Chi_Minh

# PostgreSQL
POSTGRES_DB=ctu_student_service
POSTGRES_USER=replace_with_your_username
POSTGRES_PASSWORD=replace_with_a_strong_postgres_password
POSTGRES_PORT=5432

# Qdrant
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_API_KEY=replace_with_a_long_random_qdrant_api_key
QDRANT_LOG_LEVEL=INFO
QDRANT_TELEMETRY_DISABLED=true
```

So sanh voi bien dang doc thuc te trong code (`DATABASE_URL`,
`OCR_MARKDOWN_DIR`, `NVIDIA_API_KEY`, `NVIDIA_EMBEDDING_MODEL` co trong
`.env` thuc te cua may dev nhung chua co trong `.env.example`) va bien moi
can cho API layer, them vao cuoi file:

```env
# Database URL (asyncpg, doc boi app/databases/session.py)
DATABASE_URL=postgresql+asyncpg://replace_with_your_username:replace_with_a_strong_postgres_password@localhost:5432/ctu_student_service

# Qdrant client (doc boi app/vectorstore/qdrant_client.py)
QDRANT_URL=http://localhost:6333

# OCR/ingestion
OCR_MARKDOWN_DIR=./data/markdown

# NVIDIA embedding (doc boi app/embedding/embedder.py)
NVIDIA_API_KEY=replace_with_your_nvidia_api_key
NVIDIA_EMBEDDING_MODEL=baai/bge-m3

# API layer - CORS (doc boi app/core/api_settings.py)
# Danh sach origin duoc phep goi API, phan cach bang dau phay, khong dung dau cach.
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# API layer - LLM cho rag_chain/generator (doc boi app/core/api_settings.py)
# provider hien ho tro: nvidia | openai (xem muc 4 cua guide nay de chon)
LLM_PROVIDER=nvidia
LLM_API_KEY=replace_with_your_llm_api_key
LLM_CHAT_MODEL=meta/llama-3.1-8b-instruct
```

Ghi chu:

```text
- QDRANT_URL truoc day khong co trong .env.example du qdrant_client.py da
  doc os.getenv("QDRANT_URL", ...) — day la thieu sot cu, guide nay bo sung
  luon vi cung nam trong pham vi "settings/env cho tang API/service".
- DATABASE_URL/OCR_MARKDOWN_DIR cung dang thieu trong .env.example, bo sung
  de file .env.example phan anh dung moi bien dang duoc doc trong code.
- Khong xoa hoac doi ten bien QDRANT_HTTP_PORT/QDRANT_GRPC_PORT (dung cho
  docker-compose expose port, khac voi QDRANT_URL dung cho app ket noi).
```

---

## 9. Test/Kiem Thu

### 9.1 Unit test `get_api_settings()`

File: `chatbot/backend/test/core/test_api_settings.py`

```python
import pytest

from app.core import api_settings


@pytest.fixture(autouse=True)
def clear_cache():
    api_settings.get_api_settings.cache_clear()
    yield
    api_settings.get_api_settings.cache_clear()


def test_default_cors_origins_when_env_missing(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = api_settings.get_api_settings()
    assert settings.cors.allow_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://ctu.edu.vn,https://admin.ctu.edu.vn"
    )
    settings = api_settings.get_api_settings()
    assert settings.cors.allow_origins == [
        "https://ctu.edu.vn",
        "https://admin.ctu.edu.vn",
    ]


def test_cors_wildcard_raises_value_error(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="allow_credentials"):
        api_settings.get_api_settings()


def test_llm_provider_invalid_raises_value_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        api_settings.get_api_settings()


def test_llm_settings_default_provider_is_nvidia(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = api_settings.get_api_settings()
    assert settings.llm.provider == "nvidia"
```

Chay:

```bash
cd chatbot/backend
pytest test/core/test_api_settings.py -v
```

### 9.2 Smoke test CORS qua HTTP thuc

Sau khi `main.py`/`health.py` da co noi dung o muc 5-6, chay:

```bash
cd chatbot/backend
uvicorn app.main:app --reload --port 8000
```

Kiem tra origin duoc allow (thay `http://localhost:5173` bang gia tri dang
co trong `CORS_ORIGINS`):

```bash
curl -i -X OPTIONS http://localhost:8000/health \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET"
```

Ky vong response co header:

```text
access-control-allow-origin: http://localhost:5173
```

Kiem tra origin KHONG duoc allow:

```bash
curl -i -X OPTIONS http://localhost:8000/health \
  -H "Origin: http://evil.example.com" \
  -H "Access-Control-Request-Method: GET"
```

Ky vong response KHONG co header `access-control-allow-origin` (hoac
FastAPI/Starlette tra ve khong co header CORS tuong ung, tuy version).

Health check thuong:

```bash
curl http://localhost:8000/health
```

Ky vong:

```json
{"status": "ok"}
```

---

## 10. Done Khi

- [ ] `app/core/api_settings.py` ton tai voi `get_api_settings()`,
  `CorsSettings`, `LlmSettings`, `ApiSettings`.
- [ ] `get_api_settings()` doc `CORS_ORIGINS`, `LLM_PROVIDER`, `LLM_API_KEY`,
  `LLM_CHAT_MODEL` tu env, co default hop ly cho tung bien khong bat buoc.
- [ ] `CORS_ORIGINS=*` bi tu choi voi `ValueError` ro rang (do dung
  `allow_credentials=True`).
- [ ] `LLM_PROVIDER` ngoai whitelist (`nvidia`/`openai`) bi tu choi.
- [ ] `app/main.py` khoi tao `FastAPI()`, gan `CORSMiddleware` dung
  `api_settings.cors.allow_origins`, include `health` router.
- [ ] `app/api/health.py` co route `GET /health` tra `{"status": "ok"}`.
- [ ] `requirements.txt` co `fastapi`, `uvicorn[standard]`,
  `langchain-nvidia-ai-endpoints`.
- [ ] `chatbot/.env.example` co day du bien dang duoc code doc thuc te
  (`DATABASE_URL`, `QDRANT_URL`, `OCR_MARKDOWN_DIR`, `NVIDIA_API_KEY`,
  `NVIDIA_EMBEDDING_MODEL`) cong voi bien moi (`CORS_ORIGINS`,
  `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_CHAT_MODEL`).
- [ ] `ChunkingSettings`/`RetrievalSettings` trong `settings_loader.py`
  khong bi sua.
- [ ] Test `test_api_settings.py` pass.
- [ ] `curl -X OPTIONS /health` voi origin hop le tra
  `access-control-allow-origin` dung origin do; origin la khong nam trong
  `CORS_ORIGINS` khong co header nay.
- [ ] Chua chot chinh thuc provider LLM cho `rag_chain.py` — muc 4 chi la
  de xuat, can nguoi dung/chu du an xac nhan truoc khi Guide 18 code thuc
  `get_chat_llm()`.

---

## 11. Phu Thuoc / Thu Tu Lam Truoc

```text
- Khong phu thuoc guide nao trong .docs/guild_implement/*.md ve mat schema
  (khong dong toi 9 bang DB, khong dong toi ChunkingSettings/RetrievalSettings).
- Guide 15 (QDRANT_VECTORSTORE) va Guide 14 (EMBEDDING) da gia dinh
  QDRANT_URL/QDRANT_API_KEY/NVIDIA_API_KEY ton tai trong env — guide nay
  chinh thuc dua chung vao .env.example, khong doi cach doc trong
  qdrant_client.py/embedder.py.
- Guide 18 (RAG_ANSWER_CHAIN) can ket qua muc 4 cua guide nay (LLM_PROVIDER
  da chot) truoc khi viet app/llm/generator.py va noi vao rag_chain.py.
- Neu sau nay co guide rieng cho router /api/v1/rag, /api/v1/documents,
  /api/v1/ingestion, guide do se import app trong main.py da tao o day va
  goi app.include_router(...) tiep, khong tao lai FastAPI() instance moi.
```
