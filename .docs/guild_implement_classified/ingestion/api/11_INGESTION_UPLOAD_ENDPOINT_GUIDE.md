# 11. Endpoint POST /api/v1/documents/upload

**Last Updated:** 2026-07-14

Mục tiêu:

```text
Nhan file (multipart/form-data: file, title)
Luu file goc vao thu muc uploads/ tren server
Tao record documents + document_versions moi (hoac version moi neu document_key da ton tai)
Tra ve JSON khop 100% shape cua mockApi.uploadDocument() trong admin-frontend
De admin-frontend chi doi 1 dong goi fetch, khong doi UI/step khac
```

Endpoint này là route đầu tiên trong `app/api/ingestion.py`. Các guide 12/13/14/15 sẽ thêm
route OCR (`/versions/{id}/ocr`), metadata (`/versions/{id}/metadata`), ingest
(`/versions/{id}/ingest`) vào cùng file này, dùng cùng `router = APIRouter(...)`.

---

## 1. File Cần Tạo/Sửa

```text
chatbot/backend/app/api/ingestion.py            (MỚI — chưa tồn tại)
chatbot/backend/app/main.py                     (SỬA — hiện đang rỗng 0 dòng)
chatbot/backend/requirements.txt                (SỬA — thêm fastapi/uvicorn/multipart)
chatbot/backend/test/api/test_upload_endpoint.py (MỚI)
```

`app/api/health.py` và `app/api/__init__.py` đã tồn tại nhưng đang rỗng — guide này không
đụng tới 2 file đó, chỉ tạo router mới cho ingestion.

---

## 2. Trạng Thái Hiện Tại (đã xác nhận bằng đọc code, không suy đoán)

```text
app/main.py: 0 dong. Chua co FastAPI() instance, chua co CORSMiddleware, chua include_router nao.
app/api/health.py, app/api/__init__.py: ton tai nhung rong.
app/api/ingestion.py: CHUA TON TAI, phai tao moi trong guide nay.
app/ingestion/repository.py: CHUA TON TAI (chi con file .pyc cu trong __pycache__, source da bi xoa).
  -> Guide 12 (Postgres Ingestion Repository) se tao lai file nay cho luong full parent/child chunks.
  -> Vi upload chi tao document + version (chua co chunk), guide nay KHONG phu thuoc guide 12,
     va se tu viet helper get_or_create_document_type rieng, gon, trong ingestion.py.
app/databases/models/documents.py: DA CO Document, DocumentVersion, Department,
  DocumentType, DocumentRecipient voi cac field dung nhu liet ke o muc 6.
app/databases/session.py: DA CO AsyncSessionLocal + get_session() (FastAPI dependency,
  yield AsyncSession, khong tu commit).
app/schemas/enums.py: DA CO FileType, DocumentType (danh sach code hop le).
requirements.txt: hien KHONG co fastapi, uvicorn, python-multipart. Da xac nhan bang
  cach chay python -c "import fastapi" trong .venv va bi ModuleNotFoundError.
```

---

## 3. Dependency Cần Thêm

Thêm vào `chatbot/backend/requirements.txt`:

```text
fastapi>=0.111
uvicorn[standard]>=0.30
python-multipart>=0.0.9
```

`python-multipart` là bắt buộc — FastAPI dùng nó để parse `multipart/form-data`
(`UploadFile`, `Form`). Thiếu package này, request upload sẽ lỗi 500 lúc runtime dù code
Python không báo lỗi khi import.

Cài đặt:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot
.venv\Scripts\pip.exe install -r backend\requirements.txt
```

---

## 4. Response Contract (khớp `mockClient.js` — bắt buộc giữ đúng tên field)

Đọc lại `admin-frontend/src/api/mockClient.js` (`uploadDocument`) và
`admin-frontend/src/steps/UploadStep.jsx` xác nhận shape response admin đang đợi:

```json
{
  "document_id": 101,
  "document_key": "quy-che-dao-tao",
  "document_version_id": 101,
  "version_key": "quy-che-dao-tao-v1",
  "source_path": "uploads/quy-che-dao-tao-v1.pdf",
  "file_type": "pdf",
  "checksum": "3f9a...64-hex-chars",
  "size": 245678,
  "ocr_status": "not_started",
  "review_status": "not_reviewed",
  "rag_status": "not_indexed"
}
```

Lưu ý quan trọng khác với mock:

```text
Mock tra checksum dang "sha256:" + hex ngan (khong chuan). Response THAT phai tra sha256
hex digest THUAN, dung 64 ky tu — khop voi cot document_versions.checksum String(64) va
DocumentVersionMetadata.checksum(max_length=64) trong app/schemas/documents.py. KHONG
them prefix "sha256:" vi se vuot 64 ky tu va insert DB se fail.
UploadStep.jsx chi doc field: document_key, version_key, source_path, file_type, checksum,
ocr_status. Cac field con lai (document_id, document_version_id, review_status, rag_status,
size) khong hien UI ngay nhung PipelineContext van luu de cac step sau (OCR, metadata,
ingest) dung document_version_id goi API.
```

---

## 5. Helper Slugify Và File Type

Trong `app/api/ingestion.py`:

```python
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import Document, DocumentType, DocumentVersion
from app.databases.session import get_session

router = APIRouter(prefix="/documents", tags=["ingestion"])

UPLOAD_DIR = Path("uploads")

# Map extension thực của file -> giá trị FileType enum (app/schemas/enums.py).
# "image" la category chung cho anh scan, khong phai extension.
EXTENSION_TO_FILE_TYPE: dict[str, str] = {
    "pdf": "pdf",
    "doc": "doc",
    "docx": "docx",
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "tif": "image",
    "tiff": "image",
    "html": "html",
    "htm": "html",
    "txt": "txt",
    "csv": "csv",
    "xlsx": "xlsx",
    "pptx": "pptx",
    "md": "md",
}


def slugify(text: str) -> str:
    """
    Chuyen tieu de tieng Viet co dau thanh document_key an toan.
    Tuong duong ham slugify() trong admin-frontend/src/api/mockClient.js,
    de document_key sinh ra o backend giong voi tri giac admin dang thay tu mock.
    """
    text = (text or "").strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:60]


def resolve_file_type(filename: str) -> str:
    if "." not in filename:
        raise HTTPException(status_code=400, detail="File không có phần mở rộng")
    ext = filename.rsplit(".", 1)[-1].lower()
    file_type = EXTENSION_TO_FILE_TYPE.get(ext)
    if file_type is None:
        raise HTTPException(
            status_code=400,
            detail=f"Không hỗ trợ phần mở rộng .{ext}",
        )
    return file_type
```

`resolve_file_type` chỉ chấp nhận đúng danh sách extension mà admin-frontend cho chọn
(`UploadStep.jsx` input `accept=".pdf,.docx,.doc,.png,.jpg,.jpeg,.tiff,.html"`). Nếu sau này
frontend mở thêm loại file, cập nhật `EXTENSION_TO_FILE_TYPE` cùng lúc.

---

## 6. Helper Ghi Document + DocumentVersion

`Document.document_type_id` là FK not-null nhưng ở bước upload, người dùng **chưa chọn**
`document_type` (bước đó nằm ở guide 13 — PUT metadata). Dùng tạm `document_type = "unknown"`,
sẽ được cập nhật thật ở bước metadata sau.

```python
DOCUMENT_TYPE_NAMES = {
    "unknown": "Unknown",
}


async def _get_or_create_document_type(session: AsyncSession, code: str) -> DocumentType:
    result = await session.execute(select(DocumentType).where(DocumentType.code == code))
    row = result.scalar_one_or_none()
    if row:
        return row

    row = DocumentType(code=code, name=DOCUMENT_TYPE_NAMES.get(code, code))
    session.add(row)
    await session.flush()
    return row


async def _find_document_by_key(session: AsyncSession, document_key: str) -> Document | None:
    result = await session.execute(
        select(Document).where(Document.document_key == document_key)
    )
    return result.scalar_one_or_none()


async def _count_versions(session: AsyncSession, document_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
    )
    return int(result.scalar_one())


async def create_initial_document_version(
    session: AsyncSession,
    *,
    title: str,
    file_type: str,
    checksum: str,
) -> tuple[Document, DocumentVersion]:
    """
    Tao document moi (neu document_key chua ton tai) hoac tao version moi cho
    document da ton tai cung document_key (slug tu title trung nhau).

    Gia dinh MVP: title trung slug = cung 1 document, nen se sinh version_key
    tang dan (v1, v2, ...). Neu can 2 document khac nhau nhung cung ten, phai
    doi title hoac xu ly them o buoc sau — ngoai pham vi guide nay.
    """
    document_type = await _get_or_create_document_type(session, "unknown")

    base_key = slugify(title)
    if not base_key:
        base_key = f"tai-lieu-{checksum[:8]}"

    document = await _find_document_by_key(session, base_key)

    if document is None:
        document = Document(
            document_key=base_key,
            title=title,
            document_type_id=document_type.id,
            domain="",
            audience=[],
        )
        session.add(document)
        await session.flush()
        version_index = 1
    else:
        version_index = await _count_versions(session, document.id) + 1

    version = DocumentVersion(
        document_id=document.id,
        version_key=f"{document.document_key}-v{version_index}",
        title=title,
        file_type=file_type,
        checksum=checksum,
        ocr_status="not_started",
        review_status="not_reviewed",
        rag_status="not_indexed",
    )
    session.add(version)
    await session.flush()

    return document, version
```

Lưu ý:

```text
document_key la unique constraint trong DB (models/documents.py). Neu 2 lan upload cung
title -> cung slug -> code coi la version moi cua document cu, KHONG tao document trung.
version_key duy nhat nho suffix "-v{n}" tang dan theo so version da co.
source_path chua duoc set trong ham nay vi phai biet version_key truoc de dat ten file
(xem muc 7) — se gan version.source_path ngay sau khi ghi file xong, van trong transaction.
```

---

## 7. Route `POST /api/v1/documents/upload`

```python
class UploadDocumentResponse(BaseModel):
    document_id: int
    document_key: str
    document_version_id: int
    version_key: str
    source_path: str
    file_type: str
    checksum: str
    size: int
    ocr_status: str
    review_status: str
    rag_status: str


@router.post("/upload", response_model=UploadDocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    session: AsyncSession = Depends(get_session),
) -> UploadDocumentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Thiếu tên file")

    file_type = resolve_file_type(file.filename)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File tải lên trống")

    checksum = hashlib.sha256(content).hexdigest()
    resolved_title = title.strip() or Path(file.filename).stem

    async with session.begin():
        document, version = await create_initial_document_version(
            session,
            title=resolved_title,
            file_type=file_type,
            checksum=checksum,
        )

        original_ext = file.filename.rsplit(".", 1)[-1].lower()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = UPLOAD_DIR / f"{version.version_key}.{original_ext}"
        dest_path.write_bytes(content)

        version.source_path = dest_path.as_posix()

    return UploadDocumentResponse(
        document_id=document.id,
        document_key=document.document_key,
        document_version_id=version.id,
        version_key=version.version_key,
        source_path=version.source_path,
        file_type=version.file_type,
        checksum=version.checksum,
        size=len(content),
        ocr_status=version.ocr_status,
        review_status=version.review_status,
        rag_status=version.rag_status,
    )
```

Giải thích thứ tự trong `async with session.begin()`:

```text
1. Insert document/document_version, flush de co version.id + version_key.
2. Chi sau khi co version_key moi ghi file vat ly xuong uploads/, dat ten file
   theo version_key (vd "quy-che-dao-tao-v1.pdf") de khong trung ten giua cac
   document/version khac nhau du file goc cung ten.
3. Gan version.source_path roi de session.begin() tu commit khi thoat block.
4. Neu buoc ghi file loi (disk day, permission...), exception se lam session.begin()
   rollback DB — khong de lai document/version "mo coi" khong co file.
```

`UPLOAD_DIR = Path("uploads")` là đường dẫn tương đối tính từ working directory lúc chạy
`uvicorn` (thường là `chatbot/backend/`). Thư mục `uploads/` sẽ được tạo tự động nếu chưa có.

---

## 8. Đăng Ký Router Trong `main.py`

`app/main.py` hiện đang **rỗng hoàn toàn**. Guide này thêm phần tối thiểu để chạy/test được
endpoint; các guide 12-18 sau sẽ tiếp tục `include_router` thêm cho OCR/metadata/ingest/RAG.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ingestion import router as ingestion_router

app = FastAPI(title="CTU Service Chatbot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # admin-frontend (Vite dev server)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router, prefix="/api/v1")
```

`allow_origins` hiện chỉ liệt kê rõ origin dev của admin-frontend — không dùng `["*"]` cùng
`allow_credentials=True` (FastAPI/Starlette sẽ từ chối kết hợp này). Nếu sau này deploy domain
khác, thêm origin đó vào danh sách, không đổi sang wildcard.

Chạy thử server:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

---

## 9. Lưu Ý Bảo Mật (chưa xử lý trong guide này, cần biết trước khi deploy)

```text
Endpoint nay hien KHONG co authentication/authorization — bat ky ai goi duoc
POST /api/v1/documents/upload deu tao duoc document/version moi va ghi file vao server.
Theo CLAUDE.md quy tac chung cua bo guide, KHONG them JWT/auth trong pham vi guide nay.
Truoc khi mo endpoint nay ra internet/production, can bo sung xac thuc (vd session admin)
o mot guide rieng — ghi nhan de khong quen, khong tu them auth ngoai pham vi yeu cau.
Chua co gioi han kich thuoc file (max upload size) va rate limit — nen bo sung khi
productionize, khong bat buoc cho MVP admin noi bo.
```

---

## 10. Test/Kiểm Thử

### 10.1. Unit test với `TestClient`

File `chatbot/backend/test/api/test_upload_endpoint.py`. Test override `get_session` để
dùng DB test (guard giống guide 05/12), không đụng DB dev.

```python
import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.databases.models import Document, DocumentVersion
from app.databases.session import AsyncSessionLocal, get_session
from app.main import app

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    raise RuntimeError("Refusing to run upload endpoint tests outside test DB")


async def _override_get_session():
    async with AsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session
client = TestClient(app)


def test_upload_document_creates_version(tmp_path):
    sample_pdf = tmp_path / "quy_che_dao_tao.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4 fake content for test")

    with open(sample_pdf, "rb") as fh:
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("quy_che_dao_tao.pdf", fh, "application/pdf")},
            data={"title": "Quy chế đào tạo test"},
        )

    assert response.status_code == 201
    body = response.json()

    assert body["document_key"] == "quy-che-dao-tao-test"
    assert body["version_key"] == "quy-che-dao-tao-test-v1"
    assert body["file_type"] == "pdf"
    assert len(body["checksum"]) == 64
    assert body["ocr_status"] == "not_started"
    assert body["review_status"] == "not_reviewed"
    assert body["rag_status"] == "not_indexed"


def test_upload_rejects_unsupported_extension(tmp_path):
    bad_file = tmp_path / "data.exe"
    bad_file.write_bytes(b"binary")

    with open(bad_file, "rb") as fh:
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("data.exe", fh, "application/octet-stream")},
            data={"title": "Không hợp lệ"},
        )

    assert response.status_code == 400
```

Cần thêm `httpx` vào `requirements.txt` (FastAPI `TestClient` dùng `httpx` làm transport từ
Starlette 0.37+). Cleanup: xoá row test trong DB test và file trong `uploads/` sau khi test
chạy — có thể thêm fixture `autouse` xoá theo `document_key` bắt đầu bằng `quy-che-dao-tao-test`.

Chạy test:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/api/test_upload_endpoint.py
```

### 10.2. Test tay bằng curl

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@./Noi_quy_KTX_nam_2016.pdf" \
  -F "title=Nội quy KTX năm 2016"
```

Kết quả mong đợi:

```json
{
  "document_id": 1,
  "document_key": "noi-quy-ktx-nam-2016",
  "document_version_id": 1,
  "version_key": "noi-quy-ktx-nam-2016-v1",
  "source_path": "uploads/noi-quy-ktx-nam-2016-v1.pdf",
  "file_type": "pdf",
  "checksum": "<64 hex chars>",
  "size": 123456,
  "ocr_status": "not_started",
  "review_status": "not_reviewed",
  "rag_status": "not_indexed"
}
```

Gọi lại lần 2 với cùng title/file, kỳ vọng `document_key` giữ nguyên nhưng `version_key`
tăng lên `-v2`, và `document_id` không đổi.

---

## 11. Lỗi Dễ Gặp

### Lỗi: 500 Internal Server Error khi gửi multipart

Nguyên nhân:

```text
Thieu package python-multipart trong requirements.txt/venv.
```

Xử lý:

```text
pip install python-multipart, restart uvicorn.
```

### Lỗi: `checksum` bị cắt/insert DB fail vì quá 64 ký tự

Nguyên nhân:

```text
Copy nguyen logic checksum tu mockClient.js (co prefix "sha256:").
```

Xử lý:

```text
Chi dung hashlib.sha256(content).hexdigest() thuan, khong them prefix.
```

### Lỗi: `UniqueViolation` trên `documents.document_key`

Nguyên nhân:

```text
Race condition: 2 request upload cung slug chay dong thoi, ca 2 deu thay
_find_document_by_key tra None roi cung insert Document moi.
```

Xử lý (MVP, chấp nhận được với traffic thấp của admin nội bộ):

```text
Bat exception IntegrityError quanh session.begin(), tra 409 Conflict va goi lai.
Khong bat buoc xu ly concurrency phuc tap hon trong guide nay.
```

### Lỗi: CORS bị chặn khi admin-frontend gọi từ `http://localhost:5173`

Nguyên nhân:

```text
main.py chua add CORSMiddleware, hoac allow_origins khong khop dung port Vite dang chay.
```

Xử lý:

```text
Kiem tra port thuc te cua `vite` (mac dinh 5173, co the doi), sua allow_origins cho khop.
```

---

## 12. Done Khi

- [ ] `app/api/ingestion.py` tồn tại với `router = APIRouter(prefix="/documents", ...)`.
- [ ] `POST /api/v1/documents/upload` nhận đúng `multipart/form-data` (`file`, `title`).
- [ ] File gốc được lưu vào `uploads/{version_key}.{ext}` trên server.
- [ ] `documents` + `document_versions` được insert đúng, `document_type` tạm `"unknown"`.
- [ ] Upload lần 2 cùng title tạo version mới (`-v2`) trên cùng `document_key`, không tạo
      document trùng.
- [ ] Response JSON đúng field/tên như `mockClient.js.uploadDocument()` — admin-frontend chỉ
      cần đổi `mockApi.uploadDocument` thành `fetch()` thật, không sửa `UploadStep.jsx`.
- [ ] `checksum` trả về là sha256 hex thuần, đúng 64 ký tự.
- [ ] `app/main.py` có `FastAPI()`, `CORSMiddleware`, và `include_router` cho ingestion.
- [ ] `requirements.txt` có `fastapi`, `uvicorn[standard]`, `python-multipart`, `httpx`.
- [ ] Test upload endpoint pass trên DB test (`ctu_student_service_test`).
- [ ] curl thủ công trả đúng shape JSON như mục 10.2.

---

## 13. Phụ Thuộc / Thứ Tự Làm Trước

```text
Khong phu thuoc cung xong guide 09 (Markdown Reader) hay guide 12 (Postgres Ingestion
Repository) — endpoint nay chi tao document + version rong (chua co chunk/markdown).

Guide 12/13/14/15 se tiep tuc THEM ROUTE vao chinh file app/api/ingestion.py nay:
  - Guide 12/13: PUT /api/v1/versions/{id}/metadata, POST /api/v1/versions/{id}/ocr.
  - Guide 14/15: POST /api/v1/versions/{id}/ingest (goi chunker + repository + embedding +
    Qdrant tu guide 09/10/12/14/15 that).

Khi guide 12 (Postgres Ingestion Repository) hoan thanh, co the (khong bat buoc) refactor
_get_or_create_document_type() trong ingestion.py de tai su dung ham cung ten trong
app/ingestion/repository.py, tranh trung logic — nhung khong lam thay doi API contract cua
guide nay.
```
