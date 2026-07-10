# 11. Part D - Hướng Dẫn Implement Chunk Preview

**Last Updated:** 2026-06-20

File này tách chi tiết từ guide 07, phần D.

Mục tiêu:

```text
Doc Markdown
validate metadata
chunk body
in preview de kiem tra truoc khi ghi DB
```

Preview giúp phát hiện lỗi chunking sớm: mất nội dung, heading sai, page sai, child thiếu parent.

---

## 1. File Cần Tạo

```text
chatbot/backend/app/ingestion/preview.py
chatbot/backend/test/ingestion/test_preview.py
```

Phụ thuộc vào:

```text
app.ingestion.markdown_reader
app.ingestion.chunking.chunker
```

Chunker hiện tại:

```text
Public API nam o app.ingestion.chunking.chunker.
Preview chi goi chunk_markdown_document(document), khong goi truc tiep parent_chunker/child_chunker.
Parent/child phan biet bang chunk.chunk_type.
Child lien ket parent bang parent_chunk_key stable key.
```

---

## 2. Output Contract

Preview nên trả về `dict` để dễ serialize JSON:

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
  "item_marker": "a)",
  "item_level": 3,
  "item_path": ["Khoan 1", "Diem a)"],
  "legal_unit_type": "point",
  "block_type": "lettered_item",
  "page_start": 1,
  "page_end": 1,
  "token_count": 120,
  "content_preview": "..."
}
```

Lưu ý:

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
    chunk_result = chunk_markdown_document(document)
    chunks = [*chunk_result.parent_chunks, *chunk_result.child_chunks]
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
        "warnings": [*warnings, *format_reports(chunk_result.warnings)],
        "errors": format_reports(chunk_result.errors),
        "chunks": [chunk_to_preview_item(chunk) for chunk in chunks],
    }
```

Validation reports từ structural parser phải hiện trong preview, không bị nuốt:

```python
def format_reports(reports: list[ValidationReport]) -> list[str]:
    return [
        f"Ambiguous page {report.page}: {report.reason}"
        for report in reports
    ]
```

---

## 4. Implement `chunk_to_preview_item`

```python
def chunk_to_preview_item(chunk: Chunk) -> dict[str, Any]:
    metadata = chunk.metadata or {}
    return {
        "chunk_key": chunk.chunk_key,
        "parent_chunk_key": chunk.parent_chunk_key,
        "chunk_type": chunk.chunk_type,
        "chunk_index": chunk.chunk_index,
        "heading_path": chunk.heading_path,
        "item_marker": metadata.get("item_marker"),
        "item_level": metadata.get("item_level"),
        "item_path": metadata.get("item_path", []),
        "legal_unit_type": metadata.get("legal_unit_type", "none"),
        "block_type": metadata.get("block_type"),
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

        if chunk.chunk_type == "child":
            metadata = chunk.metadata or {}
            block_type = metadata.get("block_type")
            if block_type in {"numbered_item", "lettered_item", "bullet_item"}:
                item_path = metadata.get("item_path", [])
                if not item_path:
                    warnings.append(f"Child {chunk.chunk_key} has empty item_path")

    return warnings
```

Lưu ý:

```text
Preview warning khong nhat thiet fail.
Pipeline ingest moi quyet dinh warning nao thanh error.
```

---

## 6. CLI Tạm Thời

Thêm vào cuối `preview.py`:

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

Chạy:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m app.ingestion.preview "..\..\nlcs\06_Processing\03_Markdown_Cleaning\PDFs_CTSV\Noi_quy_KTX_nam_2016_structured.md"
```

Nếu file Markdown chưa có metadata đúng schema, dùng test fixture trước.

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

## 8. Không Làm Trong Preview

Preview không:

```text
insert DB
embed
upsert Qdrant
update status
auto fix Markdown
```

Preview chỉ đọc, chunk và report.

---

## 9. Done Khi

- [ ] `build_chunk_preview(path)` trả dict serializable.
- [ ] Preview đếm đúng parent/child.
- [ ] Preview item có heading_path, page, token_count.
- [ ] Warning phát hiện child thiếu parent.
- [ ] CLI chạy được với file fixture.
- [ ] Test preview pass.

---

## 10. Lỗi Dễ Gặp

### Lỗi: preview dùng file thật bị ValidationError

Nguyên nhân:

```text
File Markdown that chua co metadata theo schema backend.
```

Xử lý:

```text
Test bang fixture truoc.
Sau do tao canonical Markdown metadata dung document_key/version_key.
```

### Lỗi: console không hiện tiếng Việt đúng

Nguyên nhân:

```text
PowerShell encoding.
```

Xử lý:

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8
```

### Lỗi: warnings quá nhiều empty heading_path

Nguyên nhân:

```text
Chunker chua tao default heading_path ["document-root"].
```

Xử lý:

```text
Sua chunker, khong sua preview.
```

## 12. Validation Severity Trong Preview

Preview phải hiển thị `severity`, `code`, `page`, `reason`, `selected_owner` và `candidate_owners` nếu có.
`warning` được hiển thị nhưng không tự động đánh dấu publish failed; `error` phải nổi bật và block publish theo default contract.
Không flatten warning/error thành chuỗi mất cấu trúc trong output máy đọc; formatter chuỗi chỉ dùng cho giao diện người đọc.
