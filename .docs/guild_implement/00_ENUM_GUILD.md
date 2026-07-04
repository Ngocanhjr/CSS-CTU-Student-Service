# 00. Huong Dan Implement `app/schemas/enums.py`

**Last Updated:** 2026-07-04

Source of truth cho enum: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md` (phan Status Enums,
Domain Values, Asset Type Values).

File nay huong dan tao/cap nhat enum dung chung cho cac schema:

```text
documents.py
assets.py
chunks.py
rag.py
```

Trong code hien tai nen dung `typing.Literal`, chua can tao class ke thua `Enum`.

## Muc Tieu

`enums.py` la noi duy nhat dinh nghia cac gia tri hop le cho:

- status workflow (ocr/review/rag/index);
- loai tai lieu;
- domain;
- file type;
- asset type + validity;
- quan he document version -> asset;
- chunk type.

Khong khai bao lai enum trong `documents.py`, `assets.py`, `chunks.py`.

## Quyet Dinh Da Chot

Khong them cac enum/gia tri sau (da loai khoi schema hien tai):

```text
Priority
ChunkingStrategy
ocr_status = "not_required"
CollectionStatus
VersionRole
Confidentiality
CitationType
```

Rule quan trong:

```text
File parser-only/Markdown/text van dung ocr_status = "done" sau khi parser validation hoan tat.
Index eligibility: ocr_status = done AND review_status = approved.
Student RAG chi dung version co review_status = approved AND rag_status = published.
```

## Quy Uoc Key Va ID

Enum khong quan ly identifier, nhung cac schema dung chung quy uoc sau:

```text
id           = khoa ky thuat noi bo cua database
document_key = ma on dinh cua tai lieu trong YAML/RAG
version_key  = ma on dinh cua version trong YAML/RAG
asset_key    = ma on dinh cua asset trong YAML/RAG
```

Khong dung `document_id`/`version_id` trong YAML/RAG schema neu da chon quy uoc `*_key`.

## File Can Sua

```text
chatbot/backend/app/schemas/enums.py
```

## Import

```python
from typing import Literal
```

## Status Enums

Khop chinh xac phan Status Enums trong spec 05.

### `OcrStatus`

Khong co `"not_required"`.

```python
OcrStatus = Literal[
    "not_started",
    "processing",
    "need_review",
    "failed",
    "done",
]
```

### `ReviewStatus`

```python
ReviewStatus = Literal[
    "not_reviewed",
    "reviewing",
    "need_fix",
    "approved",
    "rejected",
]
```

### `RagStatus`

```python
RagStatus = Literal[
    "not_indexed",
    "chunked",
    "embedded",
    "indexed",
    "published",
    "deactivated",
    "failed",
]
```

Y nghia quan trong:

```text
indexed   = da index, co the dung cho admin/internal search
published = duoc student RAG su dung
```

### `IndexStatus`

Dung cho `document_chunks.index_status`.

```python
IndexStatus = Literal[
    "not_indexed",
    "indexed",
    "deactivated",
    "failed",
]
```

### `ValidityStatus`

Chi dung cho `assets.validity_status`. Khong dua vao version metadata.

```python
ValidityStatus = Literal[
    "valid",
    "invalid",
    "expired",
]
```

## Document Enums

### `DocumentType`

```python
DocumentType = Literal[
    "noi_quy",
    "quy_trinh",
    "bieu_mau",
    "hoi_dap",
    "unknown",
]
```

### `Domain`

Khop phan Domain Values trong spec 05 (`documents.domain`).

```python
Domain = Literal[
    "hoc_vu",
    "hoc_phi",
    "dao_tao",
    "nghien_cuu_khoa_hoc",
    "hop_tac_quoc_te",
    "hoc_bong",
    "sinh_vien",
]
```

## Asset Enums

### `AssetType`

```python
AssetType = Literal[
    "form",
    "template",
    "guide",
    "attachment",
]
```

Y nghia:

```text
form       = bieu mau can dien/tai ve
template   = mau tai lieu
guide      = huong dan su dung/thuc hien
attachment = file/link dinh kem khac
```

### `DocumentAssetRelationType`

```python
DocumentAssetRelationType = Literal[
    "required_form",
    "reference",
    "supplement",
    "guide",
]
```

Y nghia:

```text
required_form = bieu mau bat buoc cho thu tuc/tai lieu
reference     = tai lieu/file tham khao
supplement    = file bo sung cho noi dung chinh
guide         = huong dan thuc hien/su dung
```

## File/Chunk Enums

### `FileType`

```python
FileType = Literal[
    "pdf",
    "doc",
    "docx",
    "image",
    "xlsx",
    "pptx",
    "txt",
    "md",
    "html",
    "csv",
    "url",
    "youtube",
]
```

### `ChunkType`

```python
ChunkType = Literal[
    "parent",
    "child",
]
```

## Full Template Goi Y

Neu can viet lai file `enums.py`, co the dung khung nay:

```python
from typing import Literal


OcrStatus = Literal[
    "not_started",
    "processing",
    "need_review",
    "failed",
    "done",
]

ReviewStatus = Literal[
    "not_reviewed",
    "reviewing",
    "need_fix",
    "approved",
    "rejected",
]

RagStatus = Literal[
    "not_indexed",
    "chunked",
    "embedded",
    "indexed",
    "published",
    "deactivated",
    "failed",
]

IndexStatus = Literal[
    "not_indexed",
    "indexed",
    "deactivated",
    "failed",
]

ValidityStatus = Literal[
    "valid",
    "invalid",
    "expired",
]

DocumentType = Literal[
    "noi_quy",
    "quy_trinh",
    "bieu_mau",
    "hoi_dap",
    "unknown",
]

Domain = Literal[
    "hoc_vu",
    "hoc_phi",
    "dao_tao",
    "nghien_cuu_khoa_hoc",
    "hop_tac_quoc_te",
    "hoc_bong",
    "sinh_vien",
]

AssetType = Literal[
    "form",
    "template",
    "guide",
    "attachment",
]

DocumentAssetRelationType = Literal[
    "required_form",
    "reference",
    "supplement",
    "guide",
]

FileType = Literal[
    "pdf",
    "doc",
    "docx",
    "image",
    "xlsx",
    "pptx",
    "txt",
    "md",
    "html",
    "csv",
    "url",
    "youtube",
]

ChunkType = Literal[
    "parent",
    "child",
]
```

## Common Mistakes Can Tranh

- Khong them `Priority`.
- Khong them `ChunkingStrategy`.
- Khong them `"not_required"` vao `OcrStatus`.
- Khong them `CollectionStatus`, `VersionRole`, `Confidentiality`, `CitationType`. Da loai khoi schema.
- `ValidityStatus` chi co `valid`/`invalid`/`expired`, va chi dung cho `assets`.
- Khong dung enum tieng Anh cu nhu `procedure`, `form`, `faq` cho `DocumentType`; dung `quy_trinh`, `bieu_mau`, `hoi_dap`.
- Khong nham `AssetType = "form"` voi `DocumentType = "bieu_mau"`.
- Khong nham `RagStatus.indexed` voi `RagStatus.published`.

## Test Sau Khi Sua

Chay tai:

```text
chatbot/backend
```

Import test:

```powershell
python -c "from app.schemas.enums import AssetType, DocumentAssetRelationType; print('asset enums ok')"
python -c "from app.schemas.enums import OcrStatus, RagStatus, DocumentType, ChunkType, Domain; print('core enums ok')"
```

Validation test nhanh voi Pydantic:

```powershell
@'
from pydantic import BaseModel, ValidationError
from app.schemas.enums import AssetType, DocumentAssetRelationType, OcrStatus

class TestModel(BaseModel):
    asset_type: AssetType
    relation_type: DocumentAssetRelationType
    ocr_status: OcrStatus

print(TestModel(asset_type="form", relation_type="required_form", ocr_status="done"))

try:
    TestModel(asset_type="form", relation_type="required_form", ocr_status="not_required")
except ValidationError as exc:
    print("blocked not_required")
    print(exc)
'@ | python -
```

Ket qua mong doi:

```text
asset enums ok
core enums ok
blocked not_required
```
