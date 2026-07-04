# 01. Huong Dan Implement Schema RAG Theo Module

**Last Updated:** 2026-07-04

Source of truth cho field YAML metadata: `chatbot/.docs/spec/ctu-service/07_RAG_SPEC.md`.
Source of truth cho schema DB: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`.

File nay huong dan cach tach schema thay vi dua tat ca vao `app/schemas/rag.py`.

Huong tach da chot:

```text
documents.py = metadata tai lieu, version, status, publish rule
assets.py    = bieu mau/file/link lien quan
chunks.py    = noi dung da chia chunk
rag.py       = public import layer neu can import gom
```

## Muc Tieu

Schema trong `app/schemas` phuc vu 4 viec:

- validate YAML/frontmatter metadata truoc khi chunk/index;
- validate asset/form/link lien quan den tai lieu;
- validate parent/child chunk contract;
- export class de backend import gon.

Khong nhoi toan bo database schema vao mot file `rag.py`.

## Quyet Dinh Da Chot

1. Khong tao `Priority` enum.
2. Khong tao `ChunkingStrategy` enum.
3. Khong dung `ocr_status = "not_required"`.
4. File Markdown da parser/review van dung `ocr_status = "done"`.
5. `is_latest` chi la ranking preference, khong phai hard filter retrieval.
6. Status workflow (`ocr_status`, `review_status`, `rag_status`, `status_note`) nam truc tiep
   trong `document_versions`, khong co bang `document_version_status` rieng.
7. `validity_status` chi ap dung cho `assets`, khong dua vao version metadata.
8. Khong dua relationship fields (`replaces`, `amends`, `supplements`...) hoac `chunking_strategy`
   vao YAML metadata.
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

## Quy Uoc Key Va ID

Dung thong nhat:

```text
id           = khoa ky thuat noi bo database
document_key = ma on dinh cua tai lieu trong YAML/RAG
version_key  = ma on dinh cua version trong YAML/RAG
asset_key    = ma on dinh cua asset trong YAML/RAG
```

Trong schema metadata/chunk/asset relation, dung `document_key`, `version_key`, `asset_key`.

Khong dung `document_id`/`version_id` trong YAML/RAG schema neu da chon quy uoc `*_key`.

## File Can Tao/Sua

Trong:

```text
chatbot/backend/app/schemas/
```

nen co:

```text
enums.py
documents.py
assets.py
chunks.py
rag.py
__init__.py
```

Neu muon tranh lap `StrictSchema`, co the tao them `base.py`.

## Thu Tu Implement

1. Kiem tra `enums.py`.
2. Tao `base.py` neu dung base chung.
3. Tao `documents.py`.
4. Tao `assets.py`.
5. Tao `chunks.py`.
6. Doi `rag.py` thanh file re-export.
7. Cap nhat `__init__.py` neu can.
8. Chay import test.
9. Chay validation test.

## `enums.py` Can Co

Khong them `Priority`, `ChunkingStrategy`, hoac `"not_required"`.

Can co cac type (khop `05_DATABASE_SPEC.md` phan Status Enums):

```python
OcrStatus
ReviewStatus
RagStatus
IndexStatus
ValidityStatus      # chi dung cho assets
DocumentType
FileType
ChunkType
AssetType
DocumentAssetRelationType
Domain
```

Cac enum status khop spec 05:

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
ValidityStatus = Literal["valid", "invalid", "expired"]
```

Khong con `CollectionStatus`, `VersionRole`, `Confidentiality`, `CitationType`.

## Optional: `base.py`

File:

```text
app/schemas/base.py
```

Noi dung:

```python
from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

Ly do dung `extra="forbid"`:

- bat loi typo nhu `is_lasted` thay vi `is_latest`;
- tranh chunk/asset/status nhan field la;
- chi class tong hop `DocumentMetadata` moi cho phep metadata phu bang `extra="allow"`.

---

# 1. `documents.py`

File:

```text
app/schemas/documents.py
```

## Trach Nhiem

`documents.py` chua:

```text
DocumentBaseMetadata
DocumentVersionStatus
DocumentVersionMetadata
DocumentMetadata
```

Khong dua asset detail, chunk detail, ingestion job detail vao file nay.

## Import

```python
from __future__ import annotations

from datetime import date

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import (
    DocumentType,
    FileType,
    OcrStatus,
    RagStatus,
    ReviewStatus,
)
```

## `DocumentBaseMetadata`

Khop `documents` trong spec 05: chi `document_key`, `title`, `document_type`, `domain`,
`audience`. Khong co `department`, khong co `tags`.

```python
class DocumentBaseMetadata(StrictSchema):
    document_key: str = Field(min_length=1)
    title: str = ""
    document_type: DocumentType
    domain: str = ""
    audience: list[str] = Field(default_factory=list)

    @field_validator("audience")
    @classmethod
    def clean_string_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]
```

## `DocumentVersionStatus`

Chi giu status workflow nam truc tiep tren `document_versions`. Khong co `validity_status`,
khong co `collection_status`.

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

Khop optional fields trong spec 07 + cot `document_versions` spec 05. Khong co
`version_label`, `version_role`, `effective_date`, `expiry_date`, relationship arrays,
`confidentiality`, `citation_type`, `related_asset_keys`, `validity_status`.

```python
class DocumentVersionMetadata(DocumentVersionStatus):
    version_key: str = Field(min_length=1)
    title: str = ""

    code: str | None = None
    issued_date: date | None = None
    is_latest: bool = False

    source_url: str = ""
    source_path: str = ""
    canonical_markdown_path: str = ""
    file_type: FileType = "md"
    language: str = "vi"
    issuing_authority: str = ""
    signer: str = ""
    accessed_date: date | None = None

    checksum: str | None = None
```

Ghi nho:

```text
Dung is_latest, khong dung is_lasted.
source_path la path file goc.
canonical_markdown_path la path Markdown da clean/review.
Dung path tuong doi trong repo/vault, khong dung absolute Windows path.
```

## Validator Trong `DocumentVersionMetadata`

Validate publish/index rule (khong con validity_status/confidentiality):

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

Class tong hop de validate YAML/frontmatter:

```python
class DocumentMetadata(DocumentBaseMetadata, DocumentVersionMetadata):
    model_config = ConfigDict(extra="allow")
```

Ly do `extra="allow"`:

- YAML/frontmatter co the co field phu chua map vao schema;
- ingestion co the dua field phu vao DB `extra_metadata`;
- nhung schema con van strict de bat typo.

---

# 2. `assets.py`

File:

```text
app/schemas/assets.py
```

## Trach Nhiem

`assets.py` chua schema cho:

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
    ValidityStatus,
)
```

## `AssetMetadata`

Khop `assets` trong spec 05: `asset_key`, `title`, `asset_type`, `url`, `checksum`,
`validity_status`. Khong co `file_path`, `file_type`, `download_url`, `is_latest`,
`review_status`, `rag_status`.

```python
class AssetMetadata(StrictSchema):
    asset_key: str = Field(min_length=1)
    title: str = ""
    asset_type: AssetType
    url: str = ""
    checksum: str | None = None
    validity_status: ValidityStatus = "valid"
```

Khong can dua vao schema metadata giai doan dau:

```text
id
created_at
```

Nhung field do thuoc DB/API response.

## `DocumentAssetRelation`

Khop `document_assets` trong spec 05: `relation_type`, `required_when`, `display_order`.
Khong co cot `required` boolean.

```python
class DocumentAssetRelation(StrictSchema):
    version_key: str = Field(min_length=1)
    asset_key: str = Field(min_length=1)

    relation_type: DocumentAssetRelationType = "reference"
    required_when: str | None = None
    display_order: int = Field(default=0, ge=0)
```

Dung class nay khi can validate quan he document version -> asset.

---

# 3. `chunks.py`

File:

```text
app/schemas/chunks.py
```

## Trach Nhiem

`chunks.py` chi chua schema va validator cho chunk.

## Import

```python
from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import ChunkType
```

## `Chunk`

Chunk dung `parent_chunk_key` trong payload/RAG contract (DB dung `parent_chunk_id`).
`chunk_type` la `parent` hoac `child`.

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

## Trach Nhiem

Sau khi da tach module, `rag.py` chi nen la public import layer:

```python
from app.schemas.rag import DocumentMetadata, AssetMetadata, Chunk
```

## Noi Dung De Xuat

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

Co the export cac class on dinh:

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

Khong export wildcard.

---

# 6. Field Khong Nen Dua Vao Cac Schema Nay

Khong dua cac group sau vao `documents.py`, `assets.py`, `chunks.py`:

```text
database id auto-increment
created_at / updated_at audit fields
ingestion_jobs fields
processed_chunks / current_step / error_message
qdrant_point_id
index_status
extra_metadata
```

Nhung field tren nen nam o DB model, repository schema, hoac ingestion job schema rieng.

Rieng `source_path` va `canonical_markdown_path` co the nam trong `DocumentVersionMetadata` vi chung giup audit nguon file.

---

# 7. Common Mistakes Can Tranh

- Sai: `is_lasted`. Dung: `is_latest`.
- Sai: import `Priority`, `ChunkingStrategy`. Khong dung 2 type nay.
- Sai: them `"not_required"` vao `OcrStatus`. Khong dung.
- Sai: them `collection_status` / `CollectionStatus`. Da loai khoi schema.
- Sai: them `validity_status` vao version metadata. Chi `assets` co `validity_status`.
- Sai: them relationship fields (`replaces`, `amends`...) vao YAML. Khong dung.
- Sai: dua chunk validator vao `documents.py`. De trong `chunks.py`.
- Sai: bat buoc `is_latest = true` moi retrieve. `is_latest` chi la ranking preference.
- Sai: child chunk khong co `parent_chunk_key`. Phai validate.
- Sai: parent chunk co `parent_chunk_key`. Phai validate.

---

# 8. Test Sau Khi Code

Chay trong PowerShell tai:

```text
chatbot/backend
```

## Import tung module

```powershell
python -c "from app.schemas.documents import DocumentMetadata, DocumentVersionStatus; print('documents ok')"
python -c "from app.schemas.assets import AssetMetadata, DocumentAssetRelation; print('assets ok')"
python -c "from app.schemas.chunks import Chunk; print('chunks ok')"
```

## Import qua `rag.py`

```powershell
python -c "from app.schemas.rag import DocumentMetadata, AssetMetadata, Chunk; print('rag public import ok')"
```

## Test published hop le

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

## Test published bi chan khi chua approved

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
    validity_status="valid",
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

# 9. Ket Qua Mong Doi

Sau khi implement xong:

```text
app/schemas/documents.py import duoc
app/schemas/assets.py import duoc
app/schemas/chunks.py import duoc
app/schemas/rag.py import duoc
published bi chan neu chua ocr_status=done va review_status=approved
published hop le khi done + approved
```
