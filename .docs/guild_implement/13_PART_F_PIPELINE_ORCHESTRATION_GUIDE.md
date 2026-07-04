# 13. Part F - Huong Dan Implement Ingestion Pipeline Orchestration

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan F.

Muc tieu:

```text
Dieu phoi reader -> chunker -> repository -> embedding -> qdrant
```

Pipeline khong nen chua logic chi tiet cua tung phan. No chi goi cac module da tach.

---

## 1. File Can Sua

```text
chatbot/backend/app/ingestion/pipeline.py
chatbot/backend/test/ingestion/test_pipeline.py
```

Pipeline phu thuoc vao:

```text
app.ingestion.markdown_reader
app.ingestion.chunking.chunker
app.ingestion.repository
app.embedding.embedder
app.vectorstore.repository
app.databases.session
```

Chunker hien tai da tach module:

```text
chunking/chunker.py chi orchestration chunk.
chunking/parent_chunker.py build ParentSection va parent Chunk.
chunking/child_chunker.py split parent Chunk thanh child Chunks.
Pipeline chi goi chunk_markdown_document(document).
```

---

## 2. Mode Chay

Pipeline nen co 2 mode:

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

Lam `publish=False` truoc de test DB/chunking khong can model embedding/Qdrant.

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

## 4. Helper Dem Chunk

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
    chunks = chunk_markdown_document(document)
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

    return await publish_saved_document(result)
```

`publish_saved_document` se lam trong guide 14-15 sau khi co embedder va qdrant repository.

---

## 6. Publish Guard

Truoc khi embed/upsert, can check:

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
`review_status = approved AND rag_status = published`. Khong dung `validity_status` cho version.

MVP chi can student publish.

---

## 7. Error Handling

Khi pipeline loi, can ghi ingestion job neu da co document_version.

MVP don gian:

```text
Neu loi truoc khi save DB: raise.
Neu loi sau khi save DB: update status failed.
```

Suggested helper:

```python
async def mark_ingestion_failed(document_version_id: int, stage: str, error: Exception) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            status = await session.get(DocumentVersionStatus, document_version_id)
            if status:
                status.rag_status = "failed"
                status.status_note = f"{stage}: {error}"
```

Luu y:

```text
Khong swallow exception. Mark failed xong van raise.
```

---

## 8. CLI Tam Thoi

Them vao `pipeline.py`:

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
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
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

Guard DB test nhu guide 12.

---

## 10. Done Khi

- [ ] `ingest_markdown_file(..., publish=False)` doc/chunk/save DB duoc.
- [ ] Pipeline khong chua logic chunking chi tiet.
- [ ] Pipeline khong chua SQL upsert chi tiet.
- [ ] Error sau DB save co the mark failed.
- [ ] CLI tam thoi chay duoc.
- [ ] Test pipeline publish=False pass.

---

## 11. Loi De Gap

### Loi: circular import

Nguyen nhan:

```text
repository import pipeline, pipeline import repository.
```

Xu ly:

```text
repository khong duoc import pipeline.
Pipeline la layer tren cung cua ingestion.
```

### Loi: publish=True nhung chua co Qdrant

Xu ly:

```text
Cho publish=True raise NotImplementedError cho den khi xong guide 14-15.
```

### Loi: test pipeline ghi DB dev

Xu ly:

```text
Dung guard DATABASE_URL.endswith("/ctu_student_service_test").
```
