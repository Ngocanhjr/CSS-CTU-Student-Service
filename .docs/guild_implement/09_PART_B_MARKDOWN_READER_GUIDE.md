# 09. Part B - Hướng Dẫn Implement Markdown Reader Và Metadata Validation

**Last Updated:** 2026-06-20

Guide này hướng dẫn riêng Markdown reader. Metadata contract đọc từ Guide 01; persistence contract
đọc từ Contract 10. Reader không sở hữu các contract đó.

Mục tiêu của part B:

```text
Doc mot file Markdown canonical
tach YAML frontmatter
validate bang DocumentMetadata
tra ve body Markdown sach cho chunker
```

Reader không chunk, không ghi DB, không embed.

---

## 1. File Cần Tạo

```text
chatbot/backend/app/ingestion/markdown_reader.py
chatbot/backend/test/ingestion/test_markdown_reader.py
```

Nếu thư mục test chưa có:

```text
chatbot/backend/test/ingestion/
```

thì tạo thêm.

---

## 2. Dependency

File:

```text
chatbot/backend/requirements.txt
```

Cần có:

```text
PyYAML>=6.0
```

Test:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -c "import yaml; print('yaml ok')"
```

---

## 3. Contract Output

Trong `markdown_reader.py`, tạo dataclass:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.documents import DocumentMetadata


@dataclass(frozen=True)
class MarkdownDocument:
    path: Path
    metadata: DocumentMetadata
    body: str
    raw_frontmatter: dict[str, Any]
```

Lý do giữ `raw_frontmatter`:

```text
debug metadata
sau nay tinh metadata_hash
kiem tra field phu neu DocumentMetadata extra allow
```

---

## 4. Hàm `read_markdown_document`

Suggested pattern:

```python
from pathlib import Path


def read_markdown_document(path: str | Path) -> MarkdownDocument:
    markdown_path = Path(path)
    text = markdown_path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    metadata = DocumentMetadata(**frontmatter)

    return MarkdownDocument(
        path=markdown_path,
        metadata=metadata,
        body=body,
        raw_frontmatter=frontmatter,
    )
```

Lưu ý:

```text
Dung encoding="utf-8".
Khong tu dong sua metadata trong reader.
Neu metadata sai, raise ValidationError de test/debug thay ngay.
```

---

## 5. Hàm `split_frontmatter`

Accepted format:

```markdown
---
document_key: "doc-key"
version_key: "doc-v1"
checksum: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
document_type: "quy_trinh"
responsible_department:
  - PDT
---

# Noi dung
```

Suggested pattern:

```python
from typing import Any

import yaml


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")

    if not normalized.startswith("---\n"):
        raise ValueError("Markdown file must start with YAML frontmatter")

    closing_marker = "\n---\n"
    closing_index = normalized.find(closing_marker, len("---\n"))
    if closing_index == -1:
        raise ValueError("Markdown file has no closing YAML frontmatter marker")

    yaml_text = normalized[len("---\n"):closing_index]
    body = normalized[closing_index + len(closing_marker):]

    frontmatter = yaml.safe_load(yaml_text) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    if not body.strip():
        raise ValueError("Markdown body is empty")

    return frontmatter, body.strip()
```

Vì sao không dùng `text.split("---\n", 2)`:

```text
Body co the chua dong --- trong noi dung hoac code fence.
Tim closing marker sau dong dau an toan hon cho MVP.
```

---

## 6. Metadata Tối Thiểu Để Test

Test fixture nên có đầy đủ field bắt buộc theo schema hiện tại:

```python
VALID_MARKDOWN = """---
document_key: "test-doc"
version_key: "test-doc-v1"
title: "Test Document"
document_type: "quy_trinh"
domain: "test"
audience:
  - "sinh_vien"
responsible_department:
  - PDT
is_latest: true
source_path: "test.md"
canonical_markdown_path: "test.md"
file_type: "md"
language: "vi"
issuing_authority: "Trường Đại học Cần Thơ"
signer_name: "Nguyen Van A"
checksum: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
ocr_status: "done"
review_status: "approved"
rag_status: "published"
---

# Test Document

Noi dung test.
"""
```

Nếu `rag_status: "published"` thì schema bắt buộc:

```text
ocr_status = done
review_status = approved
```

Metadata rules theo schema hiện tại:

```text
responsible_department luôn là list: [], [PDT], hoặc dạng nhiều dòng.
checksum bắt buộc, dùng SHA-256 hex 64 ký tự.
Không dùng version_label.
Không dùng validity_status.
Không dùng signer, dùng signer_name.
```

Nếu tài liệu chỉ ghi hiệu lực dạng kỳ/năm như `Học kỳ 2, năm học 2024-2025`, reader chỉ giữ trong metadata/extra field nếu YAML có. Không convert thành DB date, vì `document_versions` không có cột `effective_date`.

---

## 7. Test File

File:

```text
chatbot/backend/test/ingestion/test_markdown_reader.py
```

Suggested tests:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.markdown_reader import read_markdown_document, split_frontmatter


def test_split_frontmatter_valid():
    frontmatter, body = split_frontmatter(VALID_MARKDOWN)

    assert frontmatter["document_key"] == "test-doc"
    assert "# Test Document" in body


def test_read_markdown_document_valid(tmp_path: Path):
    path = tmp_path / "test.md"
    path.write_text(VALID_MARKDOWN, encoding="utf-8")

    document = read_markdown_document(path)

    assert document.metadata.document_key == "test-doc"
    assert document.metadata.version_key == "test-doc-v1"
    assert document.body.startswith("# Test Document")


def test_reader_rejects_missing_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        split_frontmatter("# No YAML")


def test_reader_rejects_empty_body():
    text = """---
document_key: "x"
---
"""

    with pytest.raises(ValueError, match="empty"):
        split_frontmatter(text)


def test_reader_rejects_invalid_publish_status(tmp_path: Path):
    invalid = VALID_MARKDOWN.replace('ocr_status: "done"', 'ocr_status: "not_started"')
    path = tmp_path / "invalid.md"
    path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValidationError):
        read_markdown_document(path)
```

---

## 8. Lưu Ý Về File Path

Reader không nên convert relative path thành absolute trong metadata.

Lý do:

```text
canonical_markdown_path trong YAML nen la path portable trong repo/vault.
Path object cua MarkdownDocument dung cho runtime doc file.
```

Nếu cần absolute path cho logging:

```python
markdown_path.resolve()
```

nhưng không ghi ngược vào metadata.

---

## 9. Không Làm Trong Reader

Không làm các việc này trong `markdown_reader.py`:

```text
khong tinh chunk
khong sua heading
khong update rag_status
khong insert database
khong goi embedding
khong goi Qdrant
```

Reader chỉ đọc và validate.

---

## 10. Lệnh Test

Chạy:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_markdown_reader.py
```

Nếu import `app` lỗi, kiểm tra:

```text
chatbot/backend/pytest.ini
```

cần có:

```ini
[pytest]
pythonpath = .
testpaths = test
```

---

## 11. Done Khi

- [x] `markdown_reader.py` có `MarkdownDocument`.

- [x] `split_frontmatter` xử lý LF và CRLF.

- [x] `read_markdown_document` validate bằng `DocumentMetadata`.

- [x] File thiếu frontmatter bị reject.

- [x] File body rỗng bị reject.

- [x] Published metadata sai status bị reject.

- [x] Test `test_markdown_reader.py` pass.

---

## 12. Lỗi Dễ Gặp

### Lỗi: `ModuleNotFoundError: No module named 'yaml'`

Xử lý:

```powershell
..\..\.venv\Scripts\python.exe -m pip install PyYAML
```

Và thêm `PyYAML>=6.0` vào requirements.

### Lỗi: YAML parse ra string/list

Nguyên nhân:

```text
Frontmatter khong phai mapping key-value.
```

Xử lý:

```text
Raise ValueError "YAML frontmatter must be a mapping".
```

### Lỗi: `document_key field required`

Nguyên nhân:

```text
File Markdown dang dung metadata cu document_id/version_id.
```

Xử lý:

```text
Sua file Markdown sang document_key/version_key hoac viet migration metadata rieng.
Khong nen them alias ngam trong reader MVP.
```
