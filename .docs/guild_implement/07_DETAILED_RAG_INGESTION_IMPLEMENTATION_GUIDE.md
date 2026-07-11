# 07. Hướng Dẫn Chi Tiết Implement Markdown Ingestion, Chunking, Embedding, Qdrant

**Last Updated:** 2026-07-10

File này nối tiếp sau:

```text
06_GiaiDoanTiepTheo.md
```

Guide 06 mô tả bức tranh tổng quát. Guide 07 đi vào từng phần cần implement trong backend để có một vertical slice RAG chạy được:

```text
Markdown canonical
-> validate YAML metadata
-> tạo parent/child chunks
-> preview chunks
-> lưu PostgreSQL
-> embed child chunks
-> upsert Qdrant
-> retrieval có citation
```

Không làm frontend, HNSW tuning, reranking nâng cao, hoặc prompt QA phức tạp trong guide này.

---

## 0. Trạng Thái Hiện Tại

Đã có:

```text
chatbot/backend/app/schemas/documents.py
chatbot/backend/app/schemas/assets.py
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/schemas/enums.py
chatbot/backend/app/databases/models/
chatbot/backend/test/schemas/
chatbot/backend/test/databases/test_database_models.py
```

Đang còn trống hoặc chưa có logic:

```text
chatbot/backend/app/ingestion/pipeline.py
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/embedding/embeder.py
```

Ghi chú:

```text
app/embedding/embeder.py đang bị đặt tên thiếu "d".
Khi implement nên tạo app/embedding/embedder.py cho tên đúng.
Nếu cần giữ backward compatibility, để embeder.py re-export từ embedder.py sau.
```

---

## 1. Mục Tiêu Của Guide 07

Sau guide này cần đạt được:

```text
1. Metadata Markdown đọc được validate bằng DocumentMetadata.
2. Chunker tạo được Chunk schema hợp lệ.
3. Có preview chunk trước khi ghi database.
4. Ingest được một file Markdown vào PostgreSQL.
5. Embed được child chunks bằng BAAI/bge-m3.
6. Upsert được vectors vào Qdrant.
7. Search trả về content + payload + citation.
8. Test không cho student retrieval lấy tài liệu chưa publish.
```

MVP chỉ cần chạy tốt với 1-2 file thật trong:

```text
nlcs/06_Processing/03_Markdown_Cleaning/
```

Sau đó mới mở rộng sang:

```text
nlcs/01_Dataset/
```

---

## 2. Nguyên Tắc Bắt Buộc

### 2.1. PostgreSQL là metadata source of truth

```text
PostgreSQL lưu document/version/status/chunks/job.
Qdrant chỉ lưu vector + payload để search nhanh.
```

Không dùng Qdrant để thay thế PostgreSQL.

### 2.2. Qdrant point phải trace ngược được PostgreSQL

Payload Qdrant tối thiểu phải có:

```text
document_key
version_key
chunk_key              # stable schema/vector key
parent_chunk_key       # stable parent key nếu có
postgres_chunk_id     # int DocumentChunk.id để hydrate từ PostgreSQL
title
page_start
page_end
source_file
```

### 2.3. Chỉ embed child chunk trong MVP

Parent chunk dùng để giữ ngữ cảnh và quan hệ section.

MVP:

```text
parent chunk: lưu PostgreSQL, không embed
child chunk: lưu PostgreSQL, embed, upsert Qdrant
```

### 2.4. Student retrieval phải filter cùng

Filter student:

```text
review_status = approved
rag_status = published
audience contains student
```

Không chỉ dựa vào việc ingestion đã lọc. Retriever vẫn phải lọc lại.

---

## 3. Dependency Cần Có

File:

```text
chatbot/backend/requirements.txt
```

Nên bổ sung khi bắt đầu implement:

```text
PyYAML>=6.0
langchain-text-splitters>=0.2
qdrant-client>=1.9
sentence-transformers>=3.0
numpy>=1.26
```

Test import nhanh:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -c "import yaml, qdrant_client, numpy; import langchain_text_splitters; print('deps ok')"
```

Nếu chưa dùng Qdrant/embedding thật trong unit test, có thể mock để test logic ingestion trước.

---

## 4. Phần A - Chốt Lại Contract DB/Schema Trước Khi Ingest

Làm phần này trước khi viết reader/chunker.

### 4.1. File Cần Kiểm Tra

```text
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/databases/models/chunks.py
chatbot/backend/alembic/versions/
chatbot/backend/test/databases/test_database_models.py
```

### 4.2. Vấn Đề Cần Xử Lý Sớm

Pydantic `Chunk` đang có:

```text
chunk_key
parent_chunk_key
chunk_type
```

DB `document_chunks` phải có cột stable `chunk_key`. Contract tối thiểu:

```text
id  
document_version_id
chunk_key
parent_chunk_id
chunk_index
chunk_type
...
qdrant_point_id
```

Quyết định:

```text
Dùng Chunk.chunk_key làm stable key từ schema/preview/tới Qdrant.
Lưu chunk_key trong document_chunks.
Dùng DocumentChunk.id riêng làm postgres_chunk_id/internal id.
```

### 4.3. Quyết Định Đề Xuất

Thêm cột `chunk_key` vào `DocumentChunk`.

Dùng mapping trong repository:

```text
Chunk.chunk_key -> DocumentChunk.chunk_key
Chunk.parent_chunk_key -> parent DocumentChunk.id -> DocumentChunk.parent_chunk_id
```

Sau khi insert PostgreSQL:

```text
DocumentChunk.id             = internal DB id
DocumentChunk.chunk_key      = stable chunk key
DocumentChunk.parent_chunk_id = internal FK resolved from parent_chunk_key
```

Lý do:

```text
PostgreSQL là source of truth.
chunk_key giúp idempotent ingest và trace ổn định.
postgres_chunk_id giúp hydrate nhanh từ PostgreSQL khi retrieve.
```

Không dùng `qdrant_point_id` thay cho `chunk_key`, vì point id là chi tiết của vector store.

### 4.4. Nullable Cần Đồng Bộ

Nếu schema Pydantic cho phép `None`, DB/migration cũng nên cho phép nullable:

```text
DocumentVersion.issued_date
DocumentVersion.accessed_date
DocumentChunk.page_start
DocumentChunk.page_end
DocumentChunk.token_count
```

Nếu DB bắt buộc non-null, chunker phải luôn gán giá trị fallback. Khuyến nghị MVP:

```text
Khong co page marker: fallback page_start/page_end = 1.
```

### 4.5. Done khi

```text
pytest test/schemas test/databases
```

pass, và migration test database chạy sạch.

---

## 5. Phần B - Markdown Reader

### 5.1. File Nên Tạo

```text
chatbot/backend/app/ingestion/markdown_reader.py
chatbot/backend/test/ingestion/test_markdown_reader.py
```

### 5.2. Trách Nhiệm

Markdown reader chỉ làm 4 việc:

```text
1. Đọc file .md.
2. Tách YAML frontmatter và Markdown body.
3. Parse YAML bằng yaml.safe_load.
4. Validate metadata bằng DocumentMetadata.
```

Không chunk, không ghi DB, không embed trong reader.

### 5.3. Contract output

Suggested pattern:

```python
from dataclasses import dataclass
from pathlib import Path

from app.schemas.documents import DocumentMetadata


@dataclass(frozen=True)
class MarkdownDocument:
    path: Path
    metadata: DocumentMetadata
    body: str
    raw_frontmatter: dict
```

### 5.4. Tách Frontmatter

Accepted format:

```markdown
---
document_key: "..."
version_key: "..."
---

# Nội dung
```

Rule:

```text
File phải bắt đầu bằng ---
Frontmatter kết thúc bằng dòng ---
Body không được rỗng
YAML parse ra dict
```

Suggested pattern:

```python
def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("Markdown file must start with YAML frontmatter")

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError("Markdown file has no closing YAML frontmatter marker")

    _, yaml_text, body = parts
    data = yaml.safe_load(yaml_text) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    if not body.strip():
        raise ValueError("Markdown body is empty")

    return data, body.strip()
```

Nếu file dùng CRLF, normalize trước:

```python
text = text.replace("\r\n", "\n")
```

### 5.5. Check checksum

Có 2 cách:

```text
Cách A: checksum là metadata bắt buộc do người tạo file điền.
Cách B: pipeline tính checksum body và compare với metadata nếu có.
```

MVP nên làm:

```text
Nếu checksum rỗng -> reject, vì DocumentMetadata đang bắt buộc checksum.
Chưa cần compare content hash trong bước đầu.
```

Sau MVP có thể thêm:

```text
metadata_hash = sha256(frontmatter normalized)
content_checksum = sha256(body)
```

### 5.6. Test Cần Có

```text
test_read_markdown_with_valid_frontmatter
test_reader_rejects_missing_frontmatter
test_reader_rejects_invalid_yaml_mapping
test_reader_rejects_empty_body
test_reader_rejects_published_invalid_status
```

---

## 6. Phần C - Heading-Aware Chunker

### 6.1. File Nên Tạo

```text
chatbot/backend/app/ingestion/chunking/
chatbot/backend/test/ingestion/test_chunker.py
```

### 6.2. Input Và Output

Input:

```text
DocumentMetadata
Markdown body
```

Output:

```text
ChunkingResult
```

Dùng schema hiện có:

```python
from app.schemas.chunks import Chunk
```

`ChunkingResult` là public return contract của `chunk_markdown_body()` và
`chunk_markdown_document()`:

```python
@dataclass(frozen=True)
class ChunkingResult:
    parent_chunks: list[Chunk]
    child_chunks: list[Chunk]
    warnings: list[ValidationReport]
    errors: list[ValidationReport]
```

`make_child_chunks()` vẫn là helper nội bộ và vẫn trả `list[Chunk]`.

### 6.3. Markdown Pattern Cần Nhận Diện

Page marker:

```markdown
<!-- page: 1 -->
```

Heading:

```markdown
# Title
## Chuong I
### Dieu 1. Pham vi dieu chinh
#### Khoan 1
```

Bảng Markdown:

```markdown
| Cot A | Cot B |
|---|---|
| A | B |
```

### 6.4. Quy Tắc heading_path

Khi gặp heading:

```text
#      -> level 1
##     -> level 2
###    -> level 3
####   -> level 4
```

Cập nhật stack:

```text
current_heading_path = headings từ level 1 đến level hiện tại
```

Ví dụ:

```text
# Quy dinh hoc vu
## Chuong II
### Dieu 5
```

Chunk bên trong `Dieu 5` có:

```python
heading_path = ["Quy dinh hoc vu", "Chuong II", "Dieu 5"]
```

### 6.5. Quy Tắc Parent Chunk

MVP đề xuất:

```text
Mỗi Markdown heading bắt đầu một parent chunk mới.
Parent hiện tại kết thúc ngay trước Markdown heading kế tiếp, bất kể heading cấp mấy.
Nội dung trước heading đầu tiên thuộc parent gốc `heading_path = ["document-root"]`.
Nếu tài liệu không có heading, tạo một parent `heading_path = ["document-root"]`.
```

Parent chunk:

```text
chunk_type = "parent"
parent_chunk_key = None
content = toàn bộ section hoặc summary raw của section
```

Nếu parent quá dài, vẫn có thể lưu content đầy đủ trong PostgreSQL. Không embed parent trong MVP.

### 6.6. Quy Tắc Child Chunk

Child chunk được tạo từ structural blocks trong parent.

MVP dùng item boundary trước:

```text
numbered_item
lettered_item
bullet_item
table
code
paragraph ro rang doc lap
```

Rule bắt buộc:

```text
StructuralBlock khong phai Chunk. Parser tao moi numbered_item, lettered_item, bullet_item thanh block rieng.
numbered_item/lettered_item, ke ca item ngan hoac ket thuc bang ":", luon tao Child rieng.
bullet ngan lien ke chi duoc gop boi child_chunker khi cung heading_path va parent_item_key;
chunk gop giu logical_item_keys cua tat ca bullet thanh vien.
Item cha co item con van tao Child rieng; item con tao Child rieng.
Item con link ve item cha bang parent_item_key trong Chunk.metadata in-memory va Qdrant payload; khong tu tao migration neu schema chua co cot/JSONB.
item_path giu marker va nhan ngan tu dong item goc, vi du ["1. Ho so gom:", "a) Don dang ky."].
Khong chi luu ["1.", "a)"] va khong sao chep toan bo noi dung dai cua item cha vao item_path.
```

`RecursiveCharacterTextSplitter` chỉ dùng khi một item/paragraph quá dài. Table và code dùng splitter riêng:

```text
child_chunk_size = 1000 characters
child_chunk_overlap = 100 characters
```

Hai giá trị này lấy từ runtime settings (xem `21_RUNTIME_SETTINGS_GUIDE.md`). Default nằm trong settings model, không dùng fallback kiểu `settings.value or 1000`.

Không nên đưa raw LangChain Document ra ngoài chunker. Output public là `ChunkingResult`.

Với bảng Markdown:

```text
Table phai duoc detect truoc item regex.
Table nho giu nguyen.
Table lon split theo row group va lap lai header.
```

### 6.7. LangChain structural parser

Suggested design:

```text
1. split_body_by_page_markers() de co PageBlock.
2. parse_page_blocks() theo thu tu: page marker da consume, code, table, heading, item, paragraph.
3. Dùng mọi Markdown heading block để tạo parent sections.
4. Rebuild heading_path từ heading blocks; nội dung trước heading đầu tiên dùng `["document-root"]`.
5. Từ section tạo parent Chunk với stable chunk_key.
6. Từ structural item/table/code/paragraph tạo ChildUnit.
7. Paragraph sau item gan vao Child hien tai; paragraph khong thuoc item nao tao paragraph Child.
8. Nếu item/paragraph ChildUnit quá dài, dùng RecursiveCharacterTextSplitter bên trong chính unit đó.
9. Table dài split theo row group và lặp header + separator; code dài split theo ranh giới dòng, mỗi split giữ opening/closing fence hợp lệ.
10. Mọi split giữ logical_item_key/parent_item_key/item_path hoặc logical_table_key/logical_code_key cùng split_index/split_count.
11. Từ ChildUnit tạo child Chunk với parent_chunk_key là stable key của parent.
12. Page marker va HTML comment ky thuat khong dua vao embedding text.
```

Import dùng:

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

### 6.8. chunk_key Đề Xuất

Stable format:

```text
<version_key>::p::<parent_index>
<version_key>::c::<child_index>
```

Ví dụ:

```text
qd3266-2024::p::0001
qd3266-2024::c::0001
```

Dùng zero padding để sort dễ đọc.

Lưu ý:

```text
Đây là stable key trong memory/preview/DB/Qdrant.
Sau khi repository insert DB, DocumentChunk.id chỉ dùng làm postgres_chunk_id nội bộ.
chunk_index trong DB phải tăng global cho cả parent và child chunks, không reset theo từng loại.
```

### 6.9. token_count MVP

Nếu chưa có tokenizer:

```python
token_count = len(content.split())
```

Đây là word count gần đúng, đủ cho MVP preview. Sau này mới đổi sang tokenizer theo model embedding.

### 6.10. Test Cần Có

```text
test_chunker_creates_parent_and_child
test_chunker_sets_parent_chunk_id_for_child
test_chunker_tracks_heading_path
test_chunker_tracks_page_range
test_chunker_rejects_empty_body
test_chunker_does_not_split_simple_table
```

---

## 7. Phần D - Chunk Preview

### 7.1. File Nên Tạo

```text
chatbot/backend/app/ingestion/preview.py
chatbot/backend/test/ingestion/test_preview.py
```

### 7.2. Mục Tiêu

Preview giúp kiểm tra chunk trước khi ghi database:

```text
metadata ok?
số chunk hợp lý?
heading_path đúng?
page_start/page_end đúng?
content có bị mất không?
table có bị vỡ không?
```

### 7.3. Output Preview Đề Xuất

JSON:

```json
{
  "document_key": "qd3266-hoc-vu",
  "version_key": "qd3266-2024",
  "total_chunks": 12,
  "parents": 4,
  "children": 8,
  "chunks": [
    {
      "chunk_key": "qd3266-2024::c::0001",
      "parent_chunk_key": "qd3266-2024::p::0001",
      "chunk_type": "child",
      "heading_path": ["Quy dinh", "Chuong I", "Dieu 1"],
      "page_start": 1,
      "page_end": 1,
      "token_count": 210,
      "content_preview": "..."
    }
  ]
}
```

### 7.4. CLI Đề Xuất

Có thể thêm command tạm thời:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -m app.ingestion.preview "..\..\nlcs\06_Processing\03_Markdown_Cleaning\PDFs_CTSV\Noi_quy_KTX_nam_2016_structured.md"
```

Nếu chưa muốn làm CLI, chỉ cần function:

```python
def build_chunk_preview(markdown_path: Path) -> dict:
    ...
```

### 7.5. Done khi

```text
Preview được 1 file CTSV.
Preview được 1 file PDT.
Không có chunk rỗng.
Không có child thiếu parent.
Không có page_start > page_end.
```

---

## 8. Phần E - PostgreSQL Ingestion Repository

### 8.1. File Nên Tạo

```text
chatbot/backend/app/ingestion/repository.py
chatbot/backend/test/ingestion/test_ingestion_repository.py
```

### 8.2. Trách Nhiệm

Repository chỉ làm việc với DB:

```text
upsert department
upsert document_type
upsert document
upsert document_version (status fields nằm trực tiếp trên version)
insert/update document_chunks
insert ingestion_job
```

Không parse Markdown, không chunk, không embed trong repository.

### 8.3. Department mapping

Metadata YAML/schema có:

```text
responsible_department: list[str]
```

DB cần:

```text
departments.code
departments.name
document_recipients(document_version_id, department_id, effective_date)
```

MVP mapping:

```text
Với từng item trong `responsible_department`:

Nếu item = "CTSV" hoặc "Phong Cong tac Sinh vien":
  code = "CTSV"
  name = original item or "Phong Cong tac Sinh vien"

Nếu item = "PDT" hoặc "Phong Dao tao":
  code = "PDT"
  name = original item or "Phong Dao tao"

Nếu rỗng:
  bỏ qua hoặc dùng fallback "UNKNOWN" theo policy ingestion
```

Không để `code` dài hơn 20 ký tự vì model đang `String(20)`.

### 8.4. Document type mapping

Metadata:

```text
document_type = noi_quy | quy_trinh | bieu_mau | hoi_dap | unknown
```

DB:

```text
document_types.code = document_type
document_types.name = label dễ đọc
```

Ví dụ:

```text
code = "quy_trinh"
name = "Quy trinh"
```

### 8.5. Upsert document

Key:

```text
documents.document_key
```

Nếu tồn tại:

```text
update title/domain/audience/department_id/document_type_id nếu cần
```

Nếu chưa tồn tại:

```text
insert mới
```

### 8.6. Upsert document_version

Key:

```text
document_versions.version_key
```

Nếu tồn tại:

```text
update metadata version nếu checksum/metadata_hash thay đổi
```

Nếu chưa tồn tại:

```text
insert mới
```

Cần cảnh báo nếu:

```text
version_key tồn tại nhưng document_key khác
```

Đây là lỗi nghiêm trọng, nên raise.

### 8.7. Status update

Không nên set `published` vào DB trước khi Qdrant upsert thành công.

Suggested workflow:

```text
metadata.rag_status = published  # y dinh publish tu YAML

DB status during chunk save:
  rag_status = chunked

After embedding:
  rag_status = embedded

After Qdrant upsert:
  rag_status = published

On failure:
  rag_status = failed
```

Nếu đang ingest expired/internal:

```text
final rag_status = indexed
```

### 8.8. Insert chunks

Thứ tự:

```text
1. Delete old chunks của document_version hoặc mark inactive.
2. Insert parent chunks trước.
3. Build map chunk_key -> database id.
4. Insert child chunks với parent_chunk_id từ map.
```

MVP có thể delete old chunks trước khi insert lại, vì document version là snapshot.

Lưu ý:

```text
Nếu Qdrant đã có old vectors, cần delete/deactivate Qdrant points trước khi replace chunks.
Nếu chưa implement delete Qdrant, chưa nên ingest lại cùng version vào data thật.
```

### 8.9. Done khi

```text
Một MarkdownDocument + list[Chunk] ghi được vào PostgreSQL.
Query lại thấy document/version/status/chunks.
Child chunk có parent_chunk_id đúng.
```

---

## 9. Phần F - Pipeline Orchestration

### 9.1. File Nên Sửa

```text
chatbot/backend/app/ingestion/pipeline.py
```

### 9.2. Pipeline Không Nên Phình To

`pipeline.py` chỉ điều phối:

```text
read markdown
chunk markdown
save metadata/chunks
embed child chunks
upsert qdrant
update status/job
```

Logic từng phần nằm ở module riêng:

```text
markdown_reader.py
chunker.py
repository.py
embedder.py
vectorstore/repository.py
```

### 9.3. Suggested public API

```python
async def ingest_markdown_file(path: Path, *, publish: bool = False) -> IngestionResult:
    ...
```

Trong đó:

```text
publish=False: chỉ validate + chunk + save DB, không upsert Qdrant
publish=True: chạy embed + upsert Qdrant nếu metadata cho phép
```

### 9.4. IngestionResult

Suggested pattern:

```python
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

### 9.5. Error handling

Nếu lỗi ở bất kỳ stage nào:

```text
ingestion_jobs.status = failed
ingestion_jobs.current_step = step đang lỗi
ingestion_jobs.error_message = message ngắn
document_versions.rag_status = failed
```

Không swallow exception trong MVP. Log rồi raise để test thấy lỗi.

---

## 10. Phần G - Embedding

### 10.1. File Nên Tạo/Sửa

```text
chatbot/backend/app/embedding/embedder.py
chatbot/backend/app/embedding/__init__.py
chatbot/backend/test/embedding/test_embedder.py
```

Có thể giữ file cũ:

```text
chatbot/backend/app/embedding/embeder.py
```

với nội dung wrapper:

```python
from app.embedding.embedder import *  # noqa: F401,F403
```

### 10.2. Model

Quyết định hiện tại:

```text
BAAI/bge-m3
```

Vector dimension thường dùng:

```text
1024
```

Nếu dùng model khác, Qdrant collection dimension phải đổi theo.

### 10.3. Input text cho embedding

Không embed raw content mới. Nên thêm context ngắn:

```text
Tai lieu: <title>
Don vi: <department>
Loai: <document_type>
Muc: <heading_path joined by " > ">
Trang: <page_start>-<page_end>

<chunk content>
```

Lý do:

```text
Chunk ngắn có thêm context sẽ search tốt hơn.
Citation vẫn lấy từ payload, không dựa vào text embed.
```

### 10.4. API Đề Xuất

```python
class Embedder:
    model_name: str = "BAAI/bge-m3"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...
```

### 10.5. Test

Unit test không nên tải model thật vì chậm.

Dùng fake embedder:

```python
class FakeEmbedder:
    def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]
```

Integration embedding thật có thể để riêng và skip mặc định:

```python
@pytest.mark.integration
```

---

## 11. Phần H - Qdrant Client Và Repository

### 11.1. File Nên Tạo/Sửa

```text
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/test/vectorstore/test_qdrant_repository.py
```

### 11.2. Collection

Tên collection đề xuất:

```text
css_qdrant
```

Config:

```text
vector_size = 1024
distance = cosine
```

### 11.3. Point ID

Qdrant point ID nên ổn định.

Khuyến nghị:

```text
point_id = uuid5(NAMESPACE_URL, str(document_chunks.id))
```

Lý do:

```text
Qdrant chấp nhận UUID string.
Upsert cùng DB chunk id sẽ dễ dàng idempotent.
```

Không dùng random UUID vì ingest lại sẽ tạo duplicate point.

### 11.4. Payload model

Suggested pattern:

```python
class VectorPayload(TypedDict):
    document_key: str
    version_key: str
    chunk_key: str
    parent_chunk_key: str | None
    postgres_chunk_id: int
    chunk_type: str
    document_type: str
    domain: str
    audience: list[str]
    review_status: str
    rag_status: str
    is_latest: bool
    page_start: int | None
    page_end: int | None
```

### 11.5. Upsert flow

```text
1. Ensure collection exists.
2. Build points từ child chunks đã embed.
3. Upsert points.
4. Update document_chunks.qdrant_point_id.
5. Update document_chunks.index_status = indexed.
6. Update document_versions.rag_status = published hoặc indexed.
```

### 11.6. Filter cho student search

Qdrant filter bắt buộc:

```text
review_status = approved
rag_status = published
audience contains student
```

Nếu Qdrant filter array contains phức tạp lúc đầu, có thể thêm payload:

```text
audience_student = true
```

Nhưng vẫn giữ `audience` list để trace.

### 11.7. Test

Unit test:

```text
test_point_id_is_stable
test_payload_contains_required_trace_fields
test_student_filter_contains_required_statuses
```

Integration test Qdrant:

```text
test_upsert_and_search_test_collection
```

Chỉ chạy khi Qdrant container đang chạy.

---

## 12. Phần I - Retrieval Tối Thiểu

### 12.1. File Nên Sửa

```text
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/test/retrieval/test_retriever.py
```

### 12.2. Input Và Output

Input:

```text
query: str
audience: "student"
top_k: int | None = None  # None => settings.retrieval.top_k
```

`top_k` lấy từ runtime settings (default `retrieval.top_k = 5`). Không dùng fallback kiểu `settings.retrieval.top_k or 5`.

Output:

```python
@dataclass(frozen=True)
class RetrievalResult:
    chunk_key: str
    score: float
    content: str
    title: str
    page_start: int | None
    page_end: int | None
    source_file: str
    source_url: str
```

### 12.3. Retrieval flow

```text
1. Embed query.
2. Search Qdrant với student filter.
3. Lấy content từ payload nếu payload có content preview/full content.
4. Tốt hơn: lấy postgres_chunk_id từ payload, query PostgreSQL để lấy full content.
5. Return result có citation.
```

MVP có thể để content trong payload để search smoke test nhanh.

Nhưng về lâu dài:

```text
Qdrant payload không nên là nơi lưu full content chính.
PostgreSQL document_chunks.content mới là canonical chunk content.
```

### 12.4. Citation format

MVP:

```text
<source_file>, trang <page_start>-<page_end>
```

Nếu `page_start` rỗng:

```text
<source_file>, mục <heading_path last item>
```

### 12.5. Test Quan Trọng

```text
test_student_retriever_filters_unpublished_documents
test_student_retriever_filters_expired_documents
test_retriever_returns_citation_fields
test_retriever_returns_empty_list_for_blank_query
```

---

## 13. Phần J - Test Và Smoke Test End-To-End

### 13.1. Test tree đề xuất

```text
chatbot/backend/test/ingestion/
  test_markdown_reader.py
  test_chunker.py
  test_preview.py
  test_ingestion_repository.py
  test_pipeline.py

chatbot/backend/test/embedding/
  test_embedder.py

chatbot/backend/test/vectorstore/
  test_qdrant_repository.py

chatbot/backend/test/retrieval/
  test_retriever.py
```

### 13.2. Không Cần Service Ngoài

Nên chạy nhanh:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -m pytest test/schemas test/ingestion/test_markdown_reader.py test/ingestion/test_chunker.py
```

### 13.3. DB integration tests

Chỉ chạy khi `DATABASE_URL` trỏ vào DB test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/databases test/ingestion/test_ingestion_repository.py
```

### 13.4. Qdrant integration tests

Chỉ chạy khi Qdrant đang chạy:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
docker compose up -d qdrant
```

Sau đó:

```powershell
cd backend
..\..\.venv\Scripts\python.exe -m pytest test/vectorstore -m integration
```

### 13.5. Thủ Công

```text
1. Start PostgreSQL và Qdrant.
2. Set DATABASE_URL sang DB test hoặc dev tùy mục đích.
3. Chạy migration.
4. Preview chunk một Markdown file.
5. Ingest file vào PostgreSQL.
6. Embed child chunks.
7. Upsert Qdrant.
8. Search query thử.
9. Kiểm tra citation.
```

Query test nên gần với nội dung tài liệu thật, ví dụ:

```text
"sinh viên cần làm gì để cấp bằng điểm"
"nội quy ký túc xá quy định về thời gian nào"
"vay vốn sinh viên STEM cần điều kiện gì"
```

---

## 14. Thứ Tự Implement Khuyến Nghị

Không code tất cả cùng lúc. Làm theo thứ tự:

```text
1. Fix DB/schema contract: stable chunk_key, parent_chunk_id FK, nullable, updated_at.
2. Add dependencies tối thiểu: PyYAML.
3. Implement markdown_reader.py + tests.
4. Implement chunker.py + tests.
5. Implement preview.py.
6. Implement ingestion repository save metadata/chunks.
7. Implement pipeline.py với mode publish=False.
8. Add embedder.py + fake embedder tests.
9. Add qdrant repository + mocked tests.
10. Implement pipeline publish=True.
11. Implement retriever.py.
12. Chạy smoke test end-to-end.
```

Nếu bước 3 hoặc 4 chưa pass, không nên bắt đầu embedding/Qdrant.

---

## 15. Checklist Hoàn Thành Guide 07

- [ ] `DocumentChunk.chunk_key` được chốt làm stable chunk key.
- [ ] Migration và DB smoke test pass.
- [ ] Markdown reader validate được frontmatter.
- [ ] Chunker tạo parent/child chunks hợp lệ.
- [ ] Preview hiện chunk rõ ràng trước khi ghi DB.
- [ ] Ingestion repository upsert document/version/status/chunks.
- [ ] Pipeline `publish=False` chạy được.
- [ ] Embedder có fake test và integration path cho BGE-M3.
- [ ] Qdrant repository có stable point id.
- [ ] Pipeline `publish=True` upsert được Qdrant.
- [ ] Retriever student filter đúng status.
- [ ] Smoke test trả về citation đúng file/trang.

---

## 16. Các Lỗi Dễ Gặp

### Lỗi 1: YAML field dùng tên cũ

Triệu chứng:

```text
ValidationError: document_key field required
```

Nguyên nhân:

```text
File Markdown vẫn dùng document_id/version_id.
```

Xử lý:

```text
Chuẩn hóa sang document_key/version_key.
Không thêm alias ngầm nếu chưa cần migration metadata cũ.
```

### Lỗi 2: Child chunk không có parent

Triệu chứng:

```text
ValidationError: child chunk requires parent_chunk_key
```

Nguyên nhân:

```text
Chunker tạo child trước parent hoặc section parser không tạo default parent.
```

Xử lý:

```text
Nếu tài liệu không có heading, tạo parent "Document" trước.
```

### Lỗi 3: Duplicate chunks khi ingest lại

Triệu chứng:

```text
UniqueConstraint document_version_id/chunk_index
```

Nguyên nhân:

```text
Ingest lại cùng version nhưng không xóa/update chunks cũ.
```

Xử lý MVP:

```text
Trong transaction, delete chunks cũ của document_version trước khi insert chunks mới.
```

Sau MVP:

```text
So sánh checksum và update diff.
```

### Lỗi 4: Qdrant duplicate points

Triệu chứng:

```text
Search trả về nhiều kết quả trùng nội dung.
```

Nguyên nhân:

```text
Point ID random mỗi lần ingest.
```

Xử lý:

```text
Dùng uuid5 từ DocumentChunk.id để point ID ổn định.
```

### Lỗi 5: Student retrieval lấy tài liệu expired

Nguyên nhân:

```text
Chỉ filter lúc ingestion, không filter lúc retrieval.
```

Xử lý:

```text
Thêm hard filter trong retriever.py và test riêng.
```

---

## 17. File Nên Đọc Lại Trước Khi Code

```text
chatbot/.docs/guild_implement/01_RAG_SCHEMA_IMPLEMENTATION_GUIDE.md
chatbot/.docs/guild_implement/03_SQLALCHEMY_9_TABLES_GUIDE.md
chatbot/.docs/guild_implement/05_DATABASE_TEST_AND_SMOKE_INSERT_GUIDE.md
chatbot/.docs/guild_implement/06_GiaiDoanTiepTheo.md
chatbot/backend/app/schemas/documents.py
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/databases/models/documents.py
chatbot/backend/app/databases/models/chunks.py
chatbot/backend/test/databases/test_database_models.py
```

Guide 07 không thay thế các guide trước. Nó chỉ biến mục tiêu của guide 06 thành các phần implementation có thể code và test lần lượt.

## 17. Final Structural Reconciliation

Các guide 09A, 10A, 10B, 10, 13, 14, 15, 16 và 17 phải tuân theo contract cuối tại
`22_CHUNKING_RETRIEVAL_RECONCILIATION_GUIDE.md`. Nếu pseudocode cũ mâu thuẫn, contract 22 ưu tiên.

Các điểm P0:

```text
- Page marker được consume và không nằm trong PageBlock.content.
- Mỗi heading mở Parent mới; không merge qua heading boundary.
- Heading-only content không bị mất embedding.
- Table/code là atomic Child riêng.
- legal_unit_type chỉ gán trong legal context.
- warning không block publish; error mới block mặc định.
- Chunk.metadata trong memory không đồng nghĩa đã persist PostgreSQL.
- Qdrant payload có structural fields để retrieval expansion.
- Retrieval có parent/child/sibling/split expansion trước rerank/context budget.
```
