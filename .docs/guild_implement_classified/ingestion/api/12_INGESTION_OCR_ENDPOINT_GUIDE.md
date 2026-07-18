# 12. Endpoint POST /api/v1/versions/{id}/ocr

**Last Updated:** 2026-07-14

```text
Muc tieu file nay:
- Tiep app/api/ingestion.py (CHUA TON TAI): them route POST
  /api/v1/versions/{id}/ocr chay OCR/parser THUC bang LlamaParse.
- Response phai khop dung field ma admin-frontend/src/api/mockClient.js
  ham runOcr() dang tra ve: {ocr_status, canonical_markdown_path,
  page_count, char_count, markdown}.
- Chot 2 phuong an: (a) MVP dong bo (khuyen nghi lam truoc), (b) 202 + job
  id poll qua GET /api/v1/ingestion/jobs/{id} (nang cap sau, chua lam
  trong guide nay).
- Neu ro mau thuan pham vi voi tai lieu da co (xem muc 0.2) truoc khi
  code, vi day la quyet dinh nghiep vu can nguoi chu du an xac nhan.
```

File này chỉ làm `app/api/ingestion.py` (route OCR), `app/schemas/ingestion.py` (response
schema) và `app/ingestion/ocr_client.py` (wrapper gọi LlamaParse SDK thật). Route
`POST /api/v1/versions/{id}/metadata` (`saveMetadata`) và `POST /api/v1/versions/{id}/ingest`
(`runIngest`) là phần việc của guide khác, **không** làm ở đây.

---

## 0. Trạng Thái Thực Tế Trước Khi Sửa (đã đọc code, không suy đoán)

### 0.1. Code hiện tại

```text
chatbot/backend/app/api/ingestion.py        -> CHUA TON TAI, phai tao moi.
chatbot/backend/app/api/routes/             -> thu muc rong. Theo dung tien le
                                                da chot o guide 06 (dat router
                                                truc tiep trong app/api/, KHONG
                                                dung app/api/routes/), guide nay
                                                lam giong vay.
chatbot/backend/app/schemas/ingestion.py    -> CHUA TON TAI, phai tao moi.
chatbot/backend/app/ingestion/ocr_client.py -> CHUA TON TAI, phai tao moi.
chatbot/backend/app/databases/models/documents.py
    -> DocumentVersion da co san cac cot can dung: source_path (Text,
       default ""), canonical_markdown_path (Text, default ""),
       ocr_status (String(50), default "not_started"), status_note
       (Text, nullable).
chatbot/backend/app/databases/models/ingestion.py
    -> IngestionJob da co san (id, document_version_id, job_type, status,
       current_step, total_chunks, processed_chunks, error_message,
       started_at, finished_at, created_by). Guide nay KHONG dung bang
       nay cho phuong an (a) MVP dong bo; chi lien quan neu lam phuong
       an (b) o guide sau.
chatbot/backend/app/databases/session.py   -> DA CO get_session() (async
                                               generator), dung Depends()
                                               binh thuong.
chatbot/backend/requirements.txt           -> KHONG co llama-parse hay
                                               llama-cloud-services, KHONG
                                               co fastapi/uvicorn (them o
                                               guide 01/02, gia dinh guide
                                               do da chay xong truoc guide
                                               nay).
chatbot/.env / chatbot/.env.example
    -> chatbot/.env (may dev thuc te) KHONG co LLAMA_CLOUD_API_KEY,
       KHONG co OCR_MARKDOWN_DIR trong .env.example (du .env thuc te co
       dong OCR_MARKDOWN_DIR tro toi thu muc ngoai repo). Chua co code
       nao doc OCR_MARKDOWN_DIR qua os.getenv() truoc guide nay - guide
       nay la noi DAU TIEN thuc su doc bien nay.
```

### 0.2. Mâu thuẫn phạm vi cần xác nhận trước khi code

`chatbot/backend/README.md` và `.docs/spec/ctu-service/08_OCR_INGESTION_SPEC.md` (đã đọc
trực tiếp) đang chốt rõ:

```text
README.md dong 7:
"This backend receives pre-processed canonical Markdown files that have
already been OCR'd and reviewed externally. LlamaParse and the OCR
pipeline run outside this codebase."

README.md dong 55:
"app/ocr does not exist. OCR/LlamaParse processing happens outside this
backend."

08_OCR_INGESTION_SPEC.md dong 8:
"OCR/LlamaParse chạy bên ngoài backend này. Backend nhận canonical
Markdown đã được OCR và review từ trước..."
```

Nhiệm vụ được giao cho guide này lại yêu cầu ngược lại: viết 1 route THỰC trong backend gọi
LlamaParse. Đây là **thay đổi phạm vi backend** so với 2 tài liệu trên, không phải lỗi chính
tả nhỏ. Guide này vẫn viết route theo đúng yêu cầu được giao (vì được chỉ định rõ, không tự
suy diễn bỏ qua), nhưng ghi rõ:

```text
- Day la MO RONG so voi README.md va 08_OCR_INGESTION_SPEC.md hien tai
  (ca 2 file do dang noi OCR nam ngoai backend).
- Neu chu du an dong y giu route nay, PHAI cap nhat lai README.md va
  08_OCR_INGESTION_SPEC.md de tranh 2 tai lieu do noi sai trang thai
  thuc te (viec cap nhat 2 file spec/README nay KHONG nam trong pham vi
  guide nay - guide nay chi viet code + note lai mau thuan, khong tu
  sua tai lieu spec).
- Endpoint POST /api/v1/versions/{id}/ocr cung KHONG nam trong
  .docs/spec/ctu-service/06_API_SPEC.md (spec goc chi co
  /api/v1/rag/answer, /api/v1/ingestion/jobs, /api/v1/documents,
  /api/v1/document-versions/{id}). Duong dan nay theo dung quy uoc dat
  ten cua admin-frontend/src/api/mockClient.js (uploadDocument/runOcr/
  saveMetadata/runIngest), KHONG theo /api/v1/ingestion/jobs nhu
  06_API_SPEC.md. Ghi ro day la MO RONG, khong doi lai
  /api/v1/ingestion/jobs da chot trong 06_API_SPEC.md.
```

### 0.3. Giả định về `source_path` (điều kiện tiên quyết chưa có)

Chưa có endpoint nào trong 9-bảng backend này để upload file gốc (PDF/doc). `uploadDocument()`
trong `mockClient.js` chỉ là mock, không map với route thật nào đã tồn tại. Route
`POST /api/v1/versions/{id}/ocr` trong guide này **giả định** `DocumentVersion.source_path`
đã được điền từ trước (ví dụ chèn thủ công qua SQL/script khi test, hoặc từ 1 route upload sẽ
được viết ở guide riêng khác, ngoài phạm vi guide này). Nếu `source_path` rỗng, route trả lỗi
rõ ràng (mục 5), không tự bịa file.

---

## 1. File Cần Tạo/Sửa

```text
chatbot/backend/app/schemas/ingestion.py          (MOI - tao)
chatbot/backend/app/ingestion/ocr_client.py       (MOI - tao)
chatbot/backend/app/api/ingestion.py              (MOI - tao)
chatbot/backend/app/main.py                       (SUA - them include_router)
chatbot/backend/requirements.txt                  (SUA - them SDK LlamaParse)
chatbot/.env.example                              (SUA - them LLAMA_CLOUD_API_KEY, OCR_MARKDOWN_DIR)
chatbot/backend/test/api/test_ingestion_ocr.py    (MOI - tao)
```

Không sửa `app/databases/models/documents.py` (cột đã đủ dùng), không sửa
`app/schemas/enums.py`.

---

## 2. SDK LlamaParse Dùng Ở Đây

Đã tra cứu tài liệu SDK chính thức (`developers.llamaindex.ai`, README package
`llama-index-readers-llama-parse`) vì project **chưa có** dòng import LlamaParse nào trong
code hiện tại (đã grep toàn `chatbot/backend`, không thấy `llama_parse`/`llama_cloud` import
ở đâu — chỉ có chuỗi text `"LlamaParse API"` trong 1 file YAML mẫu
`app/ingestion/test/test_3266.md` dùng làm giá trị `ocr_engine`, không phải code gọi SDK).

Có 2 package cùng tồn tại trên PyPI, chọn 1:

```text
llama-parse (package cu, con duoc maintain o muc README cu)
    -> from llama_parse import LlamaParse
    -> LlamaParse(api_key=..., result_type="markdown").load_data(path) / aload_data(path)
    -> tra list Document, doc.text la noi dung markdown.

llama-cloud-services (package moi hon, ke thua tu llama-parse, API tuong tu)
    -> cung co class LlamaParse voi load_data()/aload_data(), tuong thich nguoc.
```

Guide này **chọn `llama-parse`** (`pip install llama-parse`) vì API `load_data()`/`aload_data()`
đơn giản, trả `list[Document]` với `doc.text` là markdown — khớp thẳng với nhu cầu "1 file
PDF -> 1 chuỗi markdown" của route này, không cần các tính năng nâng cao (agentic mode, custom
schema) của `llama-cloud-services`. Nếu sau này cần các tính năng đó, đổi package là việc của
guide riêng, không đổi ngầm trong guide này.

Biến môi trường: **`LLAMA_CLOUD_API_KEY`** (tên chuẩn theo tài liệu chính thức, không phải tên
tự đặt). Xác nhận qua đọc `chatbot/.env` và `chatbot/.env.example`: cả 2 file **chưa có** biến
này — đây là biến môi trường MỚI phải thêm (mục 7), không phải biến đã tồn tại bị đặt tên khác.

```python
from llama_parse import LlamaParse

parser = LlamaParse(
    api_key=api_key,          # hoac bo qua, SDK tu doc os.getenv("LLAMA_CLOUD_API_KEY")
    result_type="markdown",   # "markdown" hoac "text", du an nay luon can markdown
    verbose=True,
)

documents = parser.load_data("./file.pdf")        # dong bo, blocking toi khi xong
documents = await parser.aload_data("./file.pdf")  # async

canonical_markdown = "\n\n".join(doc.text for doc in documents)
```

`load_data()`/`aload_data()` nhận cả 1 path lẻ hoặc `list[str]` (nhiều file); route này luôn
truyền 1 path lẻ vì mỗi `document_version` tương ứng 1 file gốc (`source_path`).

---

## 3. Hai Phương Án Thiết Kế Route

### 3.1. Phương án (a) — MVP đồng bộ (khuyến nghị làm trước)

```text
Client goi POST /api/v1/versions/{id}/ocr
  -> server chay LlamaParse dong bo (await aload_data(...))
  -> server ghi canonical_markdown ra file, update DocumentVersion
  -> server tra response day du {ocr_status, canonical_markdown_path,
     page_count, char_count, markdown} ngay trong 1 request duy nhat.
```

Ưu điểm: đơn giản, khớp thẳng với `runOcr()` hiện tại của `mockClient.js` (`await` 1 lần, nhận
kết quả luôn), không cần thêm bảng/trạng thái polling.

Nhược điểm: OCR file lớn (nhiều chục trang) có thể chạy vài chục giây tới vài phút. Request
HTTP đứng chờ suốt thời gian đó — cần tăng timeout ở cả client (fetch trong admin-frontend) và
server (uvicorn/reverse proxy nếu có), rủi ro timeout ở proxy hoặc trình duyệt nếu file quá lớn.

Guide này **implement phương án (a)**, vì đây là MVP và số lượng file xử lý đồng thời trong
giai đoạn đầu thấp (admin thao tác tuần tự, không phải traffic sinh viên).

### 3.2. Phương án (b) — 202 + job id, poll qua `ingestion_jobs` (nâng cấp sau)

```text
Client goi POST /api/v1/versions/{id}/ocr
  -> server tao 1 dong ingestion_jobs (job_type="ocr", status="pending")
  -> server tra ngay 202 Accepted + {job_id}
  -> server chay OCR nen (BackgroundTasks/Celery/worker rieng), cap nhat
     ingestion_jobs.status/current_step/error_message theo tien do
  -> client poll GET /api/v1/ingestion/jobs/{id}, doc current_step
     (dung field nay, khong dung current_stage - da chot trong
     06_API_SPEC.md va 08_OCR_INGESTION_SPEC.md) toi khi status="done"
     hoac "failed"
```

Đây là hướng đúng cho production (không giữ HTTP request mở hàng phút, chịu được nhiều job
đồng thời), nhưng cần thêm route `GET /api/v1/ingestion/jobs/{id}` (đã có trong
`06_API_SPEC.md`, thuộc guide riêng khác trong bộ `api/`, hiện guide đó chưa được viết) và một
cơ chế chạy nền (tối thiểu là `fastapi.BackgroundTasks`, hoặc worker riêng nếu cần chịu tải
cao hơn). **Không implement trong guide này** — ghi rõ đây là việc của guide nâng cấp sau, dùng
lại đúng bảng `ingestion_jobs` đã có sẵn 9 cột cần thiết (`status`, `current_step`,
`error_message`, `started_at`, `finished_at`).

---

## 4. Schema Response `app/schemas/ingestion.py` (File Mới)

Đối chiếu đúng field mock trả về trong `runOcr()`
(`chatbot/admin-frontend/src/api/mockClient.js` dòng 89-95):

```javascript
return {
  ocr_status: 'need_review',
  canonical_markdown_path: `canonical/${slugify(title || fileName)}.md`,
  page_count: 2,
  char_count: markdown.length,
  markdown,
}
```

Định nghĩa schema thật, kế thừa `StrictSchema` giống mọi schema khác trong `app/schemas/`:

```python
from __future__ import annotations

from pydantic import Field

from app.schemas.base import StrictSchema
from app.schemas.enums import OcrStatus


class VersionOcrResponse(StrictSchema):
    """
    Response cho POST /api/v1/versions/{id}/ocr.

    Khop dung field ma admin-frontend/src/api/mockClient.js::runOcr() dang
    tra ve, de sau nay guide tich hop admin-frontend (18_ADMIN_INGESTION_
    INTEGRATION_GUIDE.md) chi can doi tu mock sang fetch() ma khong phai
    sua lai component dang doc {ocr_status, canonical_markdown_path,
    page_count, char_count, markdown}.

    - ocr_status: trang thai OCR sau khi chay xong. MVP dong bo nay luon
      tra "done" khi LlamaParse thanh cong (khong tra "need_review" nhu
      mock - quyet dinh "can review hay khong" la viec cua nguoi duyet o
      buoc metadata/review sau, khong phai OCR tu danh gia chat luong
      chinh no). Neu LlamaParse loi, route raise HTTPException, khong tra
      response nay voi ocr_status="failed" (xem muc 6).
    - canonical_markdown_path: duong dan file .md da luu tren server, ghi
      lai vao DocumentVersion.canonical_markdown_path.
    - page_count: so trang OCR nhan dien duoc (tu so luong Document ma
      LlamaParse tra ve - load_data() tra 1 Document/trang khi khong gop
      trang).
    - char_count: do dai chuoi canonical_markdown (len(), tinh theo Python
      str, khop voi cach mock dung markdown.length ben JS).
    - markdown: toan bo noi dung markdown, de admin-frontend hien preview
      ngay khong can goi them request doc file.
    """

    ocr_status: OcrStatus
    canonical_markdown_path: str = Field(min_length=1)
    page_count: int = Field(ge=0)
    char_count: int = Field(ge=0)
    markdown: str
```

Lưu ý:

```text
- KHONG tao request body schema rieng cho endpoint nay. Route nhan
  version id qua path param (int), khong can body - toan bo input (file
  goc) da nam san o DocumentVersion.source_path (xem muc 0.3), khong yeu
  cau client gui lai fileName/title nhu mock JS dang lam (mock JS nhan
  {fileName, title} vi no chua co khai niem "version da ton tai trong
  DB", con route thuc o day luon gan voi 1 version_id cu the).
- Neu sau nay can cho phep client override tuy chon (vi du chon lai
  result_type, ngon ngu OCR), them 1 request schema moi luc do, khong bia
  truoc trong guide nay.
```

---

## 5. `app/ingestion/ocr_client.py` (File Mới)

Tách wrapper LlamaParse ra module riêng (giống cách `app/embedding/embedder.py` gói
`NVIDIAEmbeddings`, `app/vectorstore/qdrant_client.py` gói `QdrantClient`), để route FastAPI
không import trực tiếp SDK bên thứ 3, dễ mock trong test.

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from llama_parse import LlamaParse

load_dotenv(find_dotenv())

OCR_MARKDOWN_DIR = Path(os.getenv("OCR_MARKDOWN_DIR", "./data/markdown"))


@dataclass(frozen=True)
class OcrResult:
    markdown: str
    page_count: int
    canonical_markdown_path: str


def get_ocr_parser() -> LlamaParse:
    """Tao LlamaParse client that.

    Raise ValueError ro rang neu thieu LLAMA_CLOUD_API_KEY, giong dung
    pattern get_embedding() trong app/embedding/embedder.py (raise ngay
    khi thieu config, khong fallback im lang).
    """
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable is not set.")

    return LlamaParse(api_key=api_key, result_type="markdown", verbose=True)


async def run_ocr(source_path: str, *, output_key: str) -> OcrResult:
    """Chay LlamaParse tren 1 file that, ghi ket qua markdown ra dia.

    Args:
        source_path: duong dan file goc (DocumentVersion.source_path).
        output_key: ten file khong duoi mo rong dung de dat ten file
            markdown dau ra, thuong la version_key cua document_version.

    Returns:
        OcrResult voi markdown day du, so trang, va duong dan file da luu.

    Raises:
        ValueError: source_path rong hoac file khong ton tai tren dia.
    """
    if not source_path or not source_path.strip():
        raise ValueError("source_path is empty; upload file goc truoc khi chay OCR")

    file_path = Path(source_path)
    if not file_path.exists():
        raise ValueError(f"source_path khong ton tai tren dia: {source_path}")

    parser = get_ocr_parser()
    documents = await parser.aload_data(str(file_path))
    if not documents:
        raise ValueError(f"LlamaParse khong tra ve noi dung nao cho file: {source_path}")

    page_count = len(documents)
    markdown = "\n\n".join(doc.text for doc in documents)

    OCR_MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OCR_MARKDOWN_DIR / f"{output_key}.md"
    output_path.write_text(markdown, encoding="utf-8")

    return OcrResult(
        markdown=markdown,
        page_count=page_count,
        canonical_markdown_path=str(output_path),
    )
```

Lưu ý:

```text
- run_ocr() KHONG chen page marker <!-- page: N --> tu dong. LlamaParse
  tra list Document (1 Document/trang trong che do mac dinh), nhung
  khong tu chen marker theo dung format PAGE_RE cua
  app/ingestion/parsing/page_markers.py (regex <!-- page: N -->). Neu
  can markdown dau ra co page marker de chunking o Guide 10A dung duoc
  ngay, PHAI them buoc chen marker giua cac trang (vi du noi
  f"<!-- page: {i+1} -->\n{doc.text}" cho tung doc), KHONG gia dinh
  LlamaParse tu lam viec nay. Guide nay CHUA them buoc do (ngoai pham vi
  yeu cau ban dau - chi yeu cau khop 5 field response cua mock), ghi ro
  de nguoi lam Guide chunking sau khong bi bat ngo khi markdown dau ra
  thieu marker.
- output_key nen la version_key (duy nhat, on dinh), KHONG dung
  document_version_id (int) lam ten file de tranh doi ten khi id doi
  giua cac lan seed/test.
- get_ocr_parser() tao instance moi mien lan goi, khong cache/lru_cache
  nhu get_embedding() - LlamaParse client nhe, khong can warm-up rieng;
  neu can toi uu sau, xu ly o guide khac.
```

---

## 6. Router `app/api/ingestion.py` (File Mới)

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import DocumentVersion
from app.databases.session import get_session
from app.ingestion.ocr_client import run_ocr
from app.schemas.ingestion import VersionOcrResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


@router.post("/versions/{version_id}/ocr", response_model=VersionOcrResponse)
async def run_version_ocr(
    version_id: int,
    session: AsyncSession = Depends(get_session),
) -> VersionOcrResponse:
    """Chay OCR/parser (LlamaParse) tren file goc cua 1 document_version.

    Phuong an (a) MVP dong bo (xem muc 3.1 cua guide nay): request cho
    toi khi LlamaParse xong roi tra ket qua luon trong 1 response. Khong
    tao ingestion_jobs row o day - do la phuong an (b), chua implement.
    """
    version = await session.get(DocumentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="document_version not found")

    if not version.source_path:
        raise HTTPException(
            status_code=400,
            detail="document_version chua co source_path; upload file goc truoc khi chay OCR",
        )

    version.ocr_status = "processing"
    await session.commit()

    try:
        result = await run_ocr(version.source_path, output_key=version.version_key)
    except ValueError as exc:
        version.ocr_status = "failed"
        version.status_note = str(exc)
        await session.commit()
        logger.warning("OCR failed for version_id=%s: %s", version_id, exc)
        raise HTTPException(status_code=502, detail=f"OCR failed: {exc}") from exc

    version.ocr_status = "done"
    version.canonical_markdown_path = result.canonical_markdown_path
    version.status_note = None
    await session.commit()

    return VersionOcrResponse(
        ocr_status="done",
        canonical_markdown_path=result.canonical_markdown_path,
        page_count=result.page_count,
        char_count=len(result.markdown),
        markdown=result.markdown,
    )
```

Lưu ý:

```text
- Router KHONG tu khai bao prefix="/api/v1" trong APIRouter(...), dung
  dung quy tac da chot o Guide 01 muc 5.3 va Guide 06 muc 3: prefix chi
  ap dung 1 lan luc app.include_router(...) trong main.py.
- ocr_status trung gian "processing" duoc ghi vao DB TRUOC khi goi
  run_ocr() (chay co the mat vai chuc giay), de nguoi xem DB/dashboard
  khac (vi du listDocuments() o guide 19) thay dung trang thai dang
  chay, khong bi "dong bang" tren gia tri cu trong luc cho.
- Loi tu run_ocr() (ValueError: thieu LLAMA_CLOUD_API_KEY, source_path
  khong ton tai, LlamaParse tra rong) deu duoc bat thanh HTTPException
  502 "OCR failed: ...", KHONG rate response 200 voi
  ocr_status="failed" nhu VersionOcrResponse gia dinh - VersionOcrResponse
  chi mo ta response THANH CONG. Truong hop loi, client (admin-frontend)
  doc HTTP status code + {"detail": "..."} theo dung convention
  HTTPException chuan cua Guide 00 muc 3.2, khong parse OcrStatus tu loi.
- Khong dung try/except bao ngoai HTTPException 404/400 phia tren -
  2 truong hop do la loi input ro rang (version khong ton tai, thieu
  source_path), can fail nhanh truoc khi cham vao LlamaParse.
```

---

## 7. Wiring Và Cập Nhật Dependency

### 7.1. `app/main.py`

Sau Guide 01/02/06, `main.py` đã có sẵn đoạn comment placeholder cho ingestion. Uncomment
đúng 2 dòng (import + include_router) cho router này, giữ nguyên comment của
rag/documents/versions (các router đó vẫn chưa tồn tại):

```python
from app.api.health import router as health_router
from app.api.reference_data import router as reference_data_router
from app.api.ingestion import router as ingestion_router
from app.embedding.embedder import get_embedding

# ... (giu nguyen phan lifespan/app/add_middleware tu Guide 01/02)

app.include_router(health_router)
app.include_router(reference_data_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")

# from app.api.rag import router as rag_router
# from app.api.documents import router as documents_router
# from app.api.versions import router as versions_router
#
# app.include_router(rag_router, prefix="/api/v1")
# app.include_router(documents_router, prefix="/api/v1")
# app.include_router(versions_router, prefix="/api/v1")
```

Sau khi wiring, endpoint public là:

```text
POST /api/v1/versions/{id}/ocr
```

### 7.2. `requirements.txt`

Thêm 1 dòng (theo đúng quyết định mục 2):

```text
llama-parse>=0.5
```

### 7.3. `chatbot/.env.example`

Thêm vào cuối file (không xoá biến cũ):

```env
# LlamaParse OCR (doc boi app/ingestion/ocr_client.py)
LLAMA_CLOUD_API_KEY=replace_with_your_llama_cloud_api_key

# Thu muc luu canonical markdown sau OCR (doc boi app/ingestion/ocr_client.py)
OCR_MARKDOWN_DIR=./data/markdown
```

Ghi chú: `chatbot/.env` (may dev thuc te) da co dong `OCR_MARKDOWN_DIR` tro ra ngoai repo
(`../../../../CTU-Service/nlcs/06_Processing/01_OCR_Output`) nhung bien nay **chua** duoc code
nao doc truoc guide nay - `app/ingestion/ocr_client.py` (muc 5) la noi dau tien thuc su goi
`os.getenv("OCR_MARKDOWN_DIR", ...)`. Khong doi gia tri trong `.env` thuc te cua may dev, chi
bo sung dong con thieu vao `.env.example` de file mau phan anh dung bien dang duoc code dung.

---

## 8. Vấn Đề Streaming Step UI (`onStep` Callback)

`runOcr()` trong `mockClient.js` (dòng 76-96) mô phỏng 4 bước UI qua callback `onStep`:

```text
queued -> parsing -> markdown -> page_markers
```

Với REST đồng bộ (phương án (a) đã chọn ở mục 3.1), server chỉ trả **1 response duy nhất** sau
khi toàn bộ OCR xong - không có cách nào gửi 4 sự kiện `onStep` rời rạc qua 1 request/response
HTTP thông thường. Có 2 lựa chọn cho phía React admin (Guide 18 trong bộ `api/`,
`18_ADMIN_INGESTION_INTEGRATION_GUIDE.md`, sẽ tự quyết định cụ thể, guide này chỉ nêu 2 hướng):

### 8.1. Lựa chọn A - bỏ step UI, hiện 1 loading state chung (khuyến nghị cho MVP)

```text
Khi goi POST /api/v1/versions/{id}/ocr, component React hien 1 spinner/
progress bar chung ("Dang OCR tai lieu, co the mat vai chuc giay..."),
trong luc await fetch(...), khong con 4 buoc rieng
queued/parsing/markdown/page_markers.
```

Ưu điểm: đơn giản, khớp thẳng với route đồng bộ đã viết ở mục 6, không cần đổi kiến trúc
backend. Nhược điểm: mất UX chi tiết theo bước mà mock hiện có.

### 8.2. Lựa chọn B (optional) - Server-Sent Events (`StreamingResponse`, `text/event-stream`)

Nếu muốn giữ UX 4 bước, có thể đổi route thành SSE:

```python
from fastapi.responses import StreamingResponse
import json


async def _ocr_event_stream(version_id: int, session: AsyncSession):
    yield f"data: {json.dumps({'key': 'queued', 'state': 'running'})}\n\n"
    # ... goi tung buoc thuc te cua run_ocr(), yield sau moi buoc ...
    yield f"data: {json.dumps({'key': 'parsing', 'state': 'running'})}\n\n"
    result = await run_ocr(...)
    yield f"data: {json.dumps({'key': 'parsing', 'state': 'done'})}\n\n"
    # buoc markdown/page_markers hien tai KHONG phai buoc rieng trong
    # run_ocr() (ham nay chay 1 luot, khong co checkpoint giua doc va
    # ghi file) - muon co event rieng cho tung buoc phai tach lai
    # run_ocr() thanh cac ham con, ngoai pham vi guide nay.
    yield f"data: {json.dumps({'ocr_status': 'done', ...})}\n\n"


@router.post("/versions/{version_id}/ocr/stream")
async def run_version_ocr_stream(version_id: int, session=Depends(get_session)):
    return StreamingResponse(
        _ocr_event_stream(version_id, session),
        media_type="text/event-stream",
    )
```

Đây là **optional, chưa implement trong guide này**. Lý do không làm ngay:

```text
- run_ocr() hien tai (muc 5) la 1 ham nguyen khoi goi aload_data() 1 lan,
  khong co checkpoint giua cac buoc queued/parsing/markdown/page_markers
  nhu mock JS dang gia lap bang setTimeout co dinh. Muon co event SSE
  thuc cho tung buoc, phai tach run_ocr() thanh nhieu buoc con co the
  bao cao tien do rieng - day la thay doi kien truc lon hon pham vi
  "viet 1 route OCR dong bo" duoc giao cho guide nay.
- Buoc "page_markers" trong mock KHONG khop voi hanh vi LlamaParse thuc
  (da neu ro o muc 5: LlamaParse khong tu chen page marker). Neu lam SSE
  thuc, buoc nay phai doi ten/y nghia, khong the gia lap dung 4 ten buoc
  cu cua mock.
```

Nếu chốt dùng SSE, phải tạo 1 guide riêng để tách `run_ocr()` thành các bước có thể báo cáo
tiến độ, không nhồi vào việc mở rộng route đồng bộ đã có ở mục 6.

---

## 9. Test / Kiểm Thử

### 9.1. Test tự động (mock `run_ocr`, không gọi LlamaParse thật)

File:

```text
chatbot/backend/test/api/test_ingestion_ocr.py
```

Test không gọi LlamaParse thật (tốn phí, cần API key, không xác định trước nội dung trả về).
Dùng `monkeypatch` để thay `app.api.ingestion.run_ocr` bằng 1 hàm giả, giống cách project đã
dùng `monkeypatch`/fixture DB test trong `test/api/test_reference_data.py` (Guide 06) và
`test/databases/test_database_models.py`:

```python
import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.databases.models import Department, Document, DocumentType, DocumentVersion
from app.databases.session import AsyncSessionLocal
from app.ingestion.ocr_client import OcrResult
from app.main import app

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    raise RuntimeError(
        "Refusing to run ingestion OCR API tests outside ctu_student_service_test"
    )

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _cleanup(session):
    await session.execute(delete(Document).where(Document.document_key == "test-ocr-doc"))
    await session.execute(delete(DocumentType).where(DocumentType.code == "test_ocr_type"))
    await session.commit()


@pytest.fixture
async def seeded_version(tmp_path):
    fake_source = tmp_path / "source.pdf"
    fake_source.write_bytes(b"%PDF-1.4 fake content")

    async with AsyncSessionLocal() as session:
        await _cleanup(session)
        doc_type = DocumentType(code="test_ocr_type", name="Test OCR Type", is_active=True)
        session.add(doc_type)
        await session.flush()

        document = Document(
            document_key="test-ocr-doc",
            title="Tai lieu test OCR",
            document_type_id=doc_type.id,
        )
        session.add(document)
        await session.flush()

        version = DocumentVersion(
            document_id=document.id,
            version_key="test-ocr-doc-v1",
            title="Tai lieu test OCR",
            checksum="0" * 64,
            source_path=str(fake_source),
        )
        session.add(version)
        await session.commit()
        version_id = version.id

    yield version_id

    async with AsyncSessionLocal() as session:
        await _cleanup(session)


def test_run_ocr_returns_expected_fields(seeded_version, monkeypatch):
    async def fake_run_ocr(source_path: str, *, output_key: str) -> OcrResult:
        return OcrResult(
            markdown="# Tieu de\n\nNoi dung test.",
            page_count=1,
            canonical_markdown_path=f"canonical/{output_key}.md",
        )

    monkeypatch.setattr("app.api.ingestion.run_ocr", fake_run_ocr)

    client = TestClient(app)
    response = client.post(f"/api/v1/versions/{seeded_version}/ocr")

    assert response.status_code == 200
    body = response.json()
    assert body["ocr_status"] == "done"
    assert body["canonical_markdown_path"] == "canonical/test-ocr-doc-v1.md"
    assert body["page_count"] == 1
    assert body["char_count"] == len("# Tieu de\n\nNoi dung test.")
    assert body["markdown"] == "# Tieu de\n\nNoi dung test."
    assert set(body.keys()) == {
        "ocr_status",
        "canonical_markdown_path",
        "page_count",
        "char_count",
        "markdown",
    }


def test_run_ocr_returns_404_for_missing_version():
    client = TestClient(app)
    response = client.post("/api/v1/versions/999999999/ocr")
    assert response.status_code == 404


def test_run_ocr_returns_400_when_source_path_missing(seeded_version, monkeypatch):
    async def clear_source_path():
        async with AsyncSessionLocal() as session:
            version = await session.get(DocumentVersion, seeded_version)
            version.source_path = ""
            await session.commit()

    import asyncio

    asyncio.run(clear_source_path())

    client = TestClient(app)
    response = client.post(f"/api/v1/versions/{seeded_version}/ocr")
    assert response.status_code == 400


def test_run_ocr_returns_502_when_ocr_raises(seeded_version, monkeypatch):
    async def failing_run_ocr(source_path: str, *, output_key: str):
        raise ValueError("LlamaParse timeout")

    monkeypatch.setattr("app.api.ingestion.run_ocr", failing_run_ocr)

    client = TestClient(app)
    response = client.post(f"/api/v1/versions/{seeded_version}/ocr")

    assert response.status_code == 502
    assert "LlamaParse timeout" in response.json()["detail"]
```

Chạy:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/api/test_ingestion_ocr.py -v
```

### 9.2. Test thủ công bằng curl (cần `LLAMA_CLOUD_API_KEY` thật)

Chuẩn bị: chèn thủ công 1 dòng `document_versions` có `source_path` trỏ tới 1 file PDF thật
trên máy (hoặc dùng script `chatbot/backend/app/ingestion/index_document.py` làm tham khảo
cách tạo dữ liệu test), sau đó:

```bash
curl -X POST http://localhost:8000/api/v1/versions/1/ocr
```

Kỳ vọng (thành công, sau khi LlamaParse xử lý xong):

```json
{
  "ocr_status": "done",
  "canonical_markdown_path": "data/markdown/<version_key>.md",
  "page_count": 3,
  "char_count": 4521,
  "markdown": "# ...noi dung markdown day du..."
}
```

Trường hợp thiếu `LLAMA_CLOUD_API_KEY`:

```bash
curl -i -X POST http://localhost:8000/api/v1/versions/1/ocr
```

Kỳ vọng: `502 Bad Gateway`, body `{"detail": "OCR failed: LLAMA_CLOUD_API_KEY environment
variable is not set."}`.

---

## 10. Lỗi Dễ Gặp

### Lỗi: `ModuleNotFoundError: No module named 'llama_parse'`

Nguyên nhân:

```text
Chua cai llama-parse vao venv.
```

Xử lý:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pip install llama-parse
```

### Lỗi: request treo rất lâu rồi mới trả response (hoặc timeout ở proxy/browser)

Nguyên nhân:

```text
Day la hanh vi DUNG cua phuong an (a) MVP dong bo (muc 3.1) voi file
nhieu trang. Khong phai bug.
```

Xử lý:

```text
Neu file thuong xuyen qua lon/lau, chuyen sang phuong an (b) (muc 3.2)
o guide nang cap sau, khong tim cach "sua" phuong an dong bo.
```

### Lỗi: `502 OCR failed: source_path khong ton tai tren dia`

Nguyên nhân:

```text
DocumentVersion.source_path dang tro toi 1 duong dan tren may khac
(vi du duong dan luc seed test tren may dev A, chay tren may B khong co
file do), hoac file da bi di chuyen/xoa sau khi ghi source_path vao DB.
```

Xử lý:

```text
Xac nhan lai file goc con ton tai dung duong dan da luu trong
source_path truoc khi goi OCR. Guide nay khong tu tai lai file tu
source_url.
```

### Lỗi: `ResponseValidationError` vì `page_count`/`char_count` âm hoặc `markdown` rỗng

Nguyên nhân:

```text
LlamaParse tra ve list Document rong (vi du file PDF hong, khong doc
duoc noi dung) nhung khong raise loi - VersionOcrResponse validate
page_count/char_count >= 0 nen truong hop nay se fail o buoc
`if not documents: raise ValueError(...)` trong run_ocr() (muc 5)
truoc khi cham toi VersionOcrResponse, khong phai loi Pydantic.
```

Xử lý:

```text
Kiem tra file goc that su co noi dung doc duoc (khong bi corrupt, khong
phai file scan trang trang).
```

---

## 11. Done Khi

- [ ] `app/schemas/ingestion.py` có `VersionOcrResponse(ocr_status, canonical_markdown_path,
  page_count, char_count, markdown)`, kế thừa `StrictSchema`.
- [ ] `app/ingestion/ocr_client.py` có `run_ocr()`/`get_ocr_parser()`, đọc
  `LLAMA_CLOUD_API_KEY` và `OCR_MARKDOWN_DIR` qua `os.getenv()`, raise `ValueError` rõ ràng khi
  thiếu key hoặc `source_path` không hợp lệ.
- [ ] `app/api/ingestion.py` có router với `POST /versions/{version_id}/ocr`, KHÔNG tự khai
  báo prefix `/api/v1` trong `APIRouter(...)`.
- [ ] Route trả `404` khi `document_version` không tồn tại, `400` khi thiếu `source_path`,
  `502` khi `run_ocr()` raise lỗi, `200` + `VersionOcrResponse` khi thành công.
- [ ] `DocumentVersion.ocr_status` được cập nhật `processing` trước khi gọi OCR, `done`/`failed`
  sau khi có kết quả; `canonical_markdown_path` được ghi lại khi thành công.
- [ ] `app/main.py` include router này với `prefix="/api/v1"`, giữ nguyên comment placeholder
  cho rag/documents/versions.
- [ ] `requirements.txt` có `llama-parse`.
- [ ] `chatbot/.env.example` có `LLAMA_CLOUD_API_KEY`, `OCR_MARKDOWN_DIR`.
- [ ] `test/api/test_ingestion_ocr.py` pass trên DB test, mock `run_ocr()` (không gọi LlamaParse
  thật), tự cleanup data nó tạo ra.
- [ ] Guide ghi rõ (mục 0.2) đây là MỞ RỘNG so với `README.md` và `08_OCR_INGESTION_SPEC.md`
  hiện tại (2 tài liệu đó đang nói OCR nằm ngoài backend) — chưa tự sửa 2 tài liệu đó.
- [ ] Guide ghi rõ (mục 3.2, mục 8.2) phương án (b) job-id/poll và SSE step UI là nâng cấp sau,
  chưa implement trong guide này.
- [ ] Không thêm bảng DB mới, không sửa `app/schemas/enums.py`, không sửa
  `app/databases/models/documents.py`.

---

## 12. Phụ Thuộc / Thứ Tự Làm Trước

```text
- Phu thuoc 01_APP_MAIN_AND_HEALTH_GUIDE.md va 02_SETTINGS_ENV_CORS_GUIDE.md
  da xong (can FastAPI() instance va cau truc router/main.py da co san).
- Phu thuoc 06_REFERENCE_DATA_ENDPOINT_GUIDE.md ve mat tien le dat router
  (khong dung app/api/routes/, dat truc tiep trong app/api/).
- Route nay dung DocumentVersion.source_path da co san trong 9 bang DB,
  nhung CHUA co endpoint upload file goc nao trong bo guide api/ hien tai
  de tu dong dien cot nay - phai co du lieu source_path truoc khi test
  thu cong (xem muc 0.3). Neu sau nay co guide upload file rieng, guide
  do se la buoc chay TRUOC guide nay trong luong nghiep vu thuc te
  (upload -> OCR -> metadata -> ingest), du ve mat ky thuat guide nay
  khong import code tu guide upload do.
- Guide nang cap phuong an (b) (job id + poll, muc 3.2) can
  GET /api/v1/ingestion/jobs/{id} - route nay CHUA duoc guide nao trong
  bo api/ hien tai viet, se la 1 guide moi sau nay, dung lai dung bang
  ingestion_jobs da co.
- Route POST /api/v1/versions/{id}/metadata (saveMetadata) va
  POST /api/v1/versions/{id}/ingest (runIngest) la 2 guide rieng khac,
  tiep tuc trong cung file app/api/ingestion.py nay (them route moi vao
  router da tao o guide nay, khong tao APIRouter() thu hai).
- 18_ADMIN_INGESTION_INTEGRATION_GUIDE.md (thay mockClient.js bang fetch
  thuc) can guide nay xong truoc, va can quyet dinh muc 8 (bo step UI hay
  lam SSE) truoc khi sua OcrStep.jsx.
```
