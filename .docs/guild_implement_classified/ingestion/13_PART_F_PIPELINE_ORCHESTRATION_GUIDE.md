# 13. Part F - Hướng Dẫn Implement Ingestion Pipeline Orchestration

**Last Updated:** 2026-06-20

File này tách chi tiết từ guide 07, phần F.

Mục tiêu:

```text
Dieu phoi reader -> chunker -> repository -> embedding -> qdrant
```

Pipeline không nên chứa logic chi tiết của từng phần. Nó chỉ gọi các module đã tách.

---

## 1. File Cần Sửa

```text
chatbot/backend/app/ingestion/pipeline.py
chatbot/backend/test/ingestion/test_pipeline.py
```

Pipeline phụ thuộc vào:

```text
app.ingestion.markdown_reader
app.ingestion.chunking.chunker
app.ingestion.repository
app.embedding.embedder
app.vectorstore.repository
app.databases.session
```

Chunker hiện tại đã tách module:

```text
chunking/chunker.py chi orchestration chunk.
chunking/parent_chunker.py build ParentSection va parent Chunk.
chunking/child_chunker.py đọc ParentSection.blocks để tạo child Chunks.
Pipeline chi goi chunk_markdown_document(document).
```

Lưu ý quan trọng:

```text
StructuralParser chi chay mot lan trong chunk_markdown_body().
Pipeline khong parse lai Markdown body.
Child builder khong parse lai parent_chunk.content; no dung ParentSection.blocks da parse san.
```

---

## 2. Mode Chạy

Pipeline nên có 2 mode:

```text
publish=False
  doc markdown
  validate metadata
  chunk
  save PostgreSQL
  stop

publish=True
  lam tat ca buoc publish=False
  embed child chunks
  upsert Qdrant
  update status final
```

Làm `publish=False` trước để test DB/chunking không cần model embedding/Qdrant.

---

## 3. Dataclass Result

File:

```text
chatbot/backend/app/ingestion/pipeline.py
```

Suggested pattern:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionResult:
    document_key: str
    version_key: str
    document_version_id: int
    total_chunks: int
    parent_chunks: int
    child_chunks: int
    embedded_chunks: int = 0
    indexed_chunks: int = 0
```

---

## 4. Helper Đếm Chunk

```python
from app.schemas.chunks import Chunk


def count_chunks(chunks: list[Chunk]) -> tuple[int, int]:
    parent_count = sum(1 for chunk in chunks if chunk.chunk_type == "parent")
    child_count = sum(1 for chunk in chunks if chunk.chunk_type == "child")
    return parent_count, child_count
```

---

## 5. Implement `ingest_markdown_file`

MVP public API:

```python
from pathlib import Path

from app.databases.session import AsyncSessionLocal
from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.ingestion.repository import save_document_with_chunks


async def ingest_markdown_file(path: str | Path, *, publish: bool = False) -> IngestionResult:
    document = read_markdown_document(path)
    chunk_result = chunk_markdown_document(document)
    chunks = [*chunk_result.parent_chunks, *chunk_result.child_chunks]
    parent_count, child_count = count_chunks(chunks)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            saved = await save_document_with_chunks(
                session,
                metadata=document.metadata,
                chunks=chunks,
            )

    result = IngestionResult(
        document_key=document.metadata.document_key,
        version_key=document.metadata.version_key,
        document_version_id=saved.document_version_id,
        total_chunks=len(chunks),
        parent_chunks=parent_count,
        child_chunks=child_count,
    )

    if not publish:
        return result

    blocking_reports = [
        report
        for report in chunk_result.errors
    ]
    if blocking_reports:
        raise ValueError("Cannot publish document with structural parsing errors")

    # Warnings remain available for preview/log/review but do not block publish
    # by default. A separate strict mode may promote warnings to blocking.

    return await publish_saved_document(
        result,
        document=document,
        chunks=chunks,
    )
```

`publish_saved_document` sẽ làm trong guide 14-15 sau khi có embedder và qdrant repository.
Khi publish, dùng `chunks` còn trong memory để giữ `Chunk.metadata` như `item_path`,
`legal_unit_type`, `block_type`. Không load lại từ DB row nếu schema DB chưa có JSON metadata
cho `document_chunks`.

---

## 6. Publish Guard

Trước khi embed/upsert, cần check:

```python
def ensure_publish_allowed(metadata) -> None:
    if metadata.ocr_status != "done":
        raise ValueError("Cannot publish document with ocr_status != done")
    if metadata.review_status != "approved":
        raise ValueError("Cannot publish document with review_status != approved")
    if metadata.rag_status != "published":
        raise ValueError("Metadata rag_status must be published for student publish")
```

Index eligibility theo spec: `ocr_status = done AND review_status = approved`. Student filter:
`review_status = approved AND rag_status = published`. Không dùng `validity_status` trong DB.

MVP chỉ cần student publish.

---

## 7. Error Handling

Khi pipeline lỗi, cần ghi ingestion job nếu đã có document_version.

MVP đơn giản:

```text
Neu loi truoc khi save DB: raise.
Neu loi sau khi save DB: update status failed.
```

Suggested helper:

```python
from app.databases.models import DocumentVersion


async def mark_ingestion_failed(document_version_id: int, stage: str, error: Exception) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            version = await session.get(DocumentVersion, document_version_id)
            if version:
                version.rag_status = "failed"
                version.status_note = f"{stage}: {error}"
```

Lưu ý:

```text
Khong swallow exception. Mark failed xong van raise.
```

---

## 8. CLI Tạm Thời

Thêm vào `pipeline.py`:

```python
def main() -> None:
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(ingest_markdown_file(args.path, publish=args.publish))
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

Run:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m app.ingestion.pipeline path\to\sample.md
```

---

## 9. Test Pipeline `publish=False`

File:

```text
chatbot/backend/test/ingestion/test_pipeline.py
```

Test:

```python
async def test_ingest_markdown_file_without_publish(tmp_path):
    path = tmp_path / "test.md"
    path.write_text(VALID_MARKDOWN, encoding="utf-8")

    result = await ingest_markdown_file(path, publish=False)

    assert result.document_key == "test-doc"
    assert result.document_version_id > 0
    assert result.parent_chunks > 0
    assert result.child_chunks > 0
    assert result.embedded_chunks == 0
    assert result.indexed_chunks == 0
```

Guard DB test như guide 12.

---

## 10. Done Khi

- [ ] `ingest_markdown_file(..., publish=False)` đọc/chunk/save DB được.
- [ ] Pipeline không chứa logic chunking chi tiết.
- [ ] Pipeline không chứa SQL upsert chi tiết.
- [ ] Error sau DB save có thể mark failed.
- [ ] CLI tạm thời chạy được.
- [ ] Test pipeline publish=False pass.

---

## 11. Lỗi Dễ Gặp

### Lỗi: circular import

Nguyên nhân:

```text
repository import pipeline, pipeline import repository.
```

Xử lý:

```text
repository khong duoc import pipeline.
Pipeline la layer tren cung cua ingestion.
```

### Lỗi: publish=True nhưng chưa có Qdrant

Xử lý:

```text
Cho publish=True raise NotImplementedError cho den khi xong guide 14-15.
```

### Lỗi: test pipeline ghi DB dev

Xử lý:

```text
Dung guard DATABASE_URL.endswith("/ctu_student_service_test").
```

## 12. Warning/Error Publish Contract

```text
warning:
- heading context kép;
- canonical Markdown heading bất thường nhưng parser vẫn tạo output hợp lệ.

error:
- không resolve được page range;
- duplicate logical_item_key;
- child thiếu parent_chunk_key;
- split vượt boundary;
- structural parse không tạo được output hợp lệ.
```

Default publish chỉ block `error`. `warning` được giữ trong `ChunkingResult`, log và preview.
Strict mode có thể block cả warning nhưng không phải default.
