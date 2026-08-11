# 06. Endpoint du lieu tham chieu (departments, document-types)

**Last Updated:** 2026-07-14

```text
Muc tieu file nay:
- Tao GET /api/v1/departments va GET /api/v1/document-types, doc thuc tu
  PostgreSQL (bang departments, document_types trong 9 bang da chot).
- Thay the phan mock tinh trong admin-frontend/src/api/referenceData.js
  (chi phan departments/documentTypes, KHONG dong toi cac list enum tinh khac).
- Neu ro audienceOptions/domainOptions/assetTypes/ocrStatuses/reviewStatuses/
  ragStatuses la enum co dinh trong app/schemas/enums.py, KHONG can bang DB,
  KHONG bat buoc phai co endpoint rieng.
```

Guide nay nam trong bo `api/` (sau `01_APP_MAIN_AND_HEALTH_GUIDE.md` va
`02_SETTINGS_ENV_CORS_GUIDE.md`), dung lai dung skeleton `app/main.py` va
pattern router da duoc 2 guide do chot, khong tao lai `FastAPI()` instance moi.

---

## 0. Trang Thai Thuc Te Truoc Khi Sua (da doc code, khong suy doan)

```text
chatbot/backend/app/databases/models/documents.py
    -> Department(id, code, name, description, is_active) da co san.
    -> DocumentType(id, code, name, description, is_active) da co san.
    -> Ca hai da duoc export trong app/databases/models/__init__.py.

chatbot/backend/app/databases/session.py
    -> AsyncSessionLocal (async_sessionmaker) da co san.
    -> get_session() la async generator yield AsyncSession, dung duoc lam
       FastAPI Depends() ngay, KHONG can viet lai.

chatbot/backend/app/api/
    -> health.py da co router (tu Guide 01), KHONG co reference_data.py,
       rag.py, documents.py, versions.py, ingestion.py.
    -> app/api/routes/ la thu muc rong, Guide 01 khong dung thu muc nay cho
       health.py (dat truc tiep trong app/api/) — guide nay lam theo dung
       quy uoc do, KHONG dat file moi trong app/api/routes/.

chatbot/backend/app/main.py
    -> Sau Guide 01/02: da co FastAPI(), CORSMiddleware, lifespan warm-up
       embedding, app.include_router(health_router) khong prefix.
    -> Cac dong import/include_router cho rag/documents/versions/ingestion
       dang la comment placeholder, CHUA uncomment vi file router tuong ung
       chua ton tai.
    -> Guide nay se THEM 1 router moi (reference_data) — day la router DAU
       TIEN trong so cac router nghiep vu duoc bat that (health khong tinh
       la router nghiep vu).

chatbot/backend/app/schemas/
    -> assets.py, chunks.py, documents.py, enums.py, base.py, __init__.py
       da co, nhung CHUA co schema nao dung cho response cua endpoint
       reference-data (Department/DocumentType output). Phai tao moi.

chatbot/admin-frontend/src/api/referenceData.js
    -> departments va documentTypes hien la array JS tinh, moi item dang
       { id, code, name, is_active }, KHONG co field description.
    -> audienceOptions, domainOptions, assetTypes, ocrStatuses,
       reviewStatuses, ragStatuses cung la array JS tinh, khop voi cac
       Literal trong app/schemas/enums.py (Audience, Domain, AssetType,
       OcrStatus, ReviewStatus, RagStatus).
    -> File chua co import.meta.env cho API base URL, chua co fetch() nao.

chatbot/admin-frontend/vite.config.js
    -> Da co proxy '/api' -> 'http://localhost:8000' san, nen goi fetch
       tu frontend chi can dung duong dan tuong doi '/api/v1/...' luc dev,
       khong can hardcode host.
```

Ket luan: day la **phan hoan toan moi** — router, schema response, va cach
admin-frontend goi API deu chua ton tai, khong phai sua lai thiet ke da chot.

---

## 1. File Can Tao/Sua

```text
chatbot/backend/app/schemas/reference_data.py    (MOI - tao)
chatbot/backend/app/api/reference_data.py        (MOI - tao)
chatbot/backend/app/main.py                      (SUA - them include_router)
chatbot/backend/test/api/test_reference_data.py  (MOI - tao)
chatbot/admin-frontend/src/api/referenceData.js  (SUA - de xuat, xem muc 6)
```

Khong dong toi `app/databases/models/documents.py` (model da du field can
dung), khong dong toi `app/schemas/enums.py`.

---

## 2. Schema Response

File moi:

```text
chatbot/backend/app/schemas/reference_data.py
```

```python
from __future__ import annotations

from app.schemas.base import StrictSchema


class ReferenceDataItem(StrictSchema):
    """Dung chung cho Department va DocumentType — ca hai co cung shape
    (id, code, name, is_active) sau khi tra ve JSON cho client.

    Day la schema OUTPUT (serialize tu SQLAlchemy row), khong nhan input tu
    client nen `extra="forbid"` cua StrictSchema khong anh huong hanh vi —
    van ke thua StrictSchema de nhat quan voi cac schema khac trong
    app/schemas/, khong phai vi can chan extra field tu client.
    """

    id: int
    code: str
    name: str
    is_active: bool
```

Ghi chu:

```text
Khong dua "description" vao ReferenceDataItem. Yeu cau chi can
{id, code, name, is_active} khop voi shape admin-frontend dang dung
(referenceData.js hien tai khong co field description). Neu sau nay
admin-frontend can hien description, mo rong schema nay, khong tao schema
thu hai trung lap.
```

---

## 3. Router `app/api/reference_data.py`

File moi:

```text
chatbot/backend/app/api/reference_data.py
```

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import Department, DocumentType
from app.databases.session import get_session
from app.schemas.reference_data import ReferenceDataItem

router = APIRouter(tags=["reference-data"])


@router.get("/departments", response_model=list[ReferenceDataItem])
async def list_departments(
    session: AsyncSession = Depends(get_session),
) -> list[ReferenceDataItem]:
    """Tra toan bo phong ban trong bang departments, sap xep theo code.

    Khong loc is_active=True o day — admin-frontend can thay ca phong ban
    dang tat (is_active=False) de hien thi trang thai, khong an di.
    """
    result = await session.execute(select(Department).order_by(Department.code))
    rows = result.scalars().all()
    return [
        ReferenceDataItem(id=row.id, code=row.code, name=row.name, is_active=row.is_active)
        for row in rows
    ]


@router.get("/document-types", response_model=list[ReferenceDataItem])
async def list_document_types(
    session: AsyncSession = Depends(get_session),
) -> list[ReferenceDataItem]:
    """Tra toan bo loai tai lieu trong bang document_types, sap xep theo code."""
    result = await session.execute(select(DocumentType).order_by(DocumentType.code))
    rows = result.scalars().all()
    return [
        ReferenceDataItem(id=row.id, code=row.code, name=row.name, is_active=row.is_active)
        for row in rows
    ]
```

Luu y:

```text
- Router KHONG tu khai bao prefix="/api/v1" trong APIRouter(...) — dung theo
  dung quy tac Guide 01 muc 5.3: prefix "/api/v1" chi ap dung 1 lan luc
  app.include_router(...) trong main.py, tranh prefix bi lap.
- get_session() tra AsyncSession qua Depends(), moi request 1 session moi,
  khong dung AsyncSessionLocal() truc tiep trong route (giu dung pattern
  session.py da thiet ke cho FastAPI).
- Khong filter is_active trong query. Neu can endpoint chi tra active,
  them query param rieng (?is_active=true) o guide sau khi thuc te can,
  khong tu them ngoai yeu cau hien tai.
```

---

## 4. Wiring Vao `app/main.py`

Sau Guide 01/02, `main.py` co doan comment placeholder cho
rag/documents/versions/ingestion. Router `reference_data` la router dau
tien duoc bat that, nen KHONG chi uncomment — phai them 2 dong moi (import +
include_router) canh doan comment do:

```python
from app.api.health import router as health_router
from app.api.reference_data import router as reference_data_router
from app.embedding.embedder import get_embedding

# ... (giu nguyen phan lifespan/app/add_middleware tu Guide 01/02)

app.include_router(health_router)
app.include_router(reference_data_router, prefix="/api/v1")

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

Sau khi wiring xong, 2 endpoint public la:

```text
GET /api/v1/departments
GET /api/v1/document-types
```

---

## 5. Enum Tinh Vs Endpoint `/api/v1/enums` (De Xuat, Khong Bat Buoc)

`audienceOptions`, `domainOptions`, `assetTypes`, `ocrStatuses`,
`reviewStatuses`, `ragStatuses` trong `referenceData.js` la enum co dinh,
khop voi cac `Literal` trong `app/schemas/enums.py` (`Audience`, `Domain`,
`AssetType`, `OcrStatus`, `ReviewStatus`, `RagStatus`). Cac enum nay:

```text
KHONG can bang DB rieng (khong co bang audiences/domains/asset_types nao
trong 9 bang da chot).
KHONG bat buoc phai co endpoint — admin-frontend co the tiep tuc giu list
tinh trong referenceData.js, vi gia tri hiem khi doi va da duoc review/chot
trong app/schemas/enums.py.
```

Rui ro cua viec giu tinh o ca 2 phia: `enums.py` (backend) va
`referenceData.js` (frontend) la 2 noi dinh nghia doc lap, de bi lech khi
mot ben doi truoc (vi du them `Domain` moi trong `enums.py` nhung quen sua
`referenceData.js`).

De xuat (khong bat buoc lam ngay trong guide nay): them
`GET /api/v1/enums` tra:

```json
{
  "audience": ["sinh_vien", "can_bo", "giang_vien", "cong_khai"],
  "domain": ["hoc_vu", "hoc_phi", "..."],
  "document_type": ["noi_quy", "quy_trinh", "..."],
  "asset_type": ["form", "template", "guide", "attachment"],
  "ocr_status": ["not_started", "processing", "done", "failed", "need_review"],
  "review_status": ["not_reviewed", "reviewing", "need_fix", "approved", "rejected"],
  "rag_status": ["not_indexed", "chunked", "embedded", "indexed", "published", "deactivated", "failed"]
}
```

Neu lam, endpoint nay chi doc `typing.get_args(...)` tren tung `Literal`
trong `enums.py` de tranh hard-code trung lap 2 lan trong Python. Khong lam
trong guide nay vi ngoai pham vi yeu cau ban dau (chi departments va
document-types); de nguoi dung/chu du an quyet dinh co can hay khong.

---

## 6. Cap Nhat `admin-frontend/src/api/referenceData.js` (Vi Du, Khong Sua Thuc Trong Guide Nay)

Guide nay chi viet backend + doc; **khong sua truc tiep** file JS trong
repo. Vi du cach thay the phan `departments`/`documentTypes` tinh bang
fetch thuc khi implement thuc te:

```javascript
// referenceData.js — phan departments/documentTypes doi tu array tinh
// sang fetch tu backend. audienceOptions/domainOptions/... giu tinh
// (xem muc 5 cua guide 06_REFERENCE_DATA_ENDPOINT_GUIDE.md).

export async function fetchDepartments() {
  const res = await fetch('/api/v1/departments')
  if (!res.ok) throw new Error(`GET /api/v1/departments failed: ${res.status}`)
  return res.json() // [{ id, code, name, is_active }, ...]
}

export async function fetchDocumentTypes() {
  const res = await fetch('/api/v1/document-types')
  if (!res.ok) throw new Error(`GET /api/v1/document-types failed: ${res.status}`)
  return res.json()
}

// Enum tinh, khop voi app/schemas/enums.py — giu nguyen, khong doi.
export const audienceOptions = ['sinh_vien', 'giang_vien', 'can_bo', 'cong_khai']
export const domainOptions = [
  'hoc_vu', 'hoc_phi', 'dao_tao', 'nghien_cuu_khoa_hoc', 'hop_tac_quoc_te',
  'hoc_bong', 'sinh_vien', 'giang_vien', 'can_bo', 'tuyen_sinh', 'vh_xh',
  'ne_nep', 'nghi_hoc', 'dinh_chi', 'unknown',
]
export const assetTypes = ['form', 'template', 'guide', 'attachment']
export const ocrStatuses = ['not_started', 'processing', 'need_review', 'failed', 'done']
export const reviewStatuses = ['not_reviewed', 'reviewing', 'need_fix', 'approved', 'rejected']
export const ragStatuses = [
  'not_indexed', 'chunked', 'embedded', 'indexed', 'published', 'deactivated', 'failed',
]
```

Luu y quan trong khi implement thuc:

```text
- domainOptions/assetTypes/audienceOptions trong referenceData.js hien tai
  (truoc khi sua) dang KHAC voi Literal thuc trong enums.py (vi du
  assetTypes dang la ['FORM_LINK', 'VIDEO_LINK', 'WEB_LINK'], khong khop
  AssetType = ["form", "template", "guide", "attachment"] trong
  app/schemas/enums.py). Day la lech co san TRUOC guide nay, khong phai do
  guide nay tao ra — khi sua file JS thuc, phai doi theo dung Literal trong
  enums.py, khong giu nguyen gia tri cu.
- Cac component dang import departments/documentTypes truc tiep tu
  referenceData.js (vi du dropdown filter trong DocumentsListPage.jsx) se
  can doi sang goi fetchDepartments()/fetchDocumentTypes() dang async va
  luu ket qua vao React state — day la thay doi call site, ngoai pham vi
  file backend cua guide nay, nhung can luu y khi thuc thi de khong vo
  UI dang dung array dong bo.
- Khong them axios. fetch() thuan da du cho 2 GET don gian nay, dung theo
  quy uoc "KHONG co axios trong package.json" da xac nhan.
```

---

## 7. Test / Kiem Thu

### 7.1. Test tu dong

File:

```text
chatbot/backend/test/api/test_reference_data.py
```

Test phai chay tren DB test (giong guard da dung trong
`test/databases/test_database_models.py` va guide 12), va phai tu cleanup
data no tao ra:

```python
import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.databases.models import Department, DocumentType
from app.databases.session import AsyncSessionLocal
from app.main import app

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    raise RuntimeError(
        "Refusing to run reference-data API tests outside ctu_student_service_test"
    )

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _cleanup(session):
    await session.execute(delete(Department).where(Department.code == "TEST_REFDATA"))
    await session.execute(delete(DocumentType).where(DocumentType.code == "test_refdata"))
    await session.commit()


@pytest.fixture
async def seeded_reference_data():
    async with AsyncSessionLocal() as session:
        await _cleanup(session)
        session.add_all(
            [
                Department(code="TEST_REFDATA", name="Phong Test RefData", is_active=True),
                DocumentType(code="test_refdata", name="Loai Test RefData", is_active=False),
            ]
        )
        await session.commit()
    yield
    async with AsyncSessionLocal() as session:
        await _cleanup(session)


def test_list_departments_returns_seeded_row(seeded_reference_data):
    client = TestClient(app)

    response = client.get("/api/v1/departments")

    assert response.status_code == 200
    items = response.json()
    matches = [item for item in items if item["code"] == "TEST_REFDATA"]
    assert len(matches) == 1
    assert matches[0]["name"] == "Phong Test RefData"
    assert matches[0]["is_active"] is True
    assert set(matches[0].keys()) == {"id", "code", "name", "is_active"}


def test_list_document_types_returns_seeded_row(seeded_reference_data):
    client = TestClient(app)

    response = client.get("/api/v1/document-types")

    assert response.status_code == 200
    items = response.json()
    matches = [item for item in items if item["code"] == "test_refdata"]
    assert len(matches) == 1
    assert matches[0]["is_active"] is False
```

Ghi chu:

```text
- Assert bang "co it nhat 1 item khop code vua seed", KHONG assert do dai
  toan bo list bang so co dinh — DB test co the da co san department/
  document_type khac tu cac test/fixture truoc do, list se khong rong
  tuyet doi tru khi vua reset DB.
- set(matches[0].keys()) == {"id", "code", "name", "is_active"} de xac nhan
  response_model thuc su loai bo "description" (schema chi expose 4 field).
```

Chay:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/api/test_reference_data.py -v
```

### 7.2. Test thu cong bang curl

Sau khi `uvicorn app.main:app --reload --port 8000` dang chay va DB co san
it nhat vai dong trong `departments`/`document_types`:

```bash
curl http://localhost:8000/api/v1/departments
```

Ky vong (vi du):

```json
[
  {"id": 1, "code": "PDT", "name": "Phong Dao tao", "is_active": true},
  {"id": 2, "code": "PCTSV", "name": "Phong Cong tac Sinh vien", "is_active": true}
]
```

```bash
curl http://localhost:8000/api/v1/document-types
```

Ky vong (vi du):

```json
[
  {"id": 1, "code": "noi_quy", "name": "Noi quy", "is_active": true},
  {"id": 2, "code": "quy_trinh", "name": "Quy trinh", "is_active": true}
]
```

Neu DB test dang rong (chua seed department/document_type nao), ca hai
endpoint tra `[]` (khong loi 404/500) — day la hanh vi dung, khong phai bug.

---

## 8. Loi De Gap

### Loi: `ResponseValidationError` vi model tra thieu field

Nguyen nhan:

```text
Query row nhung quen truyen du 4 field (id, code, name, is_active) vao
ReferenceDataItem(...), hoac model row co field is_active = None (khong
nen xay ra vi cot co default=True, nullable=False trong model, nhung neu
DB cu bi migrate sai co the xay ra).
```

Xu ly:

```text
Dam bao cot is_active trong departments/document_types la NOT NULL DEFAULT
TRUE dung nhu 03_SQLALCHEMY_9_TABLES_GUIDE.md da chot. Neu gap du lieu cu
co is_active NULL, sua data, khong sua schema pydantic thanh Optional.
```

### Loi: `curl /api/v1/departments` tra 404

Nguyen nhan:

```text
Quen them app.include_router(reference_data_router, prefix="/api/v1")
trong main.py, hoac quen import router.
```

Xu ly:

```text
Kiem tra lai muc 4 cua guide nay da lam dung 2 dong (import + include_router)
chua, khong chi sua 1 trong 2.
```

### Loi: test fail vi DATABASE_URL tro vao DB dev

Nguyen nhan:

```text
Chua set DATABASE_URL truoc khi chay pytest, hoac set nham DB
ctu_student_service (khong co "_test").
```

Xu ly:

```text
Set lai DATABASE_URL dung ctu_student_service_test truoc khi chay test,
giong guard da co trong test_database_models.py va guide 12.
```

---

## 9. Done Khi

- [ ] `app/schemas/reference_data.py` co `ReferenceDataItem(id, code, name, is_active)`.
- [ ] `app/api/reference_data.py` co router voi `GET /departments` va
  `GET /document-types`, KHONG tu khai bao prefix `/api/v1` trong
  `APIRouter(...)`.
- [ ] `app/main.py` include router nay voi `prefix="/api/v1"`, giu nguyen
  cac comment placeholder rag/documents/versions/ingestion.
- [ ] `GET /api/v1/departments` tra dung field `{id, code, name, is_active}`,
  khong lo field `description`.
- [ ] `GET /api/v1/document-types` tra dung field tuong tu.
- [ ] Ca hai endpoint tra `[]` (khong loi) khi bang DB rong.
- [ ] `test/api/test_reference_data.py` pass tren DB test, tu cleanup data
  no tao ra.
- [ ] Khong tao bang DB moi cho audience/domain/asset_type/ocr_status/
  review_status/rag_status — cac gia tri nay van la `Literal` trong
  `app/schemas/enums.py`.
- [ ] Khong sua `app/databases/models/documents.py`,
  `app/core/settings_loader.py`, `app/schemas/enums.py`.
- [ ] Da ghi ro trong guide (muc 5) rang `GET /api/v1/enums` chi la de xuat,
  chua implement, khong bat buoc.

---

## 10. Phu Thuoc / Thu Tu Lam Truoc

```text
- Phu thuoc 01_APP_MAIN_AND_HEALTH_GUIDE.md da xong (can FastAPI() instance
  va cau truc router/main.py da co san de them include_router moi vao).
- Phu thuoc 02_SETTINGS_ENV_CORS_GUIDE.md ve mat CORS: neu admin-frontend
  (localhost:5173) goi endpoint nay tu browser, CORS_ORIGINS/ALLOWED_ORIGINS
  phai da cho phep origin do (guide 01 da khai bao san localhost:5173 trong
  ALLOWED_ORIGINS cua main.py).
- Khong phu thuoc guide chunking/embedding/Qdrant (10-16) — reference data
  chi doc 2 bang tinh, khong lien quan pipeline RAG.
- Neu sau nay lam GET /api/v1/enums (muc 5, de xuat), nen tao guide con
  moi (vi du 06A) thay vi nhoi them vao guide nay, de giu pham vi guide 06
  dung 2 endpoint da yeu cau.
- Cac guide router con lai trong bo api/ (documents, versions, ingestion,
  rag) khi tao moi, lam theo dung pattern router nay: file rieng trong
  app/api/, APIRouter() khong tu khai bao prefix, include trong main.py
  voi prefix="/api/v1" mot lan duy nhat.
```
