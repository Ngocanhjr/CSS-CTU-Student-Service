# 02. Hướng Dẫn Export Schema, Test `rag.py`, Và Metadata Validator

**Last Updated:** 2026-06-17

> **Legacy note (9-table contract):** Cac lenh import/export `DocumentVersionStatus` trong file nay
> da cu. Khong chay hoac copy cac snippet do; dung `DocumentVersionStatusFields` theo
> `03_SQLALCHEMY_9_TABLES_GUIDE.md`.

File này hướng dẫn 3 bước sau khi implement xong `app/schemas/rag.py`:

1. cập nhật `app/schemas/__init__.py`;
2. tạo test `tests/test_rag_schema.py`;
3. tạo `app/ingestion/metadata_validator.py`.

Không bắt đầu 3 bước này nếu `app/schemas/rag.py` chưa import được.

## Điều Kiện Trước Khi Làm

Chạy tại `chatbot/backend`:

```powershell
python -c "from app.schemas.rag import DocumentMetadata, DocumentVersionStatus, Chunk; print('rag schema ok')"
```

Nếu lệnh này lỗi, quay lại sửa `rag.py` trước.

## Bước 1: Cập Nhật `app/schemas/__init__.py`

Mục tiêu của `__init__.py` là cho phép import ngắn gọn:

```python
from app.schemas import DocumentMetadata, Chunk
```

Thay vì:

```python
from app.schemas.rag import DocumentMetadata, Chunk
```

### Nội Dung Đề Xuất

File:

```text
chatbot/backend/app/schemas/__init__.py
```

Nội dung:

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

### Nguyên Tắc

- Chỉ export schema đã ổn định.
- Không export bằng wildcard `from app.schemas.rag import *`.
- Không export enum từ `schemas/__init__.py` nếu chưa cần. Enum đã nằm trong `app.schemas.enums`.
- Nếu sau này thêm schema riêng như `assets.py`, `ingestion.py`, chỉ export class API cần dùng nhiều nơi.

### Test Sau Khi Sửa

```powershell
python -c "from app.schemas import DocumentMetadata, DocumentVersionStatus, Chunk; print('schema package export ok')"
```

## Bước 2: Tạo `tests/test_rag_schema.py`

Hiện tại nếu chưa có thư mục:

```text
chatbot/backend/tests
```

thì tạo thư mục này và thêm file:

```text
chatbot/backend/tests/test_rag_schema.py
```

### Mục Tiêu Test

Test nên cover các rule quan trọng:

- import schema thành công;
- metadata tối thiểu tạo được;
- published document bắt buộc `ocr_status = "done"`;
- published document bắt buộc `review_status = "approved"`;
- không chấp nhận `ocr_status = "not_required"`;
- parent chunk không có `parent_chunk_key`;
- child chunk phải có `parent_chunk_key`;
- `page_start <= page_end`.

### Nội Dung Đề Xuất

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

### Cách Chạy Test

Tại `chatbot/backend`:

```powershell
python -m pytest tests/test_rag_schema.py
```

Nếu chưa có pytest:

```powershell
pip install pytest
```

Nếu dự án không muốn thêm dependency ngay, có thể tạm chạy import/validation bằng các lệnh `python -c`, nhưng về lâu dài nên dùng pytest.

## Bước 3: Tạo `app/ingestion/metadata_validator.py`

Chỉ implement file này sau khi:

- `rag.py` import ok;
- `tests/test_rag_schema.py` pass.

File:

```text
chatbot/backend/app/ingestion/metadata_validator.py
```

### Trách Nhiệm

`metadata_validator.py` nên làm các việc:

- nhận dict metadata đã parse từ YAML/frontmatter;
- validate bằng `DocumentMetadata`;
- trả về object kết quả rõ ràng;
- không đọc file Markdown trực tiếp nếu chưa cần;
- không ghi database;
- không chunk/index;
- không sửa metadata ngầm.

### Không Nên Làm Trong File Này

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

Các việc đó thuộc service/pipeline khác.

### Nội Dung Đề Xuất

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

### Rule Publish Nằm Ở Đâu?

Rule publish nên nằm trong `DocumentMetadata`/`DocumentVersionMetadata` validator của `rag.py`.

`metadata_validator.py` chỉ gọi:

```python
DocumentMetadata.model_validate(raw_metadata)
```

Để tránh duplicate business rule.

### Test Cho Metadata Validator

Sau khi có file validator, tạo thêm:

```text
chatbot/backend/tests/test_metadata_validator.py
```

Nội dung tối thiểu:

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

Chạy:

```powershell
python -m pytest tests/test_metadata_validator.py
```

## Checklist Hoàn Thành

- [ ] `rag.py` import được.
- [ ] `app/schemas/__init__.py` export schema cần dùng.
- [ ] `from app.schemas import DocumentMetadata, Chunk` chạy được.
- [ ] `tests/test_rag_schema.py` tồn tại.
- [ ] `python -m pytest tests/test_rag_schema.py` pass.
- [ ] `metadata_validator.py` chỉ validate, không làm pipeline side effect.
- [ ] `tests/test_metadata_validator.py` pass.

## Thứ Tự Nên Commit/Làm Việc

Làm từng bước nhỏ:

1. commit/snapshot sau khi `rag.py` pass test;
2. sau đó cập nhật `schemas/__init__.py`;
3. sau đó thêm `test_rag_schema.py`;
4. sau đó thêm `metadata_validator.py`;
5. sau đó thêm `test_metadata_validator.py`.

Nếu test fail ở bước nào, sửa ngay bước đó trước khi sang bước tiếp theo.
