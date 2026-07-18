# chunk_note.md — Working Note: Chunking Pipeline

> **Nguồn chính thức:**
> - Schema chunk: `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`
> - RAG pipeline: `chatbot/.docs/spec/ctu-service/07_RAG_SPEC.md`
> - Retrieval guide: `chatbot/.docs/RAG_RETRIEVAL.md`

---

## Công cụ chunking

```text
MarkdownHeaderTextSplitter   → tạo parent chunks theo heading/section
RecursiveCharacterTextSplitter → cắt từng parent thành child chunks
```

Cả hai đều thuộc `langchain-text-splitters`. Không dùng công cụ chunking nào khác trong MVP.

---

## Luồng chunking

```text
Canonical Markdown
  ↓
MarkdownHeaderTextSplitter
  → parent chunks (theo heading/section)
  ↓
RecursiveCharacterTextSplitter
  → child chunks (300–600 tokens, overlap 50–100)
  ↓
Code gắn metadata:
  chunk_key, parent_chunk_id, parent_chunk_key
  chunk_index, chunk_type
  page_start, page_end
  heading_path, section_title
  document_version_id
  ↓
Insert vào document_chunks (PostgreSQL)
  ↓
Embed child chunks với BGE-M3
  ↓
Upsert Qdrant
```

---

## Fields chunk trong document_chunks

```text
id                  SERIAL PRIMARY KEY
parent_chunk_id     INTEGER REFERENCES document_chunks(id)   ← self-FK (NULL nếu là parent)
chunk_key           VARCHAR(255) NOT NULL
chunk_index         INTEGER NOT NULL
chunk_type          VARCHAR(20) NOT NULL    ← 'parent' | 'child'
section_title       TEXT
heading_path        TEXT
content             TEXT NOT NULL
page_start          INTEGER
page_end            INTEGER
token_count         INTEGER
checksum            VARCHAR(64)
qdrant_point_id     VARCHAR(255)
index_status        VARCHAR(50) DEFAULT 'not_indexed'
created_at          TIMESTAMP DEFAULT NOW()
updated_at          TIMESTAMP DEFAULT NOW()
document_version_id INTEGER REFERENCES document_versions(id)
```

> Không dùng `parent_id` — dùng `parent_chunk_id`.
> Không dùng `chunk_level` — dùng `chunk_type`.
> `chunk_key` phải unique per `document_version_id`.

---

## Chunk key format

```text
Parent: <version_key>::p::<index_4digits>
Child:  <version_key>::c::<index_4digits>

Ví dụ:
  quy-che-dao-tao-2024-v1::p::0001
  quy-che-dao-tao-2024-v1::c::0001
```

---

## Phân biệt parent / child

| | parent chunk | child chunk |
|---|---|---|
| `chunk_type` | `"parent"` | `"child"` |
| `parent_chunk_id` | NULL | ID của parent tương ứng |
| Dùng để embed? | Không | Có |
| Dùng để search Qdrant? | Không | Có |
| Dùng để expand context? | Có (khi tìm được child) | — |
| Kích thước gợi ý | 800–1500 tokens | 300–600 tokens |

---

## Qdrant payload cho child chunk

```json
{
  "chunk_key": "quy-che-dao-tao-2024-v1::c::0001",
  "parent_chunk_key": "quy-che-dao-tao-2024-v1::p::0001",
  "postgres_chunk_id": 123,
  "chunk_type": "child",
  "document_key": "quy-che-dao-tao-2024",
  "version_key": "quy-che-dao-tao-2024-v1",
  "review_status": "approved",
  "rag_status": "published",
  "is_latest": true,
  "page_start": 3,
  "page_end": 4
}
```

---

## Embedding cache logic

```text
L1:  load cache từ file JSON                     (chunk_key → vector)
L2:  khởi tạo vectors_by_key rỗng, missing_chunks rỗng
L3:  for mỗi chunk:
L4:    tạo enriched text
L5:    hash enriched text
L6:    tìm vector cũ theo chunk_key
L7:    nếu cache HIT  → dùng lại vector
L8:    nếu cache MISS → thêm vào missing_chunks
L9:  if missing_chunks không rỗng:
L10:   tạo list enriched text cho missing_chunks
L11:   gọi embed_texts() → BGE-M3
L12:   lưu vector mới vào cache
L13:   lưu cache xuống file JSON
L14: trả về list vector theo đúng thứ tự chunks đầu vào
```

> Embedding model: `BAAI/bge-m3`, 1024 dimensions, normalized.
> Chỉ embed `chunk_type = 'child'`. Không embed parent chunk ở giai đoạn đầu.

---

## Test load file markdown

```bash
# Basic
python -c "from app.ingestion.markdown_reader import read_markdown_document; doc = read_markdown_document('../test_doc.md'); print('PATH:', doc.path); print('TITLE:', doc.metadata.title); print('DOCUMENT_KEY:', doc.metadata.document_key); print('METADATA:', doc.metadata.model_dump()); print('BODY:'); print(doc.body)"

# Pretty print
python -c "from pprint import pprint; from app.ingestion.markdown_reader import read_markdown_document; doc = read_markdown_document('../test_doc.md'); print('PATH:', doc.path); print('TITLE:', doc.metadata.title); print('DOCUMENT_KEY:', doc.metadata.document_key); print('\nMETADATA:'); pprint(doc.metadata.model_dump(), sort_dicts=False); print('\nBODY:'); print(doc.body)"
```

---

## Quan hệ object trong code

```text
Pydantic Chunk
    ↓ chuyển đổi
LangChain Document
    ↓
Embedding (BGE-M3) / Qdrant upsert

Pydantic Chunk
    ↓ chuyển đổi
SQLAlchemy DocumentChunk
    ↓
PostgreSQL insert (css.document_chunks)
```


Markdown body
    ↓
split_body_by_page_markers()
    ↓
PageBlock[]
    ↓
parse_page_blocks()
    ↓
StructuralBlock[]
    ↓
build_parent_sections()
    ↓
ParentSection[]
    ↓
make_parent_chunk()
    ↓
build_child_units()
    ↓
make_child_chunks()
    ↓
ChunkingResult

-------
Upload canonical Markdown
→ Review/chỉnh sửa
→ Đọc YAML + page markers
→ Structural parser
→ Parent/child chunking
→ Validation
---------
load DocumentVersion đã approved
→ đọc canonical Markdown
→ tạo IngestionJob
→ chunk
→ từ chối nếu ChunkingResult.errors không rỗng
→ lưu parent + child PostgreSQL
→ embedding child
→ upsert child vào Qdrant
→ cập nhật qdrant_point_id
→ cập nhật job/rag_status
---
python -m uvicorn app.main:app --reload

## Checklist chunk pipeline

- [ ] MarkdownHeaderTextSplitter tạo đúng parent chunks theo heading
- [ ] RecursiveCharacterTextSplitter tạo child chunks 300–600 tokens
- [ ] `chunk_type` đúng (`parent` / `child`)
- [ ] `parent_chunk_id` đúng (child trỏ về parent, parent là NULL)
- [ ] `chunk_key` unique per `document_version_id`
- [ ] `page_start` / `page_end` từ page marker `<!-- page: N -->`
- [ ] `heading_path` được kế thừa từ parent
- [ ] Chỉ embed child chunks
- [ ] Qdrant payload có `chunk_key`, `parent_chunk_key`, `postgres_chunk_id`
- [ ] `index_status` cập nhật đúng sau upsert
