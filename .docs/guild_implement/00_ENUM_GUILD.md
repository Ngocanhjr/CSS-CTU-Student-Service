# 00. Hướng Dẫn Implement `app/schemas/enums.py`

**Last Updated:** 2026-07-04

Source of truth cho enum: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md` (phần Status Enums,
Domain Values, Asset Type Values).

File này hướng dẫn tạo/cập nhật enum dùng chung cho các schema:

```text
documents.py
assets.py
chunks.py
rag.py
```

Trong code hiện tại nên dùng `typing.Literal`, chưa cần tạo class kế thừa `Enum`.

## Mục Tiêu

`enums.py` là nơi duy nhất định nghĩa các giá trị hợp lệ cho:

- status workflow (ocr/review/rag/index);
- loại tài liệu;
- domain;
- file type;
- asset type + validity;
- quan hệ document version -> asset;
- chunk type.

Không khai báo lại enum trong `documents.py`, `assets.py`, `chunks.py`.

## Quyết Định Đã Chốt

Không thêm các enum/giá trị sau (đã loại khỏi schema hiện tại):

```text
Priority
ChunkingStrategy
ocr_status = "not_required"
CollectionStatus
VersionRole
Confidentiality
CitationType
```

Rule quan trọng:

```text
File parser-only/Markdown/text van dung ocr_status = "done" sau khi parser validation hoan tat.
Index eligibility: ocr_status = done AND review_status = approved.
Student RAG chi dung version co review_status = approved AND rag_status = published.
```

## Quy Ước Key Và ID

Enum không quản lý identifier, nhưng các schema dùng chung quy ước sau:

```text
id           = khoa ky thuat noi bo cua database
document_key = ma on dinh cua tai lieu trong YAML/RAG
version_key  = ma on dinh cua version trong YAML/RAG
asset_key    = ma on dinh cua asset trong YAML/RAG
```

Không dùng `document_id`/`version_id` trong YAML/RAG schema nếu đã chọn quy ước `*_key`.

## File Cần Sửa

```text
chatbot/backend/app/schemas/enums.py
```

## Import

```python
from typing import Literal
```

## Status Enums

Khớp chính xác phần Status Enums trong spec 05.

### `OcrStatus`

Không có `"not_required"`.

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

Ý nghĩa quan trọng:

```text
indexed   = da index, co the dung cho admin/internal search
published = duoc student RAG su dung
```

### `IndexStatus`

Dùng cho `document_chunks.index_status`.

```python
IndexStatus = Literal[
    "not_indexed",
    "indexed",
    "deactivated",
    "failed",
]
```

### `ValidityStatus`

Đã bỏ khỏi schema DB và YAML metadata. Không định nghĩa enum này trong MVP.

## Document Enums

### `DocumentType`

```python
DocumentType = Literal[
    "noi_quy",
    "quy_trinh",
    "bieu_mau",
    "hoi_dap",
    "ke_hoach",
    "thong_bao",
    "bao_cao",
    "huong_dan",
    "quyet_dinh",
    "cong_van",
    "thong_tu",
    "nghi_quyet",
    "unknown",
]
```

### `Audience`

```python
Audience = Literal[
    "sinh_vien",
    "can_bo",
    "giang_vien",
    "cong_khai",
]
```

`cong_khai` duoc phep trong student retrieval, cung voi `sinh_vien`.

### `Domain`

Khớp phần Domain Values trong spec 05 (`documents.domain`).

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

Ý nghĩa:

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

Ý nghĩa:

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

## Full Template Gợi Ý

Nếu cần viết lại file `enums.py`, có thể dùng khung này:

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

DocumentType = Literal[
    "noi_quy",
    "quy_trinh",
    "bieu_mau",
    "hoi_dap",
    "ke_hoach",
    "thong_bao",
    "bao_cao",
    "huong_dan",
    "quyet_dinh",
    "cong_van",
    "thong_tu",
    "nghi_quyet",
    "unknown",
]

Audience = Literal[
    "sinh_vien",
    "can_bo",
    "giang_vien",
    "cong_khai",
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

## Common Mistakes Cần Tránh

- Không thêm `Priority`.
- Không thêm `ChunkingStrategy`.
- Không thêm `"not_required"` vào `OcrStatus`.
- Không thêm `CollectionStatus`, `VersionRole`, `Confidentiality`, `CitationType`. Đã loại khỏi schema.
- Không thêm `ValidityStatus`. Field này đã bỏ khỏi DB và YAML metadata.
- Không dùng enum tiếng Anh cũ như `procedure`, `form`, `faq` cho `DocumentType`; dùng `quy_trinh`, `bieu_mau`, `hoi_dap`.
- Không nhầm `AssetType = "form"` với `DocumentType = "bieu_mau"`.
- Không nhầm `RagStatus.indexed` với `RagStatus.published`.

## Test Sau Khi Sửa

Chạy tại:

```text
chatbot/backend
```

Import test:

```powershell
python -c "from app.schemas.enums import AssetType, DocumentAssetRelationType; print('asset enums ok')"
python -c "from app.schemas.enums import Audience, OcrStatus, RagStatus, DocumentType, ChunkType, Domain; print('core enums ok')"
```

Validation test nhanh với Pydantic:

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

Kết quả mong đợi:

```text
asset enums ok
core enums ok
blocked not_required
```

## Reconciliation Guide

- `22_CHUNKING_RETRIEVAL_RECONCILIATION_GUIDE.md` là normative contract cuối cho page-aware structural chunking, payload và retrieval expansion.
- Nếu guide cũ mâu thuẫn với Guide 22, ưu tiên Guide 22.
