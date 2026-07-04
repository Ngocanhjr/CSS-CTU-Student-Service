# 17. Part J - Huong Dan Test Va Smoke Test End-To-End

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan J.

Muc tieu:

```text
Chay duoc mot vertical slice tu Markdown -> PostgreSQL -> Qdrant -> Retrieval
```

Khong yeu cau frontend hoac LLM answer trong guide nay.

---

## 1. Dieu Kien Truoc Khi Chay

Da implement xong:

```text
08 Part A - DB/schema contract
09 Part B - Markdown reader
10 Part C - Chunker
11 Part D - Preview
12 Part E - PostgreSQL repository
13 Part F - Pipeline publish=False
14 Part G - Embedding
15 Part H - Qdrant
16 Part I - Retrieval
```

Docker services:

```text
postgres
qdrant
```

---

## 2. Start Services

Tai:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
```

Chay:

```powershell
docker compose up -d postgres qdrant
docker compose ps
```

Kiem tra PostgreSQL:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dn"
```

Kiem tra Qdrant:

```powershell
Invoke-WebRequest -Uri http://localhost:6333/collections -UseBasicParsing
```

---

## 3. Set DB Test

Tai:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
```

Set:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Chay migration:

```powershell
..\..\.venv\Scripts\alembic.exe upgrade head
```

Kiem tra:

```powershell
..\..\.venv\Scripts\alembic.exe current
```

---

## 4. Test Theo Tang

Chay schema:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/schemas
```

Chay ingestion unit:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_markdown_reader.py test/ingestion/test_chunker.py test/ingestion/test_preview.py
```

Chay DB:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/databases test/ingestion/test_ingestion_repository.py
```

Chay embedding fake:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/embedding/test_embedder.py
```

Chay vectorstore/retrieval:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/vectorstore test/retrieval
```

---

## 5. Tao File Markdown Smoke Test

Nen tao fixture test trong temp hoac trong:

```text
chatbot/backend/test/fixtures/markdown/smoke_test.md
```

Noi dung:

```markdown
---
document_key: "smoke-quy-trinh-cap-bang-diem"
version_key: "smoke-quy-trinh-cap-bang-diem-v1"
title: "Quy trinh cap bang diem smoke test"
document_type: "quy_trinh"
domain: "dao_tao"
audience:
  - "student"
is_latest: true
source_path: "test/fixtures/markdown/smoke_test.md"
canonical_markdown_path: "test/fixtures/markdown/smoke_test.md"
file_type: "md"
language: "vi"
issuing_authority: "PDT"
checksum: "smoke-test-checksum"
ocr_status: "done"
review_status: "approved"
rag_status: "published"
---

<!-- page: 1 -->

# Quy trinh cap bang diem

## Dieu 1. Ho so

Sinh vien can nop don de nghi cap bang diem va giay to tuy than neu duoc yeu cau.

## Dieu 2. Noi tiep nhan

Sinh vien nop ho so tai Phong Dao tao hoac kenh truc tuyen theo thong bao cua Truong.
```

---

## 6. Smoke Step 1 - Preview

```powershell
..\..\.venv\Scripts\python.exe -m app.ingestion.preview test\fixtures\markdown\smoke_test.md
```

Mong doi:

```text
total_chunks > 0
parent_chunks > 0
child_chunks > 0
warnings = []
```

Neu warnings co heading/page, sua chunker truoc khi tiep.

---

## 7. Smoke Step 2 - Ingest PostgreSQL Only

```powershell
..\..\.venv\Scripts\python.exe -m app.ingestion.pipeline test\fixtures\markdown\smoke_test.md
```

Mong doi:

```json
{
  "document_key": "smoke-quy-trinh-cap-bang-diem",
  "version_key": "smoke-quy-trinh-cap-bang-diem-v1",
  "document_version_id": 1,
  "total_chunks": 4,
  "parent_chunks": 2,
  "child_chunks": 2,
  "embedded_chunks": 0,
  "indexed_chunks": 0
}
```

Kiem tra DB:

```powershell
cd ..\..
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT document_key, title FROM css.documents WHERE document_key LIKE 'smoke%';"
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT chunk_type, count(*) FROM css.document_chunks GROUP BY chunk_type;"
```

---

## 8. Smoke Step 3 - Publish Qdrant

Sau khi embedder va vectorstore xong:

```powershell
cd backend
..\..\.venv\Scripts\python.exe -m app.ingestion.pipeline test\fixtures\markdown\smoke_test.md --publish
```

Mong doi:

```text
embedded_chunks = child_chunks
indexed_chunks = child_chunks
```

Kiem tra DB:

```powershell
cd ..
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT id, chunk_type, qdrant_point_id, index_status FROM css.document_chunks WHERE chunk_type='child';"
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT rag_status FROM css.document_versions;"
```

Mong doi:

```text
child chunks co qdrant_point_id
index_status = indexed
document_versions.rag_status = published
```

---

## 9. Smoke Step 4 - Retrieval

Tao CLI tam thoi neu can:

```powershell
..\..\.venv\Scripts\python.exe -m app.retrieval.retriever "cap bang diem nop o dau"
```

Output mong doi:

```json
[
  {
    "chunk_key": "123",
    "score": 0.8,
    "title": "Quy trinh cap bang diem smoke test",
    "source_file": "smoke_test.md",
    "citation": "smoke_test.md, trang 1"
  }
]
```

Neu chua co CLI retrieval, viet test integration thay the.

---

## 10. Integration Test E2E

File:

```text
chatbot/backend/test/integration/test_rag_smoke.py
```

Suggested flow:

```python
@pytest.mark.integration
async def test_markdown_to_retrieval_smoke(tmp_path):
    path = tmp_path / "smoke.md"
    path.write_text(SMOKE_MARKDOWN, encoding="utf-8")

    result = await ingest_markdown_file(path, publish=True)

    assert result.child_chunks > 0
    assert result.indexed_chunks == result.child_chunks

    async with AsyncSessionLocal() as session:
        retriever = Retriever(
            embedder=FakeEmbedder(dimensions=3),
            qdrant_client=get_qdrant_client(),
            collection_name="test_ctu_student_service_chunks",
        )
        results = await retriever.search(session, query="cap bang diem nop o dau")

    assert results
    assert results[0].citation
```

Luu y:

```text
Neu dung FakeEmbedder dimensions=3, Qdrant collection test phai vector_size=3.
Khong dung chung collection voi BGE-M3 1024 dimensions.
```

---

## 11. Cleanup Smoke Data

DB cleanup:

```sql
DELETE FROM css.documents WHERE document_key LIKE 'smoke-%';
```

Do cascade, document_versions/chunks/status se bi xoa neu relationship cascade/ondelete dung.

Qdrant cleanup:

```text
Xoa collection test hoac delete points theo document_key.
```

MVP don gian:

```python
client.delete_collection("test_ctu_student_service_chunks")
```

Chi dung voi collection test.

---

## 12. Done Khi

- [ ] PostgreSQL va Qdrant start duoc.
- [ ] Migration tren DB test chay duoc.
- [ ] Preview smoke Markdown khong warning nghiem trong.
- [ ] Pipeline `publish=False` save DB duoc.
- [ ] Pipeline `publish=True` embed/upsert duoc.
- [ ] Child chunks co `qdrant_point_id`.
- [ ] Retrieval tra ve content va citation.
- [ ] Student filter khong tra expired/unpublished document.
- [ ] Smoke test co the chay lai sau cleanup.

---

## 13. Loi De Gap

### Loi: test Qdrant dimension mismatch

Nguyen nhan:

```text
Dung chung collection cho fake vector va BGE-M3.
```

Xu ly:

```text
Dung collection rieng: test fake 3 dims, dev BGE-M3 1024 dims.
```

### Loi: ingest lai tao duplicate DB rows

Nguyen nhan:

```text
Upsert document/version chua dung key hoac cleanup thieu.
```

Xu ly:

```text
Upsert theo document_key/version_key.
Delete chunks cu truoc khi insert lai.
```

### Loi: retrieval khong co ket qua

Kiem tra theo thu tu:

```text
1. Qdrant collection co points khong.
2. Payload co review_status=approved, rag_status=published khong.
3. audience_student co true khong.
4. Query vector dimension co khop collection khong.
5. postgres_chunk_id co ton tai trong DB khong.
```

### Loi: citation thieu page

Nguyen nhan:

```text
Smoke Markdown thieu <!-- page: 1 --> hoac chunker khong gan page.
```

Xu ly:

```text
Sua chunker/page marker truoc khi debug retriever.
```
