# 11. Part D - Huong Dan Implement Chunk Preview

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan D.

Muc tieu:

```text
Doc Markdown
validate metadata
chunk body
in preview de kiem tra truoc khi ghi DB
```

Preview giup phat hien loi chunking som: mat noi dung, heading sai, page sai, child thieu parent.

---

## 1. File Can Tao

```text
chatbot/backend/app/ingestion/preview.py
chatbot/backend/test/ingestion/test_preview.py
```

Phu thuoc vao:

```text
app.ingestion.markdown_reader
app.ingestion.chunking.chunker
```

Chunker hien tai:

```text
Public API nam o app.ingestion.chunking.chunker.
Preview chi goi chunk_markdown_document(document), khong goi truc tiep parent_chunker/child_chunker.
Parent/child phan biet bang chunk.chunk_type.
Child lien ket parent bang parent_chunk_key stable key.
```

---

## 2. Output Contract

Preview nen tra ve `dict` de de serialize JSON:

```json
{
  "document_key": "doc",
  "version_key": "doc-v1",
  "title": "Title",
  "total_chunks": 3,
  "parent_chunks": 1,
  "child_chunks": 2,
  "warnings": [],
  "chunks": []
}
```

Chunk preview item:

```json
{
  "chunk_key": "doc-v1::c::0001",
  "parent_chunk_key": "doc-v1::p::0001",
  "chunk_type": "child",
  "chunk_index": 1,
  "heading_path": ["Title", "Dieu 1"],
  "page_start": 1,
  "page_end": 1,
  "token_count": 120,
  "content_preview": "..."
}
```

Luu y:

```text
chunk_key trong preview la stable key se duoc luu vao DocumentChunk.chunk_key.
```

---

## 3. Implement `build_chunk_preview`

File:

```text
chatbot/backend/app/ingestion/preview.py
```

Suggested pattern:

```python
from pathlib import Path
from typing import Any

from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.schemas.chunks import Chunk


def build_chunk_preview(path: str | Path) -> dict[str, Any]:
    document = read_markdown_document(path)
    chunks = chunk_markdown_document(document)
    warnings = validate_preview_chunks(chunks)

    parent_count = sum(1 for chunk in chunks if chunk.chunk_type == "parent")
    child_count = sum(1 for chunk in chunks if chunk.chunk_type == "child")

    return {
        "document_key": document.metadata.document_key,
        "version_key": document.metadata.version_key,
        "title": document.metadata.title,
        "total_chunks": len(chunks),
        "parent_chunks": parent_count,
        "child_chunks": child_count,
        "warnings": warnings,
        "chunks": [chunk_to_preview_item(chunk) for chunk in chunks],
    }
```

---

## 4. Implement `chunk_to_preview_item`

```python
def chunk_to_preview_item(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_key": chunk.chunk_key,
        "parent_chunk_key": chunk.parent_chunk_key,
        "chunk_type": chunk.chunk_type,
        "chunk_index": chunk.chunk_index,
        "heading_path": chunk.heading_path,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "token_count": chunk.token_count,
        "content_preview": make_content_preview(chunk.content),
    }
```

Preview content:

```python
def make_content_preview(content: str, limit: int = 240) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
```

---

## 5. Validate Preview

```python
def validate_preview_chunks(chunks: list[Chunk]) -> list[str]:
    warnings: list[str] = []
    parent_keys = {chunk.chunk_key for chunk in chunks if chunk.chunk_type == "parent"}

    if not chunks:
        warnings.append("No chunks were generated")

    for chunk in chunks:
        if not chunk.content.strip():
            warnings.append(f"Chunk {chunk.chunk_key} has empty content")

        if chunk.chunk_type == "child" and chunk.parent_chunk_key not in parent_keys:
            warnings.append(f"Child {chunk.chunk_key} has missing parent {chunk.parent_chunk_key}")

        if chunk.page_start and chunk.page_end and chunk.page_start > chunk.page_end:
            warnings.append(f"Chunk {chunk.chunk_key} has invalid page range")

        if not chunk.heading_path:
            warnings.append(f"Chunk {chunk.chunk_key} has empty heading_path")

    return warnings
```

Luu y:

```text
Preview warning khong nhat thiet fail.
Pipeline ingest moi quyet dinh warning nao thanh error.
```

---

## 6. CLI Tam Thoi

Them vao cuoi `preview.py`:

```python
def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()

    preview = build_chunk_preview(args.path)
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

Chay:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m app.ingestion.preview "..\..\nlcs\06_Processing\03_Markdown_Cleaning\PDFs_CTSV\Noi_quy_KTX_nam_2016_structured.md"
```

Neu file Markdown chua co metadata dung schema, dung test fixture truoc.

---

## 7. Test Preview

File:

```text
chatbot/backend/test/ingestion/test_preview.py
```

Suggested pattern:

```python
from pathlib import Path

from app.ingestion.preview import build_chunk_preview


def test_build_chunk_preview(tmp_path: Path):
    path = tmp_path / "test.md"
    path.write_text(VALID_MARKDOWN, encoding="utf-8")

    preview = build_chunk_preview(path)

    assert preview["document_key"] == "test-doc"
    assert preview["total_chunks"] > 0
    assert preview["parent_chunks"] > 0
    assert preview["child_chunks"] > 0
    assert preview["chunks"][0]["content_preview"]
```

Test warning:

```python
from app.ingestion.preview import validate_preview_chunks
from app.schemas.chunks import Chunk


def test_preview_warns_for_missing_parent():
    child = Chunk(
        document_key="doc",
        version_key="doc-v1",
        chunk_key="doc-v1::c::0001",
        parent_chunk_key="missing",
        chunk_type="child",
        content="content",
        chunk_index=0,
    )

    warnings = validate_preview_chunks([child])

    assert any("missing parent" in warning for warning in warnings)
```

---

## 8. Khong Lam Trong Preview

Preview khong:

```text
insert DB
embed
upsert Qdrant
update status
auto fix Markdown
```

Preview chi doc, chunk va report.

---

## 9. Done Khi

- [ ] `build_chunk_preview(path)` tra dict serializable.
- [ ] Preview dem dung parent/child.
- [ ] Preview item co heading_path, page, token_count.
- [ ] Warning phat hien child thieu parent.
- [ ] CLI chay duoc voi file fixture.
- [ ] Test preview pass.

---

## 10. Loi De Gap

### Loi: preview dung file that bi ValidationError

Nguyen nhan:

```text
File Markdown that chua co metadata theo schema backend.
```

Xu ly:

```text
Test bang fixture truoc.
Sau do tao canonical Markdown metadata dung document_key/version_key.
```

### Loi: console khong hien tieng Viet dung

Nguyen nhan:

```text
PowerShell encoding.
```

Xu ly:

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8
```

### Loi: warnings qua nhieu empty heading_path

Nguyen nhan:

```text
Chunker chua tao default heading_path ["Document"].
```

Xu ly:

```text
Sua chunker, khong sua preview.
```
