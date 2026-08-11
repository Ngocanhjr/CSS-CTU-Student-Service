# 17. Part J - Hướng Dẫn Test Và Smoke Test End-To-End

**Last Updated:** 2026-07-10

File này tách chi tiết từ guide 07, phần J.

Mục tiêu:

```text
Chay duoc mot vertical slice tu Markdown -> PostgreSQL -> Qdrant -> Retrieval
```

Không yêu cầu frontend hoặc LLM answer trong guide này.

---

## 1. Điều Kiện Trước Khi Chạy

Đã implement xong:

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

Tại:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
```

Chạy:

```powershell
docker compose up -d postgres qdrant
docker compose ps
```

Kiểm tra PostgreSQL:

```powershell
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "\dn"
```

Kiểm tra Qdrant:

```powershell
Invoke-WebRequest -Uri http://localhost:6333/collections -UseBasicParsing
```

---

## 3. Set DB Test

Tại:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
```

Set:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
```

Chạy migration:

```powershell
..\..\.venv\Scripts\alembic.exe upgrade head
```

Kiểm tra:

```powershell
..\..\.venv\Scripts\alembic.exe current
```

---

## 4. Test Theo Tầng

Chạy schema:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/schemas
```

Chạy ingestion unit:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_markdown_reader.py test/ingestion/test_chunker.py test/ingestion/test_preview.py
```

Chạy DB:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/databases test/ingestion/test_ingestion_repository.py
```

Chạy embedding fake:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/embedding/test_embedder.py
```

Chạy vectorstore/retrieval:

```powershell
..\..\.venv\Scripts\python.exe -m pytest test/vectorstore test/retrieval
```

---

## 5. Tạo File Markdown Smoke Test

Nên tạo fixture test trong temp hoặc trong:

```text
chatbot/backend/test/fixtures/markdown/smoke_test.md
```

Nội dung:

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
checksum: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
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

Mong đợi:

```text
total_chunks > 0
parent_chunks > 0
child_chunks > 0
warnings = []
```

Nếu warnings có heading/page, sửa chunker trước khi tiếp.

---

## 7. Smoke Step 2 - Ingest PostgreSQL Only

```powershell
..\..\.venv\Scripts\python.exe -m app.ingestion.pipeline test\fixtures\markdown\smoke_test.md
```

Mong đợi theo contract “mỗi Markdown heading mở một Parent”:

```python
assert result.document_key == "smoke-quy-trinh-cap-bang-diem"
assert result.version_key == "smoke-quy-trinh-cap-bang-diem-v1"
assert result.parent_chunks == 3
assert result.child_chunks >= 2
assert result.total_chunks == result.parent_chunks + result.child_chunks
assert result.embedded_chunks == 0
assert result.indexed_chunks == 0
```

`# Quy trinh cap bang diem`, `## Dieu 1` và `## Dieu 2` tạo ba Parent. Heading title có thể tạo thêm `heading_content` Child theo classifier bảo thủ, nên không hardcode `child_chunks == 2`.

Kiểm tra DB:

```powershell
cd ..\..
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT document_key, title FROM css.documents WHERE document_key LIKE 'smoke%';"
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT chunk_type, count(*) FROM css.document_chunks GROUP BY chunk_type;"
```

---

## 8. Smoke Step 3 - Publish Qdrant

Sau khi embedder và vectorstore xong:

```powershell
cd backend
..\..\.venv\Scripts\python.exe -m app.ingestion.pipeline test\fixtures\markdown\smoke_test.md --publish
```

Mong đợi:

```text
embedded_chunks = child_chunks
indexed_chunks = child_chunks
```

Kiểm tra DB:

```powershell
cd ..
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT id, chunk_type, qdrant_point_id, index_status FROM css.document_chunks WHERE chunk_type='child';"
docker compose exec postgres psql -U ct239h -d ctu_student_service_test -c "SELECT rag_status FROM css.document_versions;"
```

Mong đợi:

```text
child chunks co qdrant_point_id
index_status = indexed
document_versions.rag_status = published
```

---

## 9. Smoke Step 4 - Retrieval

Tạo CLI tạm thời nếu cần:

```powershell
..\..\.venv\Scripts\python.exe -m app.retrieval.retriever "cap bang diem nop o dau"
```

Output mong đợi:

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

Nếu chưa có CLI retrieval, viết test integration thay thế.

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
            rerank=lambda results: results,  # deterministic test stub
            collection_name="ctu_chunks_bge_m3_test",
        )
        results = await retriever.search_resolved_query(
            session,
            query="cap bang diem nop o dau",
        )

    assert results
    assert results[0].citation
```

Lưu ý:

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

Do cascade, document_versions/chunks/status sẽ bị xóa nếu relationship cascade/ondelete đúng.

Qdrant cleanup:

```text
Xoa collection test hoac delete points theo document_key.
```

MVP đơn giản:

```python
client.delete_collection("ctu_chunks_bge_m3_test")
```

Chỉ dùng với collection test.

---


## 11.1 Test Contract Bổ Sung

Các test không chỉ kiểm tra số lượng chunk mà phải kiểm tra invariant:

```text
Long item:
- force split bằng fixture thật;
- cùng logical_item_key/parent_item_key;
- split_index/split_count đúng;
- không spill sang item kế tiếp.

Table:
- table nhỏ atomic;
- table lớn split theo row group;
- mỗi split lặp header + separator;
- cùng logical_table_key;
- không cắt giữa row.

Fenced code:
- atomic Child;
- marker trong code không thành heading/item;
- code dài split theo dòng, mỗi split có fence hợp lệ;
- cùng logical_code_key.

Heading-only:
- normative/independent heading -> heading_content Child;
- structural heading -> context_only_reason;
- uncertain heading -> heading_content + warning.

Hydration/expansion:
- content lấy từ PostgreSQL;
- structural metadata giữ từ Qdrant;
- parent_chunk_key fallback qua parent_chunk_id/parent row;
- child/parent/sibling/split expansion đúng;
- deduplicate, source-order và context budget đúng.
```

---

## 12. Done Khi

- [ ] PostgreSQL và Qdrant start được.
- [ ] Migration trên DB test chạy được.
- [ ] Preview smoke Markdown không warning nghiêm trọng.
- [ ] Pipeline `publish=False` save DB được.
- [ ] Pipeline `publish=True` embed/upsert được.
- [ ] Child chunks có `qdrant_point_id`.
- [ ] Retrieval trả về content và citation.
- [ ] Student filter không trả expired/unpublished document.
- [ ] Smoke test có thể chạy lại sau cleanup.

---

## 13. Lỗi Dễ Gặp

### Lỗi: test Qdrant dimension mismatch

Nguyên nhân:

```text
Dung chung collection cho fake vector va BGE-M3.
```

Xử lý:

```text
Dung collection rieng: test fake 3 dims, dev BGE-M3 1024 dims.
```

### Lỗi: ingest lại tạo duplicate DB rows

Nguyên nhân:

```text
Upsert document/version chua dung key hoac cleanup thieu.
```

Xử lý:

```text
Upsert theo document_key/version_key.
Delete chunks cu truoc khi insert lai.
```

### Lỗi: retrieval không có kết quả

Kiểm tra theo thứ tự:

```text
1. Qdrant collection co points khong.
2. Payload co review_status=approved, rag_status=published khong.
3. audience_student co true khong.
4. Query vector dimension co khop collection khong.
5. postgres_chunk_id co ton tai trong DB khong.
```

### Lỗi: citation thiếu page

Nguyên nhân:

```text
Smoke Markdown thieu <!-- page: 1 --> hoac chunker khong gan page.
```

Xử lý:

```text
Sua chunker/page marker truoc khi debug retriever.
```

## 14. Golden Fixture `test_3266.md`

Ngoài smoke fixture nhỏ, phải có golden test runnable cho tài liệu 3266.

Fixture path:

```text
chatbot/backend/test/fixtures/markdown/test_3266.md
```

Snapshot path:

```text
chatbot/backend/test/fixtures/snapshots/test_3266_chunks.json
```

Pytest command:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_3266_golden.py test/retrieval/test_structural_expansion.py
```

Concrete assertions:

```text
- standalone OCR page number và dấu --- ở page boundary không thành Child;
- page marker/HTML comment không nằm trong raw content hoặc embedding_text;
- mỗi Markdown heading mở Parent mới, không merge qua heading boundary;
- heading-only Điều 1/Điều 2/Điều 3 tạo heading_content Child hoặc context_only đúng rule;
- Chương I + NHỮNG VẤN ĐỀ CHUNG giữ derived heading_path kết hợp;
- heading bất thường "## Sau thời hạn đóng học phí..." sinh canonical_markdown_warning, không tự demote;
- Điều 18 tạo numbered/lettered Child riêng; bullet ngắn cùng parent có thể thành bullet group, giữ logical_item_keys và cross-page context;
- paragraph kế thừa item đang mở và không tạo report riêng;
- table Điều 19 là atomic table Child;
- legal_unit_type của legal list đúng và general list là none;
- logical_item_key/parent_item_key/split_index/split_count/item_path/page range đúng;
- Qdrant payload có đủ structural fields;
- retrieval expansion parent/child/sibling/split chạy đúng và giữ source order.
```

Golden snapshot phải kiểm tra Parent, Child, `heading_path`, `item_path`, `logical_item_key`, `logical_item_keys`,
`parent_item_key`, `page_start/page_end`, `split_index/split_count`, warnings/errors và block type.

Không yêu cầu fenced-code assertion trong `test_3266.md`, vì fixture này không có fenced code.
Fenced code dùng synthetic test riêng trong `test_chunker.py`.
