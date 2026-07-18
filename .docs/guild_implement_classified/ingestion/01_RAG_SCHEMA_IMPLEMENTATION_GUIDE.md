# 01. Hướng Dẫn Implement Schema RAG Theo Module

**Last Updated:** 2026-07-04

> **Legacy note (9-table contract):** Khong implement/import `DocumentVersionStatus` theo file nay.
> Dung `DocumentVersionStatusFields` va export/test hien hanh theo
> `03_SQLALCHEMY_9_TABLES_GUIDE.md`. Cac phan khac cua file chi dung de tham khao khi
> khong mau thuan voi schema 9 bang hien hanh.

Source of truth cho field YAML metadata: `chatbot/.docs/spec/ctu-service/07_RAG_SPEC.md`.
Source of truth cho schema DB: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`.

File này hướng dẫn cách tách schema thay vì dồn tất cả vào `app/schemas/rag.py`.

Hướng tách đã chốt:

```text
documents.py = metadata tai lieu, version, status, publish rule
assets.py    = bieu mau/file/link lien quan
chunks.py    = noi dung da chia chunk
rag.py       = public import layer neu can import gom
```

## Mục Tiêu

Schema trong `app/schemas` phục vụ 4 việc:

- validate YAML/frontmatter metadata trước khi chunk/index;
- validate asset/form/link liên quan đến tài liệu;
- validate parent/child chunk contract;
- export class để backend import gọn.

Không nhồi toàn bộ database schema vào một file `rag.py`.

## Quyết Định Đã Chốt

1. Không tạo `Priority` enum.
2. Không tạo `ChunkingStrategy` enum.
3. Không dùng `ocr_status = "not_required"`.
4. File Markdown đã parser/review vẫn dùng `ocr_status = "done"`.
5. `is_latest` chỉ là ranking preference, không phải hard filter retrieval.
6. Status workflow (`ocr_status`, `review_status`, `rag_status`, `status_note`) nằm trực tiếp
   trong `document_versions`, không có bảng `document_version_status` riêng.
7. Không dùng `validity_status` trong DB hoặc YAML metadata.
8. Không đưa relationship fields (`replaces`, `amends`, `supplements`...) hoặc `chunking_strategy`
   vào YAML metadata.
9. Index eligibility:

```text
ocr_status = done
AND review_status = approved
```

10. Student RAG hard filter:

```text
review_status = approved
AND rag_status = published
```

## Quy Ước Key Và ID

Dùng thống nhất:

```text
id           = khoa ky thuat noi bo database
document_key = ma on dinh cua tai lieu trong YAML/RAG
version_key  = ma on dinh cua version trong YAML/RAG
asset_key    = ma on dinh cua asset trong YAML/RAG
```

Trong schema metadata/chunk/asset relation, dùng `document_key`, `version_key`, `asset_key`.

Không dùng `document_id`/`version_id` trong YAML/RAG schema nếu đã chọn quy ước `*_key`.

## File Cần Tạo/Sửa

Trong:

```text
chatbot/backend/app/schemas/
```

nên có:

```text
enums.py
documents.py
assets.py
chunks.py
rag.py
__init__.py
```

Nếu muốn tránh lặp `StrictSchema`, có thể tạo thêm `base.py`.

## Thứ Tự Implement

1. Kiểm tra `enums.py`.
2. Tạo `base.py` nếu dùng base chung.
3. Tạo `documents.py`.
4. Tạo `assets.py`.
5. Tạo `chunks.py`.
6. Đổi `rag.py` thành file re-export.
7. Cập nhật `__init__.py` nếu cần.
8. Chạy import test.
9. Chạy validation test.

## `enums.py` Cần Có

Không thêm `Priority`, `ChunkingStrategy`, hoặc `"not_required"`.

Cần có các type (khớp `05_DATABASE_SPEC.md` phần Status Enums):

```python
OcrStatus
ReviewStatus
RagStatus
IndexStatus
DocumentType
FileType
ChunkType
AssetType
DocumentAssetRelationType
Domain
```

Các enum status khớp spec 05:

```python
OcrStatus = Literal[
    "not_started", "processing", "need_review", "failed", "done",
]
ReviewStatus = Literal[
    "not_reviewed", "reviewing", "need_fix", "approved", "rejected",
]
RagStatus = Literal[
    "not_indexed", "chunked", "embedded", "indexed", "published", "deactivated", "failed",
]
IndexStatus = Literal[
    "not_indexed", "indexed", "deactivated", "failed",
]
```

Không còn `CollectionStatus`, `VersionRole`, `Confidentiality`, `CitationType`, `ValidityStatus`.

## Optional: `base.py`

File:

```text
app/schemas/base.py
```

Nội dung:

```python
from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

Lý do dùng `extra="forbid"`:

- bắt lỗi typo như `is_lasted` thay vì `is_latest`;
- tránh chunk/asset/status nhận field lạ;
- chỉ class tổng hợp `DocumentMetadata` mới cho phép metadata phụ bằng `extra="allow"`.

---

# 1. `documents.py`

File:

```text
app/schemas/documents.py
```

## Trách Nhiệm

`documents.py` chứa:

```text
DocumentBaseMetadata
DocumentVersionStatus
DocumentVersionMetadata
DocumentMetadata
```

Không đưa asset detail, chunk detail, ingestion job detail vào file này.

## Import

```python
from __future__ import annotations

from datetime import date

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import (
    DocumentType,
    Audience,
    FileType,
    OcrStatus,
    RagStatus,
    ReviewStatus,
)
```

## `DocumentBaseMetadata`

Khớp YAML metadata: `document_key`, `title`, `responsible_department`, `document_type`,
`domain`, `audience`. DB `documents` không có cột `responsible_department`; field này
được ingest sang bảng `document_recipients`.

```python
class DocumentBaseMetadata(StrictSchema):
    document_key: str = Field(min_length=1)
    title: str = ""
    responsible_department: list[str] = Field(default_factory=list)
    document_type: DocumentType
    domain: str = ""
    audience: list[Audience] = Field(default_factory=list)

    @field_validator("audience", "responsible_department")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]
```

`responsible_department` chứa danh sách `departments.code` từ YAML, ví dụ `["PDT", "PCTSV"]`.
Repository phải map từng code sang `document_recipients(document_version_id, department_id, effective_date)`.

## `DocumentVersionStatus`

Chỉ giữ status workflow nằm trực tiếp trên `document_versions`. Không có `validity_status`,
không có `collection_status`.

```python
class DocumentVersionStatus(StrictSchema):
    ocr_status: OcrStatus = "not_started"
    review_status: ReviewStatus = "not_reviewed"
    rag_status: RagStatus = "not_indexed"
    status_note: str | None = None
```

Rule:

```text
Khong dung ocr_status = "not_required".
Index eligibility: ocr_status = done AND review_status = approved.
Publish (student-facing): review_status = approved AND rag_status = published.
```

## `DocumentVersionMetadata`

Khớp optional fields trong spec 07 + cột `document_versions` spec 05. Không có
`version_label`, `version_role`, `expiry_date`, relationship arrays,
`confidentiality`, `citation_type`, `related_asset_keys`, `validity_status`.

`effective_date` CÓ trong metadata (nullable) và dùng khi map `responsible_department`
sang `document_recipients`. Cột DB `document_recipients.effective_date` là NOT NULL và
nằm trong composite PK, nên repository phải fallback sang `issued_date` khi metadata
để trống (xem `resolve_recipient_effective_date()` ở Guide 12).

```python
class DocumentVersionMetadata(DocumentVersionStatusFields):
    version_key: str = Field(min_length=1)

    code: str | None = None
    issued_date: date | None = None
    effective_date: date | None = None
    is_latest: bool = False

    source_url: str = ""
    source_path: str | None = None
    canonical_markdown_path: str = ""
    file_type: str = "md"
    language: str = "vi"
    issuing_authority: str | None = None
    signer_name: str | None = None
    accessed_date: date | None = None

    checksum: str = Field(min_length=1, max_length=64)
    parser: str | None = None
    ocr_engine: str | None = None
    notes: str = ""
```

Ghi nhớ:

```text
Dung is_latest, khong dung is_lasted.
Khong dung version_label. Neu can phan biet version, dung version_key/code/issued_date.
title chi la tieu de chinh thuc cua van ban, khong gop nhan file/OCR batch vao title.
source_path la path file goc.
canonical_markdown_path la path Markdown da clean/review.
Dung path tuong doi trong repo/vault, khong dung absolute Windows path.
```

## Validator Trong `DocumentVersionMetadata`

Validate publish/index rule (không còn validity_status/confidentiality):

```python
    @model_validator(mode="after")
    def validate_published_rules(self) -> "DocumentVersionMetadata":
        if self.rag_status != "published":
            return self

        if self.ocr_status != "done":
            raise ValueError("published document requires ocr_status done")
        if self.review_status != "approved":
            raise ValueError("published document requires review_status approved")

        return self
```

## `DocumentMetadata`

Class tổng hợp để validate YAML/frontmatter:

```python
class DocumentMetadata(DocumentBaseMetadata, DocumentVersionMetadata):
    model_config = ConfigDict(extra="allow")
```

Lý do `extra="allow"`:

- YAML/frontmatter có thể có field phụ chưa map vào schema;
- ingestion có thể đưa field phụ vào DB `extra_metadata`;
- nhưng schema con vẫn strict để bắt typo.

---

# 2. `assets.py`

File:

```text
app/schemas/assets.py
```

## Trách Nhiệm

`assets.py` chứa schema cho:

```text
AssetMetadata
DocumentAssetRelation
```

## Import

```python
from __future__ import annotations

from pydantic import Field

from app.schemas.base import StrictSchema
from app.schemas.enums import (
    AssetType,
    DocumentAssetRelationType,
)
```

## `AssetMetadata`

Khớp `assets` trong spec 05: `asset_key`, `title`, `asset_type`, `url`, `checksum`.
Không có `validity_status`, `file_path`, `file_type`, `download_url`, `is_latest`,
`review_status`, `rag_status`.

```python
class AssetMetadata(StrictSchema):
    asset_key: str = Field(min_length=1)
    title: str = ""
    asset_type: AssetType
    url: str = ""
    checksum: str | None = None
```

Không cần đưa vào schema metadata giai đoạn đầu:

```text
id
created_at
```

Những field đó thuộc DB/API response.

## `DocumentAssetRelation`

Khớp `document_assets` trong spec 05: `relation_type`, `required_when`, `display_order`.
Không có cột `required` boolean.

```python
class DocumentAssetRelation(StrictSchema):
    version_key: str = Field(min_length=1)
    asset_key: str = Field(min_length=1)

    relation_type: DocumentAssetRelationType = "reference"
    required_when: str | None = None
    display_order: int = Field(default=0, ge=0)
```

Dùng class này khi cần validate quan hệ document version -> asset.

---

# 3. `chunks.py`

File:

```text
app/schemas/chunks.py
```

## Trách Nhiệm

`chunks.py` chỉ chứa schema và validator cho chunk.

## Import

```python
from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import ChunkType
```

## `Chunk`

Chunk dùng `parent_chunk_key` trong payload/RAG contract (DB dùng `parent_chunk_id`).
`chunk_type` là `parent` hoặc `child`.

```python
class Chunk(StrictSchema):
    document_key: str = Field(min_length=1)
    version_key: str = Field(min_length=1)

    chunk_key: str = Field(min_length=1)
    parent_chunk_key: str | None = None
    chunk_type: ChunkType

    content: str = Field(min_length=1)
    heading_path: list[str] = Field(default_factory=list)

    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    chunk_index: int = Field(ge=0)
    token_count: int | None = Field(default=None, ge=0)

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("heading_path")
    @classmethod
    def clean_heading_path(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @model_validator(mode="after")
    def validate_chunk_contract(self) -> "Chunk":
        if self.page_start is not None and self.page_end is not None:
            if self.page_start > self.page_end:
                raise ValueError("page_start must be <= page_end")

        if self.chunk_type == "parent" and self.parent_chunk_key is not None:
            raise ValueError("parent chunk must not have parent_chunk_key")

        if self.chunk_type == "child" and not self.parent_chunk_key:
            raise ValueError("child chunk requires parent_chunk_key")

        return self
```

---

# 4. `rag.py`

File:

```text
app/schemas/rag.py
```

## Trách Nhiệm

Sau khi đã tách module, `rag.py` chỉ nên là public import layer:

```python
from app.schemas.rag import DocumentMetadata, AssetMetadata, Chunk
```

## Nội Dung Đề Xuất

```python
from app.schemas.assets import AssetMetadata, DocumentAssetRelation
from app.schemas.chunks import Chunk
from app.schemas.documents import (
    DocumentBaseMetadata,
    DocumentMetadata,
    DocumentVersionMetadata,
    DocumentVersionStatus,
)

__all__ = [
    "AssetMetadata",
    "Chunk",
    "DocumentAssetRelation",
    "DocumentBaseMetadata",
    "DocumentMetadata",
    "DocumentVersionMetadata",
    "DocumentVersionStatus",
]
```

---

# 5. `__init__.py`

File:

```text
app/schemas/__init__.py
```

Có thể export các class ổn định:

```python
from app.schemas.assets import AssetMetadata, DocumentAssetRelation
from app.schemas.chunks import Chunk
from app.schemas.documents import (
    DocumentBaseMetadata,
    DocumentMetadata,
    DocumentVersionMetadata,
    DocumentVersionStatus,
)

__all__ = [
    "AssetMetadata",
    "Chunk",
    "DocumentAssetRelation",
    "DocumentBaseMetadata",
    "DocumentMetadata",
    "DocumentVersionMetadata",
    "DocumentVersionStatus",
]
```

Không export wildcard.

---

# 6. Field Không Nên Đưa Vào Các Schema Này

Không đưa các group sau vào `documents.py`, `assets.py`, `chunks.py`:

```text
database id auto-increment
created_at / updated_at audit fields
ingestion_jobs fields
processed_chunks / current_step / error_message
qdrant_point_id
index_status
extra_metadata
```

Những field trên nên nằm ở DB model, repository schema, hoặc ingestion job schema riêng.

Riêng `source_path` và `canonical_markdown_path` có thể nằm trong `DocumentVersionMetadata` vì chúng giúp audit nguồn file.

---

# 7. Common Mistakes Cần Tránh

- Sai: `is_lasted`. Đúng: `is_latest`.
- Sai: import `Priority`, `ChunkingStrategy`. Không dùng 2 type này.
- Sai: thêm `"not_required"` vào `OcrStatus`. Không dùng.
- Sai: thêm `collection_status` / `CollectionStatus`. Đã loại khỏi schema.
- Sai: thêm `validity_status` vào document/version/asset metadata. Field này đã bỏ khỏi DB.
- Sai: thêm relationship fields (`replaces`, `amends`...) vào YAML. Không dùng.
- Sai: đưa chunk validator vào `documents.py`. Để trong `chunks.py`.
- Sai: bắt buộc `is_latest = true` mỗi retrieve. `is_latest` chỉ là ranking preference.
- Sai: child chunk không có `parent_chunk_key`. Phải validate.
- Sai: parent chunk có `parent_chunk_key`. Phải validate.

---

# 8. Test Sau Khi Code

Chạy trong PowerShell tại:

```text
chatbot/backend
```

## Import từng module

```powershell
python -c "from app.schemas.documents import DocumentMetadata, DocumentVersionStatus; print('documents ok')"
python -c "from app.schemas.assets import AssetMetadata, DocumentAssetRelation; print('assets ok')"
python -c "from app.schemas.chunks import Chunk; print('chunks ok')"
```

## Import qua `rag.py`

```powershell
python -c "from app.schemas.rag import DocumentMetadata, AssetMetadata, Chunk; print('rag public import ok')"
```

## Test published hợp lệ

```powershell
@'
from app.schemas.documents import DocumentMetadata

doc = DocumentMetadata(
    document_key="doc-001",
    version_key="doc-001-v1",
    title="Quy trinh mau",
    document_type="quy_trinh",
    ocr_status="done",
    review_status="approved",
    rag_status="published",
)

print(doc.model_dump())
'@ | python -
```

## Test published bị chặn khi chưa approved

```powershell
@'
from pydantic import ValidationError
from app.schemas.documents import DocumentMetadata

try:
    DocumentMetadata(
        document_key="doc-old",
        version_key="doc-old-v1",
        document_type="quy_trinh",
        ocr_status="done",
        review_status="reviewing",
        rag_status="published",
    )
except ValidationError as exc:
    print(exc)
'@ | python -
```

## Test asset

```powershell
@'
from app.schemas.assets import AssetMetadata

asset = AssetMetadata(
    asset_key="form-cap-bang-diem",
    asset_type="form",
    title="Don xin cap bang diem",
)

print(asset.model_dump())
'@ | python -
```

## Test chunk

```powershell
@'
from app.schemas.chunks import Chunk

parent = Chunk(
    document_key="doc-001",
    version_key="doc-001-v1",
    chunk_key="p-001",
    chunk_type="parent",
    content="Noi dung parent",
    chunk_index=0,
)

child = Chunk(
    document_key="doc-001",
    version_key="doc-001-v1",
    chunk_key="c-001",
    parent_chunk_key="p-001",
    chunk_type="child",
    content="Noi dung child",
    chunk_index=1,
)

print(parent.chunk_key, child.parent_chunk_key)
'@ | python -
```

---

# 9. Kết Quả Mong Đợi

Sau khi implement xong:

```text
app/schemas/documents.py import duoc
app/schemas/assets.py import duoc
app/schemas/chunks.py import duoc
app/schemas/rag.py import duoc
published bi chan neu chua ocr_status=done va review_status=approved
published hop le khi done + approved
```
