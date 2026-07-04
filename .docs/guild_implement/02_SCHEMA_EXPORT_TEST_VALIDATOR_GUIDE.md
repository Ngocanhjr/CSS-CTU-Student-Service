# 02. Huong Dan Export Schema, Test `rag.py`, Va Metadata Validator

**Last Updated:** 2026-06-17

File nay huong dan 3 buoc sau khi implement xong `app/schemas/rag.py`:

1. cap nhat `app/schemas/__init__.py`;
2. tao test `tests/test_rag_schema.py`;
3. tao `app/ingestion/metadata_validator.py`.

Khong bat dau 3 buoc nay neu `app/schemas/rag.py` chua import duoc.

## Dieu Kien Truoc Khi Lam

Chay tai `chatbot/backend`:

```powershell
python -c "from app.schemas.rag import DocumentMetadata, DocumentVersionStatus, Chunk; print('rag schema ok')"
```

Neu lenh nay loi, quay lai sua `rag.py` truoc.

## Buoc 1: Cap Nhat `app/schemas/__init__.py`

Muc tieu cua `__init__.py` la cho phep import ngan gon:

```python
from app.schemas import DocumentMetadata, Chunk
```

Thay vi:

```python
from app.schemas.rag import DocumentMetadata, Chunk
```

### Noi Dung De Xuat

File:

```text
chatbot/backend/app/schemas/__init__.py
```

Noi dung:

```python
from app.schemas.rag import (
    Chunk,
    DocumentBaseMetadata,
    DocumentMetadata,
    DocumentVersionMetadata,
    DocumentVersionStatus,
)

__all__ = [
    "Chunk",
    "DocumentBaseMetadata",
    "DocumentMetadata",
    "DocumentVersionMetadata",
    "DocumentVersionStatus",
]
```

### Nguyen Tac

- Chi export schema da on dinh.
- Khong export bang wildcard `from app.schemas.rag import *`.
- Khong export enum tu `schemas/__init__.py` neu chua can. Enum da nam trong `app.schemas.enums`.
- Neu sau nay them schema rieng nhu `assets.py`, `ingestion.py`, chi export class API can dung nhieu noi.

### Test Sau Khi Sua

```powershell
python -c "from app.schemas import DocumentMetadata, DocumentVersionStatus, Chunk; print('schema package export ok')"
```

## Buoc 2: Tao `tests/test_rag_schema.py`

Hien tai neu chua co thu muc:

```text
chatbot/backend/tests
```

thi tao thu muc nay va them file:

```text
chatbot/backend/tests/test_rag_schema.py
```

### Muc Tieu Test

Test nen cover cac rule quan trong:

- import schema thanh cong;
- metadata toi thieu tao duoc;
- published document bat buoc `ocr_status = "done"`;
- published document bat buoc `review_status = "approved"`;
- khong chap nhan `ocr_status = "not_required"`;
- parent chunk khong co `parent_chunk_key`;
- child chunk phai co `parent_chunk_key`;
- `page_start <= page_end`.

### Noi Dung De Xuat

```python
import pytest
from pydantic import ValidationError

from app.schemas.rag import Chunk, DocumentMetadata


def valid_published_metadata(**overrides):
    data = {
        "document_key": "doc-001",
        "version_key": "doc-001-v1",
        "title": "Quy trinh mau",
        "document_type": "quy_trinh",
        "ocr_status": "done",
        "review_status": "approved",
        "rag_status": "published",
    }
    data.update(overrides)
    return data


def test_document_metadata_minimal_valid():
    doc = DocumentMetadata(
        document_key="doc-001",
        version_key="doc-001-v1",
        document_type="quy_trinh",
    )

    assert doc.document_key == "doc-001"
    assert doc.version_key == "doc-001-v1"
    assert doc.rag_status == "not_indexed"


def test_published_metadata_valid():
    doc = DocumentMetadata(**valid_published_metadata())

    assert doc.rag_status == "published"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ocr_status", "not_started"),
        ("review_status", "not_reviewed"),
    ],
)
def test_published_metadata_rejects_invalid_publish_requirements(field, value):
    data = valid_published_metadata(**{field: value})

    with pytest.raises(ValidationError):
        DocumentMetadata(**data)


def test_ocr_status_not_required_is_not_allowed():
    data = valid_published_metadata(ocr_status="not_required")

    with pytest.raises(ValidationError):
        DocumentMetadata(**data)


def test_parent_chunk_must_not_have_parent_chunk_key():
    with pytest.raises(ValidationError):
        Chunk(
            document_key="doc-001",
            version_key="doc-001-v1",
            chunk_key="p-001",
            parent_chunk_key="x",
            chunk_type="parent",
            content="Parent content",
            chunk_index=0,
        )


def test_child_chunk_requires_parent_chunk_key():
    with pytest.raises(ValidationError):
        Chunk(
            document_key="doc-001",
            version_key="doc-001-v1",
            chunk_key="c-001",
            chunk_type="child",
            content="Child content",
            chunk_index=1,
        )


def test_chunk_page_range_order():
    with pytest.raises(ValidationError):
        Chunk(
            document_key="doc-001",
            version_key="doc-001-v1",
            chunk_key="c-001",
            parent_chunk_key="p-001",
            chunk_type="child",
            content="Child content",
            chunk_index=1,
            page_start=3,
            page_end=2,
        )
```

### Cach Chay Test

Tai `chatbot/backend`:

```powershell
python -m pytest tests/test_rag_schema.py
```

Neu chua co pytest:

```powershell
pip install pytest
```

Neu du an khong muon them dependency ngay, co the tam chay import/validation bang cac lenh `python -c`, nhung ve lau dai nen dung pytest.

## Buoc 3: Tao `app/ingestion/metadata_validator.py`

Chi implement file nay sau khi:

- `rag.py` import ok;
- `tests/test_rag_schema.py` pass.

File:

```text
chatbot/backend/app/ingestion/metadata_validator.py
```

### Trach Nhiem

`metadata_validator.py` nen lam cac viec:

- nhan dict metadata da parse tu YAML/frontmatter;
- validate bang `DocumentMetadata`;
- tra ve object ket qua ro rang;
- khong doc file Markdown truc tiep neu chua can;
- khong ghi database;
- khong chunk/index;
- khong sua metadata ngam.

### Khong Nen Lam Trong File Nay

```text
OCR
Markdown cleaning
Chunking
Embedding
Qdrant upsert
Database write
Asset validation
Ingestion job transition
```

Cac viec do thuoc service/pipeline khac.

### Noi Dung De Xuat

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.schemas.rag import DocumentMetadata


@dataclass(frozen=True)
class MetadataValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class MetadataValidationResult:
    valid: bool
    metadata: DocumentMetadata | None = None
    errors: list[MetadataValidationIssue] = field(default_factory=list)


def validate_document_metadata(raw_metadata: dict[str, Any]) -> MetadataValidationResult:
    try:
        metadata = DocumentMetadata.model_validate(raw_metadata)
    except ValidationError as exc:
        return MetadataValidationResult(
            valid=False,
            errors=[
                MetadataValidationIssue(
                    field=".".join(str(part) for part in error["loc"]),
                    message=str(error["msg"]),
                )
                for error in exc.errors()
            ],
        )

    return MetadataValidationResult(valid=True, metadata=metadata)
```

### Rule Publish Nam O Dau?

Rule publish nen nam trong `DocumentMetadata`/`DocumentVersionMetadata` validator cua `rag.py`.

`metadata_validator.py` chi goi:

```python
DocumentMetadata.model_validate(raw_metadata)
```

De tranh duplicate business rule.

### Test Cho Metadata Validator

Sau khi co file validator, tao them:

```text
chatbot/backend/tests/test_metadata_validator.py
```

Noi dung toi thieu:

```python
from app.ingestion.metadata_validator import validate_document_metadata


def test_validate_document_metadata_success():
    result = validate_document_metadata(
        {
            "document_key": "doc-001",
            "version_key": "doc-001-v1",
            "document_type": "quy_trinh",
        }
    )

    assert result.valid is True
    assert result.metadata is not None
    assert result.errors == []


def test_validate_document_metadata_failure():
    result = validate_document_metadata({})

    assert result.valid is False
    assert result.metadata is None
    assert result.errors
```

Chay:

```powershell
python -m pytest tests/test_metadata_validator.py
```

## Checklist Hoan Thanh

- [ ] `rag.py` import duoc.
- [ ] `app/schemas/__init__.py` export schema can dung.
- [ ] `from app.schemas import DocumentMetadata, Chunk` chay duoc.
- [ ] `tests/test_rag_schema.py` ton tai.
- [ ] `python -m pytest tests/test_rag_schema.py` pass.
- [ ] `metadata_validator.py` chi validate, khong lam pipeline side effect.
- [ ] `tests/test_metadata_validator.py` pass.

## Thu Tu Nen Commit/Lam Viec

Lam tung buoc nho:

1. commit/snapshot sau khi `rag.py` pass test;
2. sau do cap nhat `schemas/__init__.py`;
3. sau do them `test_rag_schema.py`;
4. sau do them `metadata_validator.py`;
5. sau do them `test_metadata_validator.py`.

Neu test fail o buoc nao, sua ngay buoc do truoc khi sang buoc tiep theo.
