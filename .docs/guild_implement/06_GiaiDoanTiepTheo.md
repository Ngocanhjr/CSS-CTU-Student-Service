---
title: "Hướng dẫn 06 - Giai đoạn ingestion và indexing RAG end-to-end"
document_type: "huong_dan_quan_tri"
domain: "rag_ingestion"
department: "NLCS"
audience:
  - "developer"
  - "admin"
  - "researcher"
version: "1.0"
status: "draft"
created_at: "2026-06-19"
updated_at: "2026-07-04"
tags:
  - nlcs
  - chatbot
  - rag
  - ingestion
  - chunking
  - embedding
  - qdrant
  - postgresql
---

# Hướng dẫn 06 - Giai đoạn ingestion và indexing RAG end-to-end

File này dùng cho giai đoạn tiếp theo sau khi đã có:

- Vault tài liệu NLCS với `02_Attachments`, `06_Processing`, `01_Dataset`.
- Metadata schema Pydantic cho document, asset, chunk.
- SQLAlchemy models cho PostgreSQL.
- Migration khởi tạo các bảng RAG lõi.
- Quyết định công nghệ: FastAPI, PostgreSQL, Qdrant, LangChain, `BAAI/bge-m3`.

Mục tiêu của giai đoạn 06 là làm chạy được một vertical slice tối thiểu:

```text
Canonical Markdown đã được OCR/làm sạch từ bên ngoài
→ backend nhận file .md
→ đọc YAML metadata
→ validate metadata
→ tạo parent/child chunks
→ lưu document/version/chunks vào PostgreSQL
→ embed child chunks
→ upsert vector vào Qdrant
→ retrieval trả về chunk có citation
```

Không triển khai HNSW tuning, reranking nâng cao hoặc UI phức tạp trong giai đoạn này.

---

## 1. Phạm vi của giai đoạn 06

### Làm trong giai đoạn này

- Chuẩn hóa contract giữa YAML metadata, Pydantic schema, SQLAlchemy model và migration.
- Viết Markdown ingestion pipeline nhận file `.md` canonical đã OCR từ bên ngoài.
- Viết chunker theo heading và page marker.
- Lưu metadata/chunks vào PostgreSQL.
- Embed child chunks bằng `BAAI/bge-m3`.
- Upsert Qdrant point với payload đủ để trace về PostgreSQL.
- Viết retrieval tối thiểu để search Qdrant và trả citation.
- Có test cho schema, chunker, metadata validation và ingest một file mẫu.

### Chưa làm trong giai đoạn này

- Không tích hợp OCR hay LlamaParse trong backend — quá trình OCR chạy hoàn toàn bên ngoài, backend chỉ nhận canonical Markdown đã qua xử lý.
- Không chỉnh nội dung nghiệp vụ của tài liệu gốc trong pipeline.
- Không dùng raw OCR output làm nguồn RAG nếu đã có canonical Markdown.
- Không publish tài liệu chưa được review hoặc chưa rag_status=published cho student chatbot.
- Không tối ưu HNSW hoặc custom vector index.
- Không làm frontend đầy đủ trước khi backend retrieval chạy ổn.

---

## 2. Đầu vào bắt buộc

Backend nhận canonical Markdown đã được OCR và làm sạch từ bên ngoài. File nên nằm trong:

```text
nlcs/01_Dataset/
```

Trong giai đoạn thử nghiệm có thể dùng file đã làm sạch ở:

```text
nlcs/06_Processing/03_Markdown_Cleaning/
```

nhưng phải coi đó là dữ liệu test, không phải nguồn publish chính thức.

Metadata tối thiểu cần thống nhất theo code backend hiện tại:

```yaml
document_key: ""
version_key: ""
title: ""
document_type: "noi_quy"
domain: ""
audience:
  - "student"

is_latest: true

source_url: ""
source_path: ""
canonical_markdown_path: ""
file_type: "md"
accessed_date:

language: "vi"
issuing_authority: ""
signer_name: ""
checksum: ""

ocr_status: "done"
review_status: "approved"
rag_status: "published"
```

Ghi chú quan trọng:

- Dùng `document_key` và `version_key` cho backend mới.
- Không dùng lại cặp tên cũ `document_id` / `version_id` trong Pydantic metadata nếu code đã chuyển sang quy ước `*_key`.
- `checksum` là bắt buộc để audit nội dung version.

---

## 3. Điều kiện ingest và publish

### Student-facing RAG

Chỉ dùng tài liệu cho chatbot sinh viên khi đủ:

```text
review_status = approved
rag_status = published
```

Nếu thiếu một trong hai điều kiện này, pipeline có thể validate hoặc chunk thử, nhưng retriever student phải bỏ qua.

### Admin/internal search

Tài liệu hết hiệu lực hoặc chưa publish có thể được index cho tra cứu nội bộ nếu:

```text
review_status = approved
rag_status = indexed
```

Không chuyển tài liệu chưa approve sang `published`.

---

## 4. Thứ tự triển khai khuyến nghị

### Bước 1 - Chốt lại contract DB và schema

Kiểm tra các file:

```text
chatbot/backend/app/schemas/documents.py
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/databases/models/documents.py
chatbot/backend/app/databases/models/chunks.py
chatbot/backend/alembic/versions/
```

Việc cần làm:

- Đồng bộ nullable giữa SQLAlchemy model và migration.
- Các field ngày như `issued_date`, `accessed_date` nên cho phép `NULL` nếu Pydantic đang cho phép `None`.
- Các field chunk như `page_start`, `page_end`, `token_count` nên cho phép `NULL` nếu chunk không xác định được trang hoặc chưa đếm token.
- Kiểm tra `updated_at`: nếu model dùng `onupdate` nhưng không có default, migration insert ban đầu có thể thiếu giá trị.
- Chạy test model trước khi viết ingestion thật.

Done khi:

- Migration chạy được từ database trống.
- Test SQLAlchemy model pass.
- Tạo được schema `css` và các bảng lõi.

---

### Bước 2 - Nhận canonical Markdown và viết Markdown reader

Backend nhận file `.md` đã được OCR/làm sạch từ bên ngoài (không tích hợp OCR trong backend).

Module đề xuất:

```text
chatbot/backend/app/ingestion/markdown_reader.py
```

Reader cần làm:

- Đọc file `.md`.
- Tách YAML frontmatter và body.
- Parse YAML bằng parser thật, không tự split thủ công nếu có thể tránh.
- Validate YAML bằng `DocumentMetadata`.
- Trả về object gồm `metadata`, `body`, `source_path`.

Không làm ở bước này:

- Không chunk.
- Không embed.
- Không ghi database.

Done khi:

- Đọc được một file Markdown mẫu.
- Báo lỗi rõ nếu thiếu `document_key`, `version_key`, `checksum`.
- Báo lỗi rõ nếu `rag_status = published` nhưng chưa đủ điều kiện publish.

---

### Bước 3 - Viết structural parent-child chunker

Module đề xuất:

```text
chatbot/backend/app/ingestion/chunking/
```

Chunker dùng structural parser trước, LangChain splitter sau:

- Mỗi Markdown heading tạo parent section mới.
- Nội dung trước heading đầu tiên thuộc `heading_path = ["document-root"]`.
- `numbered_item`, `lettered_item`, `bullet_item` tạo StructuralBlock boundary; child chunker chỉ có thể gộp bullet ngắn cùng heading và cùng item cha.
- Table/code được detect trước item regex.
- `RecursiveCharacterTextSplitter` chỉ split bên trong item/paragraph quá dài; table/code dùng logic riêng.

Chunker cần hiểu:

```markdown
<!-- page: 1 -->

# Tên tài liệu

## Chương I

### Điều 1. Phạm vi điều chỉnh
```

Quy tắc chunk:

- Parent chunk theo Markdown heading section.
- Child chunk cắt từ parent bằng recursive character splitter khi nội dung dài.
- Mỗi child phải có `parent_chunk_key` là stable parent key trước khi insert DB.
- Mỗi chunk phải giữ `heading_path`.
- `page_start` và `page_end` lấy từ page marker gần nhất.
- `chunk_index` tăng tuần tự global trong cùng một `version_key`, không reset riêng parent/child.
- `chunk_type` là `parent` hoặc `child` (không dùng chunk_level).

Gợi ý định danh:

```text
parent: <version_key>::p::<parent_index_4_digits>
child:  <version_key>::c::<child_index_4_digits>
```

Sau khi lưu DB, `document_chunks.id` là internal DB id. Repository chịu trách nhiệm map `parent_chunk_key` sang `parent_chunk_id` (cột self-FK trong DB).

Done khi:

- Tạo được parent và child chunks từ một file thật.
- Không mất nội dung giữa các page marker.
- Heading path không rỗng với section có heading.
- Child chunk validate được bằng `app.schemas.chunks.Chunk`.
- Draft keys theo đúng format `<version_key>::p::0001` và `<version_key>::c::0001`.

---

### Bước 4 - Preview chunk trước khi ghi DB

Module hoặc command đề xuất:

```text
chatbot/backend/app/ingestion/preview.py
```

Preview nên xuất JSON hoặc Markdown ngắn gồm:

```text
chunk_key
parent_chunk_key
chunk_type
heading_path
page_start
page_end
token_count
content preview
```

Checklist preview:

- [ ] Tổng số chunk hợp lý.
- [ ] Không có chunk rỗng.
- [ ] Không có child thiếu parent.
- [ ] Không có parent gắn parent khác.
- [ ] Page range không đảo ngược.
- [ ] Nội dung bảng không bị mất.
- [ ] Nội dung điều/khoản không bị cắt sai nghĩa.

Done khi có thể preview ít nhất một tài liệu CTSV và một tài liệu PDT.

---

### Bước 5 - Lưu metadata và chunks vào PostgreSQL

Module đề xuất:

```text
chatbot/backend/app/ingestion/repository.py
```

Thứ tự ghi:

```text
departments
→ document_types
→ documents
→ document_versions  (bao gồm set status trực tiếp: review_status, rag_status, ocr_status)
→ document_recipients
→ document_chunks parent
→ document_chunks child  (resolve parent_chunk_key → parent_chunk_id)
→ ingestion_jobs
```

Nguyên tắc:

- Upsert theo `document_key`, `version_key`.
- Không tạo version trùng.
- Không xóa version cũ khi ingest version mới.
- Status workflow (review_status, rag_status, ocr_status) được lưu trực tiếp trên bảng `document_versions`, không có bảng `document_version_status` riêng.
- `document_recipients` ghi nhận đối tượng thụ hưởng (audience) của từng version.
- PostgreSQL là nguồn metadata chính; Qdrant chỉ lưu payload phục vụ search.

Done khi:

- Ingest một Markdown mẫu vào PostgreSQL.
- Query được document, version và chunks.
- Parent-child chunks liên kết đúng qua `parent_chunk_id`.

---

### Bước 6 - Embedding child chunks

Module đề xuất:

```text
chatbot/backend/app/embedding/embedder.py
```

Chỉ embed child chunk ở giai đoạn đầu.

Input embedding nên ghép:

```text
Tài liệu: <title>
Loại: <document_type>
Mục: <heading_path>
Trang: <page_start>-<page_end>

<content>
```

Không embed:

- Parent chunk.
- Chunk rỗng.
- Tài liệu chưa approved nếu đang chạy student pipeline.
- Tài liệu chưa rag_status=published.

Done khi:

- Tạo được vector cho batch child chunks.
- Lưu được model/version embedding dùng cho audit.
- Có xử lý lỗi theo batch, không làm hỏng toàn bộ job khi một chunk lỗi.

---

### Bước 7 - Upsert Qdrant

Module đề xuất:

```text
chatbot/backend/app/vectorstore/repository.py
```

Payload tối thiểu:

```json
{
  "document_key": "",
  "version_key": "",
  "chunk_key": "",
  "parent_chunk_key": "",
  "chunk_type": "child",
  "document_type": "",
  "domain": "",
  "audience": ["student"],
  "review_status": "approved",
  "rag_status": "published",
  "is_latest": true,
  "page_start": 1,
  "page_end": 1,
  "postgres_chunk_id": 0
}
```

Nguyên tắc:

- Point ID nên ổn định theo `version_key + chunk_key`.
- Qdrant payload phải đủ để filter nhanh.
- Qdrant payload phải đủ để trace về PostgreSQL.
- Sau khi upsert thành công, cập nhật `document_chunks.qdrant_point_id` và `index_status`.

Done khi:

- Upsert được child chunks vào collection.
- Search Qdrant trả về đúng payload.
- PostgreSQL biết chunk nào đã có vector.

---

### Bước 8 - Retrieval tối thiểu

Module đề xuất:

```text
chatbot/backend/app/retrieval/retriever.py
```

Retriever student phải filter:

```text
review_status = approved
rag_status = published
audience contains student
```

Output tối thiểu:

```json
{
  "query": "",
  "results": [
    {
      "chunk_key": "",
      "score": 0.0,
      "content": "",
      "title": "",
      "page_start": 1,
      "page_end": 1,
      "source_file": ""
    }
  ]
}
```

Done khi:

- Query thử trả về chunk liên quan.
- Citation có trang hoặc section.
- Không trả tài liệu chưa publish cho student.

---

## 5. Test bắt buộc cho giai đoạn 06

### Unit tests

- `DocumentMetadata` reject publish sai điều kiện.
- `Chunk` reject child không có parent_chunk_key.
- Markdown reader tách đúng YAML/body.
- Chunker giữ đúng heading path.
- Chunker giữ page range hợp lệ.
- Chunker gán đúng `chunk_type` (parent/child).

### Integration tests

- Ingest một Markdown mẫu vào PostgreSQL test database.
- Tạo chunks từ file thật trong `nlcs/06_Processing/03_Markdown_Cleaning/`.
- Upsert mock hoặc test Qdrant collection.
- Search với filter student không trả tài liệu chưa review_status=approved hoặc chưa rag_status=published.

### Smoke test thủ công

```text
1. Chạy PostgreSQL và Qdrant bằng compose.
2. Chạy migration.
3. Preview chunk một file Markdown.
4. Ingest file đó vào PostgreSQL.
5. Embed và upsert Qdrant.
6. Search thử một câu hỏi.
7. Kiểm tra citation trỏ đúng tài liệu/trang.
```

---

## 6. Tiêu chí hoàn thành giai đoạn 06

Giai đoạn 06 hoàn thành khi đạt đủ:

- [ ] Migration chạy sạch từ database trống (9 bảng lõi).
- [ ] Backend nhận canonical Markdown đã OCR từ bên ngoài, không tích hợp OCR trong pipeline.
- [ ] Một file Markdown canonical được validate metadata.
- [ ] Chunker tạo parent/child chunks hợp lệ với đúng `chunk_type` và `parent_chunk_key`.
- [ ] PostgreSQL lưu document/version (status trên document_versions)/chunks với parent_chunk_id đúng.
- [ ] `document_recipients` ghi nhận audience của version.
- [ ] Embedding tạo vector cho child chunks.
- [ ] Qdrant lưu vector và payload.
- [ ] Retriever trả kết quả có citation.
- [ ] Student retriever chỉ trả tài liệu có review_status=approved AND rag_status=published.
- [ ] Có test tự động cho các contract chính.
- [ ] Có log ingestion_jobs để debug khi lỗi.

---

## 7. Rủi ro cần xử lý sớm

| Rủi ro | Cách xử lý |
|---|---|
| Metadata YAML dùng `document_id` cũ trong khi backend dùng `document_key` | Viết mapper hoặc chuẩn hóa metadata trước khi ingest |
| Migration không khớp model nullable | Sửa model/migration trước khi viết ingestion |
| Page marker thiếu hoặc sai | Cho phép `page_start/page_end = null`, nhưng log cảnh báo |
| Chunk quá dài do section lớn | Tách child theo token limit, giữ heading context |
| Bảng Markdown bị cắt vỡ | Không split giữa bảng nếu có thể; preview trước khi ingest |
| Qdrant có vector cũ | Dùng point ID ổn định và upsert idempotent |
| Tài liệu chưa publish lọt vào student chatbot | Filter cứng ở retriever theo review_status=approved AND rag_status=published |
| canonical Markdown chưa sạch | Kiểm tra ocr_status=done trong metadata; từ chối ingest nếu chưa done |

---

## 8. Thứ tự làm việc trong một ngày code

Khuyến nghị không làm lan man. Đi theo thứ tự:

1. Sửa contract DB/schema cho chạy migration sạch.
2. Viết Markdown reader và test.
3. Viết chunker và preview CLI nhỏ.
4. Ingest metadata/chunks vào PostgreSQL.
5. Embed child chunks.
6. Upsert Qdrant.
7. Viết retriever search tối thiểu.
8. Chạy smoke test end-to-end với một file thật.

Nếu một bước chưa chạy được, không nhảy sang bước sau trừ khi đang viết mock để test độc lập.

---

## 9. File nên ưu tiên đọc khi bắt đầu

```text
nlcs/QuickGuide_QuyTrinh_XuLy.md
nlcs/05_Research/Database_rule.md
chatbot/README.md
chatbot/backend/README.md
chatbot/note.md
chatbot/db_note.md
chatbot/backend/app/schemas/documents.py
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/databases/models/documents.py
chatbot/backend/app/databases/models/chunks.py
```

Các file này đủ để bắt đầu giai đoạn 06 mà không cần thiết kế lại kiến trúc.
