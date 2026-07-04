# 07. Huong Dan Chi Tiet Implement Markdown Ingestion, Chunking, Embedding, Qdrant

**Last Updated:** 2026-06-20

File nay noi tiep sau:

```text
06_GiaiDoanTiepTheo.md
```

Guide 06 mo ta buc tranh tong quat. Guide 07 di vao tung phan can implement trong backend de co mot vertical slice RAG chay duoc:

```text
Markdown canonical
-> validate YAML metadata
-> tao parent/child chunks
-> preview chunks
-> luu PostgreSQL
-> embed child chunks
-> upsert Qdrant
-> retrieval co citation
```

Khong lam frontend, HNSW tuning, reranking nang cao, hoac prompt QA phuc tap trong guide nay.

---

## 0. Trang Thai Hien Tai

Da co:

```text
chatbot/backend/app/schemas/documents.py
chatbot/backend/app/schemas/assets.py
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/schemas/enums.py
chatbot/backend/app/databases/models/
chatbot/backend/test/schemas/
chatbot/backend/test/databases/test_database_models.py
```

Dang con trong hoac chua co logic:

```text
chatbot/backend/app/ingestion/pipeline.py
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/embedding/embeder.py
```

Ghi chu:

```text
app/embedding/embeder.py dang bi dat ten thieu "d".
Khi implement nen tao app/embedding/embedder.py cho ten dung.
Neu can giu backward compatibility, de embeder.py re-export tu embedder.py sau.
```

---

## 1. Muc Tieu Cua Guide 07

Sau guide nay can dat duoc:

```text
1. Metadata Markdown doc duoc validate bang DocumentMetadata.
2. Chunker tao duoc Chunk schema hop le.
3. Co preview chunk truoc khi ghi database.
4. Ingest duoc mot file Markdown vao PostgreSQL.
5. Embed duoc child chunks bang BAAI/bge-m3.
6. Upsert duoc vectors vao Qdrant.
7. Search tra ve content + payload + citation.
8. Test khong cho student retrieval lay tai lieu chua publish.
```

MVP chi can chay tot voi 1-2 file that trong:

```text
nlcs/06_Processing/03_Markdown_Cleaning/
```

Sau do moi mo rong sang:

```text
nlcs/01_Dataset/
```

---

## 2. Nguyen Tac Bat Buoc

### 2.1. PostgreSQL la metadata source of truth

```text
PostgreSQL luu document/version/status/chunks/job.
Qdrant chi luu vector + payload de search nhanh.
```

Khong dung Qdrant de thay the PostgreSQL.

### 2.2. Qdrant point phai trace nguoc duoc PostgreSQL

Payload Qdrant toi thieu phai co:

```text
document_key
version_key
chunk_key              # stable schema/vector key
parent_chunk_key       # stable parent key neu co
postgres_chunk_id     # int DocumentChunk.id de hydrate tu PostgreSQL
title
page_start
page_end
source_file
```

### 2.3. Chi embed child chunk trong MVP

Parent chunk dung de giu ngu canh va quan he section.

MVP:

```text
parent chunk: luu PostgreSQL, khong embed
child chunk: luu PostgreSQL, embed, upsert Qdrant
```

### 2.4. Student retrieval phai filter cung

Filter student:

```text
review_status = approved
rag_status = published
audience contains student
```

Khong chi dua vao viec ingestion da loc. Retriever van phai loc lai.

---

## 3. Dependency Can Co

File:

```text
chatbot/backend/requirements.txt
```

Nen bo sung khi bat dau implement:

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

Neu chua dung Qdrant/embedding that trong unit test, co the mock de test logic ingestion truoc.

---

## 4. Phan A - Chot Lai Contract DB/Schema Truoc Khi Ingest

Lam phan nay truoc khi viet reader/chunker.

### 4.1. File can kiem tra

```text
chatbot/backend/app/schemas/chunks.py
chatbot/backend/app/databases/models/chunks.py
chatbot/backend/alembic/versions/
chatbot/backend/test/databases/test_database_models.py
```

### 4.2. Van de can xu ly som

Pydantic `Chunk` dang co:

```text
chunk_key
parent_chunk_key
chunk_type
```

DB `document_chunks` phai co cot stable `chunk_key`. Contract toi thieu:

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

Quyet dinh:

```text
Dung Chunk.chunk_key lam stable key tu schema/preview/toi Qdrant.
Luu chunk_key trong document_chunks.
Dung DocumentChunk.id rieng lam postgres_chunk_id/internal id.
```

### 4.3. Quyet dinh de xuat

Them cot `chunk_key` vao `DocumentChunk`.

Dung mapping trong repository:

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

Ly do:

```text
PostgreSQL la source of truth.
chunk_key giup idempotent ingest va trace on dinh.
postgres_chunk_id giup hydrate nhanh tu PostgreSQL khi retrieve.
```

Khong dung `qdrant_point_id` thay cho `chunk_key`, vi point id la chi tiet cua vector store.

### 4.4. Nullable can dong bo

Neu schema Pydantic cho phep `None`, DB/migration cung nen cho phep nullable:

```text
DocumentVersion.issued_date
DocumentVersion.accessed_date
DocumentChunk.page_start
DocumentChunk.page_end
DocumentChunk.token_count
```

Neu DB bat buoc non-null, chunker phai luon gan gia tri fallback. Khuyen nghi MVP:

```text
Cho phep NULL, log warning neu khong co page marker.
```

### 4.5. Done khi

```text
pytest test/schemas test/databases
```

pass, va migration test database chay sach.

---

## 5. Phan B - Markdown Reader

### 5.1. File nen tao

```text
chatbot/backend/app/ingestion/markdown_reader.py
chatbot/backend/test/ingestion/test_markdown_reader.py
```

### 5.2. Trach nhiem

Markdown reader chi lam 4 viec:

```text
1. Doc file .md.
2. Tach YAML frontmatter va Markdown body.
3. Parse YAML bang yaml.safe_load.
4. Validate metadata bang DocumentMetadata.
```

Khong chunk, khong ghi DB, khong embed trong reader.

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

### 5.4. Tach frontmatter

Accepted format:

```markdown
---
document_key: "..."
version_key: "..."
---

# Noi dung
```

Rule:

```text
File phai bat dau bang ---
Frontmatter ket thuc bang dong ---
Body khong duoc rong
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

Neu file dung CRLF, normalize truoc:

```python
text = text.replace("\r\n", "\n")
```

### 5.5. Check checksum

Co 2 cach:

```text
Cach A: checksum la metadata bat buoc do nguoi tao file dien.
Cach B: pipeline tinh checksum body va compare voi metadata neu co.
```

MVP nen lam:

```text
Neu checksum rong -> reject, vi DocumentMetadata dang bat buoc checksum.
Chua can compare content hash trong buoc dau.
```

Sau MVP co the them:

```text
metadata_hash = sha256(frontmatter normalized)
content_checksum = sha256(body)
```

### 5.6. Test can co

```text
test_read_markdown_with_valid_frontmatter
test_reader_rejects_missing_frontmatter
test_reader_rejects_invalid_yaml_mapping
test_reader_rejects_empty_body
test_reader_rejects_published_invalid_status
```

---

## 6. Phan C - Heading-Aware Chunker

### 6.1. File nen tao

```text
chatbot/backend/app/ingestion/chunker.py
chatbot/backend/test/ingestion/test_chunker.py
```

### 6.2. Input va output

Input:

```text
DocumentMetadata
Markdown body
```

Output:

```text
list[Chunk]
```

Dung schema hien co:

```python
from app.schemas.chunks import Chunk
```

### 6.3. Markdown pattern can nhan dien

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

Bang Markdown:

```markdown
| Cot A | Cot B |
|---|---|
| A | B |
```

### 6.4. Quy tac heading_path

Khi gap heading:

```text
#      -> level 1
##     -> level 2
###    -> level 3
####   -> level 4
```

Cap nhat stack:

```text
current_heading_path = headings tu level 1 den level hien tai
```

Vi du:

```text
# Quy dinh hoc vu
## Chuong II
### Dieu 5
```

Chunk ben trong `Dieu 5` co:

```python
heading_path = ["Quy dinh hoc vu", "Chuong II", "Dieu 5"]
```

### 6.5. Quy tac parent chunk

MVP de xuat:

```text
Moi section tu heading level 2 hoac 3 tao mot parent chunk.
Neu tai lieu khong co heading, tao parent "Document".
```

Parent chunk:

```text
chunk_type = "parent"
parent_chunk_key = None
content = toan bo section hoac summary raw cua section
```

Neu parent qua dai, van co the luu content day du trong PostgreSQL. Khong embed parent trong MVP.

### 6.6. Quy tac child chunk

Child chunk duoc cat tu content cua parent.

MVP dung `RecursiveCharacterTextSplitter` tu `langchain-text-splitters`:

```text
child_chunk_size = 1800 characters
child_chunk_overlap = 200 characters
```

Khong nen dua raw LangChain Document ra ngoai chunker. Output public van la `list[Chunk]`.

Voi bang Markdown:

```text
MVP uu tien child_chunk_size du lon de table nho khong bi cat.
Neu table lon bi cat, them table-protection sau khi co test rieng.
```

### 6.7. LangChain structural parser

Suggested design:

```text
1. Dung MarkdownHeaderTextSplitter de tach body thanh parent sections.
2. Dung strip_headers=False de giu heading trong content.
3. Rebuild heading_path tu metadata h1/h2/h3.
4. Lay page_start/page_end bang regex tu page marker trong section text.
5. Tu section tao parent Chunk voi stable chunk_key.
6. Dung RecursiveCharacterTextSplitter cat section thanh child texts.
7. Tu child text tao child Chunk voi parent_chunk_key la stable key cua parent.
```

Import dung:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
```

### 6.8. chunk_key de xuat

Stable format:

```text
<version_key>::p::<parent_index>
<version_key>::c::<child_index>
```

Vi du:

```text
qd3266-2024::p::0001
qd3266-2024::c::0001
```

Dung zero padding de sort de doc.

Luu y:

```text
Day la stable key trong memory/preview/DB/Qdrant.
Sau khi repository insert DB, DocumentChunk.id chi dung lam postgres_chunk_id noi bo.
chunk_index trong DB phai tang global cho ca parent va child chunks, khong reset theo tung loai.
```

### 6.9. token_count MVP

Neu chua co tokenizer:

```python
token_count = len(content.split())
```

Day la word count gan dung, du cho MVP preview. Sau nay moi doi sang tokenizer theo model embedding.

### 6.10. Test can co

```text
test_chunker_creates_parent_and_child
test_chunker_sets_parent_chunk_id_for_child
test_chunker_tracks_heading_path
test_chunker_tracks_page_range
test_chunker_rejects_empty_body
test_chunker_does_not_split_simple_table
```

---

## 7. Phan D - Chunk Preview

### 7.1. File nen tao

```text
chatbot/backend/app/ingestion/preview.py
chatbot/backend/test/ingestion/test_preview.py
```

### 7.2. Muc tieu

Preview giup kiem tra chunk truoc khi ghi database:

```text
metadata ok?
so chunk hop ly?
heading_path dung?
page_start/page_end dung?
content co bi mat khong?
table co bi vo khong?
```

### 7.3. Output preview de xuat

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

### 7.4. CLI de xuat

Co the them command tam thoi:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -m app.ingestion.preview "..\..\nlcs\06_Processing\03_Markdown_Cleaning\PDFs_CTSV\Noi_quy_KTX_nam_2016_structured.md"
```

Neu chua muon lam CLI, chi can function:

```python
def build_chunk_preview(markdown_path: Path) -> dict:
    ...
```

### 7.5. Done khi

```text
Preview duoc 1 file CTSV.
Preview duoc 1 file PDT.
Khong co chunk rong.
Khong co child thieu parent.
Khong co page_start > page_end.
```

---

## 8. Phan E - PostgreSQL Ingestion Repository

### 8.1. File nen tao

```text
chatbot/backend/app/ingestion/repository.py
chatbot/backend/test/ingestion/test_ingestion_repository.py
```

### 8.2. Trach nhiem

Repository chi lam viec voi DB:

```text
upsert department
upsert document_type
upsert document
upsert document_version (status fields nam truc tiep tren version)
insert/update document_chunks
insert ingestion_job
```

Khong parse Markdown, khong chunk, khong embed trong repository.

### 8.3. Department mapping

Metadata hien co co:

```text
department: str
```

DB can:

```text
departments.code
departments.name
```

MVP mapping:

```text
Neu department = "CTSV" hoac "Phong Cong tac Sinh vien":
  code = "CTSV"
  name = original department or "Phong Cong tac Sinh vien"

Neu department = "PDT" hoac "Phong Dao tao":
  code = "PDT"
  name = original department or "Phong Dao tao"

Neu rong:
  code = "UNKNOWN"
  name = "Unknown"
```

Khong de `code` dai hon 20 ky tu vi model dang `String(20)`.

### 8.4. Document type mapping

Metadata:

```text
document_type = noi_quy | quy_trinh | bieu_mau | hoi_dap | unknown
```

DB:

```text
document_types.code = document_type
document_types.name = label de doc
```

Vi du:

```text
code = "quy_trinh"
name = "Quy trinh"
```

### 8.5. Upsert document

Key:

```text
documents.document_key
```

Neu ton tai:

```text
update title/domain/audience/department_id/document_type_id neu can
```

Neu chua ton tai:

```text
insert moi
```

### 8.6. Upsert document_version

Key:

```text
document_versions.version_key
```

Neu ton tai:

```text
update metadata version neu checksum/metadata_hash thay doi
```

Neu chua ton tai:

```text
insert moi
```

Can canh bao neu:

```text
version_key ton tai nhung document_key khac
```

Day la loi nghiem trong, nen raise.

### 8.7. Status update

Khong nen set `published` vao DB truoc khi Qdrant upsert thanh cong.

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

Neu dang ingest expired/internal:

```text
final rag_status = indexed
```

### 8.8. Insert chunks

Thu tu:

```text
1. Delete old chunks cua document_version hoac mark inactive.
2. Insert parent chunks truoc.
3. Build map chunk_key -> database id.
4. Insert child chunks voi parent_chunk_id tu map.
```

MVP co the delete old chunks truoc khi insert lai, vi document version la snapshot.

Luu y:

```text
Neu Qdrant da co old vectors, can delete/deactivate Qdrant points truoc khi replace chunks.
Neu chua implement delete Qdrant, chua nen ingest lai cung version vao data that.
```

### 8.9. Done khi

```text
Mot MarkdownDocument + list[Chunk] ghi duoc vao PostgreSQL.
Query lai thay document/version/status/chunks.
Child chunk co parent_chunk_id dung.
```

---

## 9. Phan F - Pipeline Orchestration

### 9.1. File nen sua

```text
chatbot/backend/app/ingestion/pipeline.py
```

### 9.2. Pipeline khong nen phinh to

`pipeline.py` chi dieu phoi:

```text
read markdown
chunk markdown
save metadata/chunks
embed child chunks
upsert qdrant
update status/job
```

Logic tung phan nam o module rieng:

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

Trong do:

```text
publish=False: chi validate + chunk + save DB, khong upsert Qdrant
publish=True: chay embed + upsert Qdrant neu metadata cho phep
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

Neu loi o bat ky stage nao:

```text
ingestion_jobs.status = failed
ingestion_jobs.current_step = step dang loi
ingestion_jobs.error_message = message ngan
document_versions.rag_status = failed
```

Khong swallow exception trong MVP. Log roi raise de test thay loi.

---

## 10. Phan G - Embedding

### 10.1. File nen tao/sua

```text
chatbot/backend/app/embedding/embedder.py
chatbot/backend/app/embedding/__init__.py
chatbot/backend/test/embedding/test_embedder.py
```

Co the giu file cu:

```text
chatbot/backend/app/embedding/embeder.py
```

voi noi dung wrapper:

```python
from app.embedding.embedder import *  # noqa: F401,F403
```

### 10.2. Model

Quyet dinh hien tai:

```text
BAAI/bge-m3
```

Vector dimension thuong dung:

```text
1024
```

Neu dung model khac, Qdrant collection dimension phai doi theo.

### 10.3. Input text cho embedding

Khong embed raw content moi. Nen them context ngan:

```text
Tai lieu: <title>
Don vi: <department>
Loai: <document_type>
Muc: <heading_path joined by " > ">
Trang: <page_start>-<page_end>

<chunk content>
```

Ly do:

```text
Chunk ngan co them context se search tot hon.
Citation van lay tu payload, khong dua vao text embed.
```

### 10.4. API de xuat

```python
class Embedder:
    model_name: str = "BAAI/bge-m3"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...
```

### 10.5. Test

Unit test khong nen tai model that vi cham.

Dung fake embedder:

```python
class FakeEmbedder:
    def embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]
```

Integration embedding that co the de rieng va skip mac dinh:

```python
@pytest.mark.integration
```

---

## 11. Phan H - Qdrant Client Va Repository

### 11.1. File nen tao/sua

```text
chatbot/backend/app/vectorstore/qdrant_client.py
chatbot/backend/app/vectorstore/models.py
chatbot/backend/app/vectorstore/repository.py
chatbot/backend/test/vectorstore/test_qdrant_repository.py
```

### 11.2. Collection

Ten collection de xuat:

```text
ctu_student_service_chunks
```

Config:

```text
vector_size = 1024
distance = cosine
```

### 11.3. Point ID

Qdrant point ID nen on dinh.

Khuyen nghi:

```text
point_id = uuid5(NAMESPACE_URL, str(document_chunks.id))
```

Ly do:

```text
Qdrant chap nhan UUID string.
Upsert cung DB chunk id se de dang idempotent.
```

Khong dung random UUID vi ingest lai se tao duplicate point.

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
2. Build points tu child chunks da embed.
3. Upsert points.
4. Update document_chunks.qdrant_point_id.
5. Update document_chunks.index_status = indexed.
6. Update document_versions.rag_status = published hoac indexed.
```

### 11.6. Filter cho student search

Qdrant filter bat buoc:

```text
review_status = approved
rag_status = published
audience contains student
```

Neu Qdrant filter array contains phuc tap luc dau, co the them payload:

```text
audience_student = true
```

Nhung van giu `audience` list de trace.

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

Chi chay khi Qdrant container dang chay.

---

## 12. Phan I - Retrieval Toi Thieu

### 12.1. File nen sua

```text
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/test/retrieval/test_retriever.py
```

### 12.2. Input va output

Input:

```text
query: str
audience: "student"
top_k: int = 5
```

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
2. Search Qdrant voi student filter.
3. Lay content tu payload neu payload co content preview/full content.
4. Tot hon: lay postgres_chunk_id tu payload, query PostgreSQL de lay full content.
5. Return result co citation.
```

MVP co the de content trong payload de search smoke test nhanh.

Nhung ve lau dai:

```text
Qdrant payload khong nen la noi luu full content chinh.
PostgreSQL document_chunks.content moi la canonical chunk content.
```

### 12.4. Citation format

MVP:

```text
<source_file>, trang <page_start>-<page_end>
```

Neu `page_start` rong:

```text
<source_file>, muc <heading_path last item>
```

### 12.5. Test quan trong

```text
test_student_retriever_filters_unpublished_documents
test_student_retriever_filters_expired_documents
test_retriever_returns_citation_fields
test_retriever_returns_empty_list_for_blank_query
```

---

## 13. Phan J - Test Va Smoke Test End-To-End

### 13.1. Test tree de xuat

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

### 13.2. Unit tests khong can service ngoai

Nen chay nhanh:

```powershell
cd chatbot/backend
..\..\.venv\Scripts\python.exe -m pytest test/schemas test/ingestion/test_markdown_reader.py test/ingestion/test_chunker.py
```

### 13.3. DB integration tests

Chi chay khi `DATABASE_URL` tro vao DB test:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/databases test/ingestion/test_ingestion_repository.py
```

### 13.4. Qdrant integration tests

Chi chay khi Qdrant dang chay:

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot
docker compose up -d qdrant
```

Sau do:

```powershell
cd backend
..\..\.venv\Scripts\python.exe -m pytest test/vectorstore -m integration
```

### 13.5. Smoke test thu cong

```text
1. Start PostgreSQL va Qdrant.
2. Set DATABASE_URL sang DB test hoac dev tuy muc dich.
3. Chay migration.
4. Preview chunk mot Markdown file.
5. Ingest file vao PostgreSQL.
6. Embed child chunks.
7. Upsert Qdrant.
8. Search query thu.
9. Kiem tra citation.
```

Query test nen gan voi noi dung tai lieu that, vi du:

```text
"sinh vien can lam gi de cap bang diem"
"noi quy ky tuc xa quy dinh ve thoi gian nao"
"vay von sinh vien STEM can dieu kien gi"
```

---

## 14. Thu Tu Implement Khuyen Nghi

Khong code tat ca cung luc. Lam theo thu tu:

```text
1. Fix DB/schema contract: stable chunk_key, parent_chunk_id FK, nullable, updated_at.
2. Add dependencies toi thieu: PyYAML.
3. Implement markdown_reader.py + tests.
4. Implement chunker.py + tests.
5. Implement preview.py.
6. Implement ingestion repository save metadata/chunks.
7. Implement pipeline.py voi mode publish=False.
8. Add embedder.py + fake embedder tests.
9. Add qdrant repository + mocked tests.
10. Implement pipeline publish=True.
11. Implement retriever.py.
12. Chay smoke test end-to-end.
```

Neu buoc 3 hoac 4 chua pass, khong nen bat dau embedding/Qdrant.

---

## 15. Checklist Hoan Thanh Guide 07

- [ ] `DocumentChunk.chunk_key` duoc chot lam stable chunk key.
- [ ] Migration va DB smoke test pass.
- [ ] Markdown reader validate duoc frontmatter.
- [ ] Chunker tao parent/child chunks hop le.
- [ ] Preview hien chunk ro rang truoc khi ghi DB.
- [ ] Ingestion repository upsert document/version/status/chunks.
- [ ] Pipeline `publish=False` chay duoc.
- [ ] Embedder co fake test va integration path cho BGE-M3.
- [ ] Qdrant repository co stable point id.
- [ ] Pipeline `publish=True` upsert duoc Qdrant.
- [ ] Retriever student filter dung status.
- [ ] Smoke test tra ve citation dung file/trang.

---

## 16. Cac Loi De Gap

### Loi 1: YAML field dung ten cu

Trieu chung:

```text
ValidationError: document_key field required
```

Nguyen nhan:

```text
File Markdown van dung document_id/version_id.
```

Xu ly:

```text
Chuan hoa sang document_key/version_key.
Khong them alias ngam neu chua can migration metadata cu.
```

### Loi 2: Child chunk khong co parent

Trieu chung:

```text
ValidationError: child chunk requires parent_chunk_key
```

Nguyen nhan:

```text
Chunker tao child truoc parent hoac section parser khong tao default parent.
```

Xu ly:

```text
Neu tai lieu khong co heading, tao parent "Document" truoc.
```

### Loi 3: Duplicate chunks khi ingest lai

Trieu chung:

```text
UniqueConstraint document_version_id/chunk_index
```

Nguyen nhan:

```text
Ingest lai cung version nhung khong xoa/update chunks cu.
```

Xu ly MVP:

```text
Trong transaction, delete chunks cu cua document_version truoc khi insert chunks moi.
```

Sau MVP:

```text
So sanh checksum va update diff.
```

### Loi 4: Qdrant duplicate points

Trieu chung:

```text
Search tra ve nhieu ket qua trung noi dung.
```

Nguyen nhan:

```text
Point ID random moi lan ingest.
```

Xu ly:

```text
Dung uuid5 tu DocumentChunk.id de point ID on dinh.
```

### Loi 5: Student retrieval lay tai lieu expired

Nguyen nhan:

```text
Chi filter luc ingestion, khong filter luc retrieval.
```

Xu ly:

```text
Them hard filter trong retriever.py va test rieng.
```

---

## 17. File Nen Doc Lai Truoc Khi Code

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

Guide 07 khong thay the cac guide truoc. No chi bien muc tieu cua guide 06 thanh cac phan implementation co the code va test lan luot.
