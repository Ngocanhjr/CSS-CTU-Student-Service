# 09. Part B - Huong Dan Implement Markdown Reader Va Metadata Validation

**Last Updated:** 2026-06-20

File nay tach chi tiet tu `07_DETAILED_RAG_INGESTION_IMPLEMENTATION_GUIDE.md`, phan B.

Muc tieu cua part B:

```text
Doc mot file Markdown canonical
tach YAML frontmatter
validate bang DocumentMetadata
tra ve body Markdown sach cho chunker
```

Reader khong chunk, khong ghi DB, khong embed.

---

## 1. File Can Tao

```text
chatbot/backend/app/ingestion/markdown_reader.py
chatbot/backend/test/ingestion/test_markdown_reader.py
```

Neu thu muc test chua co:

```text
chatbot/backend/test/ingestion/
```

thi tao them.

---

## 2. Dependency

File:

```text
chatbot/backend/requirements.txt
```

Can co:

```text
PyYAML>=6.0
```

Test:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -c "import yaml; print('yaml ok')"
```

---

## 3. Contract Output

Trong `markdown_reader.py`, tao dataclass:

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

Ly do giu `raw_frontmatter`:

```text
debug metadata
sau nay tinh metadata_hash
kiem tra field phu neu DocumentMetadata extra allow
```

---

## 4. Ham `read_markdown_document`

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

Luu y:

```text
Dung encoding="utf-8".
Khong tu dong sua metadata trong reader.
Neu metadata sai, raise ValidationError de test/debug thay ngay.
```

---

## 5. Ham `split_frontmatter`

Accepted format:

```markdown
---
document_key: "doc-key"
version_key: "doc-v1"
checksum: "abc"
document_type: "quy_trinh"
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

Vi sao khong dung `text.split("---\n", 2)`:

```text
Body co the chua dong --- trong noi dung hoac code fence.
Tim closing marker sau dong dau an toan hon cho MVP.
```

---

## 6. Metadata Toi Thieu De Test

Test fixture nen co day du field bat buoc theo schema hien tai:

```python
VALID_MARKDOWN = """---
document_key: "test-doc"
version_key: "test-doc-v1"
title: "Test Document"
document_type: "quy_trinh"
domain: "test"
audience:
  - "student"
is_latest: true
source_path: "test.md"
canonical_markdown_path: "test.md"
file_type: "md"
language: "vi"
issuing_authority: "PDT"
checksum: "test-checksum"
ocr_status: "done"
review_status: "approved"
rag_status: "published"
---

# Test Document

Noi dung test.
"""
```

Neu `rag_status: "published"` thi schema bat buoc:

```text
ocr_status = done
review_status = approved
```

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

## 8. Luu Y Ve File Path

Reader khong nen convert relative path thanh absolute trong metadata.

Ly do:

```text
canonical_markdown_path trong YAML nen la path portable trong repo/vault.
Path object cua MarkdownDocument dung cho runtime doc file.
```

Neu can absolute path cho logging:

```python
markdown_path.resolve()
```

nhung khong ghi nguoc vao metadata.

---

## 9. Khong Lam Trong Reader

Khong lam cac viec nay trong `markdown_reader.py`:

```text
khong tinh chunk
khong sua heading
khong update rag_status
khong insert database
khong goi embedding
khong goi Qdrant
```

Reader chi doc va validate.

---

## 10. Lenh Test

Chay:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_markdown_reader.py
```

Neu import `app` loi, kiem tra:

```text
chatbot/backend/pytest.ini
```

can co:

```ini
[pytest]
pythonpath = .
testpaths = test
```

---

## 11. Done Khi

- [ ] `markdown_reader.py` co `MarkdownDocument`.
- [ ] `split_frontmatter` xu ly LF va CRLF.
- [ ] `read_markdown_document` validate bang `DocumentMetadata`.
- [ ] File thieu frontmatter bi reject.
- [ ] File body rong bi reject.
- [ ] Published metadata sai status bi reject.
- [ ] Test `test_markdown_reader.py` pass.

---

## 12. Loi De Gap

### Loi: `ModuleNotFoundError: No module named 'yaml'`

Xu ly:

```powershell
..\..\.venv\Scripts\python.exe -m pip install PyYAML
```

Va them `PyYAML>=6.0` vao requirements.

### Loi: YAML parse ra string/list

Nguyen nhan:

```text
Frontmatter khong phai mapping key-value.
```

Xu ly:

```text
Raise ValueError "YAML frontmatter must be a mapping".
```

### Loi: `document_key field required`

Nguyen nhan:

```text
File Markdown dang dung metadata cu document_id/version_id.
```

Xu ly:

```text
Sua file Markdown sang document_key/version_key hoac viet migration metadata rieng.
Khong nen them alias ngam trong reader MVP.
```
