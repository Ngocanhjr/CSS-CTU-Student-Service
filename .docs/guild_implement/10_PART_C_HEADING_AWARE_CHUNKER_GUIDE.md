# 10. Part C - Huong Dan Implement Structural Parent-Child Chunker

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan C.

Muc tieu:

```text
Nhan Markdown body da validate
dung langchain-text-splitters de tach structural parent sections
dung RecursiveCharacterTextSplitter de tach child chunks trong tung parent
giu heading_path, page range, table/page marker neu co
tra ve list[Chunk] voi stable chunk keys
```

Chunker khong doc file, khong parse YAML, khong ghi DB, khong tao DB id.

---

## 1. File Can Tao/Sua

```text
chatbot/backend/app/ingestion/chunking/__init__.py
chatbot/backend/app/ingestion/chunking/chunker.py
chatbot/backend/app/ingestion/chunking/parent_chunker.py
chatbot/backend/app/ingestion/chunking/child_chunker.py
chatbot/backend/app/ingestion/chunking/text_stats.py
chatbot/backend/app/ingestion/parsing/__init__.py
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/test/ingestion/test_chunker.py
chatbot/backend/requirements.txt
```

Chunker nhan input tu:

```text
app.ingestion.markdown_reader.MarkdownDocument
```

Dependency can co:

```text
langchain-text-splitters>=0.2
```

Import de xuat trong tung file:

```python
# parent_chunker.py
from langchain_text_splitters import MarkdownHeaderTextSplitter

# child_chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

# parent_chunker.py va child_chunker.py
from app.ingestion.chunking.text_stats import count_units
```

---

## 1.1 Tach File Theo Trach Nhiem

Dung cau truc:

```text
app/ingestion/chunking/
    __init__.py
    chunker.py
    parent_chunker.py
    child_chunker.py
    text_stats.py
```

Trach nhiem:

```text
chunker.py
- public API: chunk_markdown_document(), chunk_markdown_body()
- dieu phoi parent_chunker va child_chunker
- quan ly chunk_index global va child_counter
- return list[Chunk]

parent_chunker.py
- ParentSection dataclass
- HEADERS_TO_SPLIT_ON
- heading_path_from_metadata()
- make_parent_section()
- build_parent_sections()
- make_parent_chunk()

child_chunker.py
- build_child_splitter()
- split_parent_chunk_to_child_texts()
- make_child_chunks()

text_stats.py
- count_units()
```

Khong tach nho hon nua trong MVP. Ba file nay du de clean code ma khong lam structure qua phan manh.

## 2. Contract Quan Trong

Trong MVP:

```text
Chunk.chunk_key = stable key trong memory/preview/DB/Qdrant
Chunk.parent_chunk_key = stable parent key trong memory/preview/DB/Qdrant
DocumentChunk.id = internal PostgreSQL primary key sau khi insert DB
DocumentChunk.parent_chunk_id = internal FK sau khi repository map parent_chunk_key -> DB id
```

Chunker tao stable key, khong tao DB id.

Stable key de xuat:

```text
<version_key>::p::<parent_index>
<version_key>::c::<child_index>
```

Vi du:

```text
qd3266-2024::p::0001
qd3266-2024::c::0001
```

Luu y quan trong:

```text
parent_index va child_index chi dung de tao stable key rieng tung loai.
chunk_index trong Chunk/DocumentChunk phai la global sequential index trong version.
Khong reset chunk_index rieng cho parent/child, vi DB unique(document_version_id, chunk_index).
```

---

## 3. Chien Luoc Chunking

MVP dung 2 lop:

```text
Layer 1: MarkdownHeaderTextSplitter
  -> tach Markdown thanh parent structural sections theo heading

Layer 2: RecursiveCharacterTextSplitter
  -> tach tung parent section thanh child chunks nho hon

Project code
  -> gan stable chunk_key, parent_chunk_key, page_start/page_end, heading_path, chunk_index
```

Ly do:

```text
LangChain lo phan splitting co ban.
Project code van giu quyen kiem soat metadata, citation, DB mapping.
Khong dua DB id vao chunker.
```

---

## 4. Public API De Xuat

File:

```text
chatbot/backend/app/ingestion/chunking/chunker.py
```

Suggested pattern:

```python
from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk


def chunk_markdown_document(document: MarkdownDocument) -> list[Chunk]:
    return chunk_markdown_body(
        body=document.body,
        document_key=document.metadata.document_key,
        version_key=document.metadata.version_key,
    )
```

Ham core:

```python
def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int = 1800,
    child_chunk_overlap: int = 200,
) -> list[Chunk]:
    ...
```

Trong MVP, `child_chunk_size` va `child_chunk_overlap` tinh theo ky tu vi `RecursiveCharacterTextSplitter` mac dinh dung length function theo character.

---

## 5. ParentSection Dataclass

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

`ParentSection` nam trong `parent_chunker.py` vi no la output cua buoc tach parent section. Khong dat trong `chunker.py`, vi `chunker.py` chi nen dieu phoi orchestration.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ParentSection:
    content: str
    heading_path: list[str]
    page_start: int
    page_end: int
```

Neu `child_chunker.py` can type hint `ParentSection`, import:

```python
from app.ingestion.chunking.parent_chunker import ParentSection
```

`ParentSection` khong phai schema/API public; no chi la dataclass noi bo cua ingestion chunking.

---

## 6. Page Marker

OCR/canonical Markdown phai giu marker:

```markdown
<!-- page: 1 -->
```

Page marker helper duoc tach rieng o:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Xem chi tiet tai:

```text
chatbot/.docs/guild_implement/10A_PART_C_PAGE_MARKER_HELPER_GUIDE.md
```

Trong `parent_chunker.py` va `child_chunker.py`, import:

```python
from app.ingestion.parsing.page_markers import require_page_range
```

Rule:

```text
Page marker khong duoc xoa truoc khi split.
Parent/child page_start/page_end lay tu content sau split.
Parent chunk phai resolve duoc page range, khong duoc tra `None`.
Neu child khong co page marker nhung parent co page range, fallback sang parent range.
Neu toan bo document khong co page marker thi chunker fail som de khong tao chunk sai contract.
```

---

## 6.1 Text Stats Helper

File:

```text
chatbot/backend/app/ingestion/chunking/text_stats.py
```

MVP dung word count don gian de gan `token_count`. Sau nay co the thay bang tokenizer that neu can.

```python
def count_units(text: str) -> int:
    return len(text.split())
```

Rule:

```text
token_count khong duoc null.
Parent va child chunk deu dung cung helper nay.
```

---

## 7. Tao Parent Sections Bang MarkdownHeaderTextSplitter

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Header config de xuat:

```python
HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]
```

Helper nho de code gon hon:

```python
def heading_path_from_metadata(metadata: dict) -> list[str]:
    heading_path = [
        str(metadata[key]).strip()
        for key in ("h1", "h2", "h3")
        if metadata.get(key)
    ]
    return heading_path or ["Document"]


def make_parent_section(content: str, heading_path: list[str]) -> ParentSection:
    page_start, page_end = require_page_range(content)
    return ParentSection(
        content=content,
        heading_path=heading_path,
        page_start=page_start,
        page_end=page_end,
    )
```

Function chinh:

```python
def build_parent_sections(body: str) -> list[ParentSection]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )

    docs = splitter.split_text(body)

    if not docs:
        return [make_parent_section(body.strip(), ["Document"])]

    sections: list[ParentSection] = []
    for doc in docs:
        content = doc.page_content.strip()
        if not content:
            continue

        sections.append(
            make_parent_section(
                content,
                heading_path_from_metadata(doc.metadata or {}),
            )
        )

    return sections
```

Luu y:

```text
LangChain metadata chi giu heading theo header config.
Neu can level 4-6 sau nay, them ("####", "h4")... vao config.
Khong dua langchain Document ra khoi chunker; output public van la list[Chunk].
Can test case page marker nam truoc heading. Neu MarkdownHeaderTextSplitter lam roi marker khoi section dau tien, `require_page_range(content)` se fail. Khi do can preprocess de gan current page marker vao section hoac giu marker trong content truoc khi tao ParentSection.
```

---

## 8. Tao Parent Chunk

Parent chunk luu full section trong PostgreSQL, khong embed trong MVP.

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

```python
from app.ingestion.chunking.text_stats import count_units


def make_parent_chunk(
    *,
    section: ParentSection,
    document_key: str,
    version_key: str,
    parent_index: int,
    chunk_index: int,
) -> Chunk:
    parent_key = f"{version_key}::p::{parent_index:04d}"
    return Chunk(
        document_key=document_key,
        version_key=version_key,
        chunk_key=parent_key,
        chunk_type="parent",
        content=section.content,
        heading_path=section.heading_path,
        page_start=section.page_start,
        page_end=section.page_end,
        chunk_index=chunk_index,
        token_count=count_units(section.content),
    )
```

---

## 9. Tao Child Texts Bang RecursiveCharacterTextSplitter

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

Child splitter:

```python
def build_child_splitter(
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )
```

Split:

```python
def split_parent_chunk_to_child_texts(
    parent_chunk: Chunk,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> list[str]:
    splitter = build_child_splitter(
        child_chunk_size=child_chunk_size,
        child_chunk_overlap=child_chunk_overlap,
    )
    texts = splitter.split_text(parent_chunk.content)
    return [text.strip() for text in texts if text.strip()]
```

Ly do split bang `parent_chunk` thay vi `ParentSection`:

```text
Sau khi da tao parent Chunk, child pipeline chi nen lam viec voi parent Chunk.
ParentSection chi la object tam de build parent Chunk.
Dung parent_chunk.content giup flow don gian hon:
ParentSection -> parent Chunk -> child texts -> child Chunks
```

Luu y ve table:

```text
RecursiveCharacterTextSplitter khong hieu semantic table cua du an.
Voi MVP, uu tien child_chunk_size du lon de table thuong khong bi cat.
Neu table bi cat, them buoc protect table blocks truoc khi split trong version sau.
Khong split Markdown table line-by-line bang custom code neu chua co test.
```

---

## 10. Tao Child Chunks

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

```python
def make_child_chunks(
    *,
    child_texts: list[str],
    parent_chunk: Chunk,
    document_key: str,
    version_key: str,
    child_start_index: int,
    chunk_start_index: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for offset, text in enumerate(child_texts):
        child_number = child_start_index + offset
        page_start, page_end = require_page_range(
            text,
            fallback=(parent_chunk.page_start, parent_chunk.page_end),
        )

        chunks.append(
            Chunk(
                document_key=document_key,
                version_key=version_key,
                chunk_key=f"{version_key}::c::{child_number:04d}",
                parent_chunk_key=parent_chunk.chunk_key,
                chunk_type="child",
                content=text,
                heading_path=parent_chunk.heading_path,
                page_start=page_start,
                page_end=page_end,
                chunk_index=chunk_start_index + offset,
                token_count=count_units(text),
            )
        )
    return chunks
```

Ly do khong truyen `section` vao `make_child_chunks()`:

```text
ParentSection chi la object tam sau buoc tach heading.
parent_chunk la Chunk cha chinh thuc da tao tu ParentSection.
Child chunk chi can parent_chunk de lay:
- parent_chunk.chunk_key lam parent_chunk_key
- parent_chunk.heading_path
- parent_chunk.page_start/page_end lam fallback
```

Sau khi da co `parent_chunk`, child pipeline khong can dua `section` tiep vao nua.

---

## 11. Ham Core `chunk_markdown_body`

File:

```text
chatbot/backend/app/ingestion/chunking/chunker.py
```

Suggested pattern:

```python
from app.ingestion.chunking.child_chunker import (
    make_child_chunks,
    split_parent_chunk_to_child_texts,
)
from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)


def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int = 1800,
    child_chunk_overlap: int = 200,
) -> list[Chunk]:
    if not body.strip():
        raise ValueError("Markdown body is empty")

    sections = build_parent_sections(body)
    chunks: list[Chunk] = []
    child_counter = 1
    chunk_index = 0

    for parent_counter, section in enumerate(sections, start=1):
        parent = make_parent_chunk(
            section=section,
            document_key=document_key,
            version_key=version_key,
            parent_index=parent_counter,
            chunk_index=chunk_index,
        )
        chunks.append(parent)
        chunk_index += 1

        child_texts = split_parent_chunk_to_child_texts(
            parent,
            child_chunk_size=child_chunk_size,
            child_chunk_overlap=child_chunk_overlap,
        )
        children = make_child_chunks(
            child_texts=child_texts,
            parent_chunk=parent,
            document_key=document_key,
            version_key=version_key,
            child_start_index=child_counter,
            chunk_start_index=chunk_index,
        )
        chunks.extend(children)
        child_counter += len(children)
        chunk_index += len(children)

    return chunks
```

---

## 12. Test Can Co

File:

```text
chatbot/backend/test/ingestion/test_chunker.py
```

Test fixture:

```python
SAMPLE_BODY = """<!-- page: 1 -->

# Tai lieu mau

## Chuong I

### Dieu 1. Pham vi

Noi dung dieu 1.

| Cot A | Cot B |
|---|---|
| A | B |

<!-- page: 2 -->

### Dieu 2. Doi tuong

Noi dung dieu 2.
"""
```

Tests:

```python
from app.ingestion.chunking.chunker import chunk_markdown_body


def test_chunker_creates_parent_and_child():
    chunks = chunk_markdown_body(
        body=SAMPLE_BODY,
        document_key="doc",
        version_key="doc-v1",
    )

    assert any(chunk.chunk_type == "parent" for chunk in chunks)
    assert any(chunk.chunk_type == "child" for chunk in chunks)


def test_child_chunks_have_parent_key():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")
    parent_keys = {chunk.chunk_key for chunk in chunks if chunk.chunk_type == "parent"}

    for chunk in chunks:
        if chunk.chunk_type == "child":
            assert chunk.parent_chunk_key in parent_keys


def test_chunker_uses_stable_key_pattern():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")

    assert any(chunk.chunk_key.startswith("doc-v1::p::") for chunk in chunks)
    assert any(chunk.chunk_key.startswith("doc-v1::c::") for chunk in chunks)


def test_chunk_index_is_global_sequential():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunker_tracks_heading_path():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")
    assert any("Dieu 1. Pham vi" in chunk.heading_path for chunk in chunks)


def test_chunker_tracks_page_range():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")
    assert any(chunk.page_start == 1 for chunk in chunks)


def test_chunker_keeps_page_marker_before_heading():
    body = """<!-- page: 1 -->

# Title

Content on page 1.
"""
    chunks = chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1")

    assert chunks
    assert all(chunk.page_start == 1 and chunk.page_end == 1 for chunk in chunks)


def test_chunker_rejects_empty_body():
    with pytest.raises(ValueError):
        chunk_markdown_body(body="", document_key="doc", version_key="doc-v1")


def test_chunker_rejects_missing_page_marker():
    with pytest.raises(ValueError):
        chunk_markdown_body(
            body="# Title\n\nNo page marker.",
            document_key="doc",
            version_key="doc-v1",
        )
```

Table test nen bat dau don gian:

```python
def test_chunker_keeps_small_table_visible():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")
    table_chunks = [chunk for chunk in chunks if "| Cot A | Cot B |" in chunk.content]

    assert table_chunks
    assert "| A | B |" in table_chunks[0].content
```

Khong assert table khong bao gio bi split neu `child_chunk_size` qua nho. Neu muon rule do, can implement table-protection rieng.

---

## 13. Lenh Test

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_chunker.py
```

---

## 14. Done Khi

- [ ] Co dependency `langchain-text-splitters`.
- [ ] Chunker khong mat noi dung body.
- [ ] Parent chunk khong co `parent_chunk_key`.
- [ ] Child chunk co `parent_chunk_key` la stable parent key.
- [ ] `chunk_key` theo pattern `<version_key>::p/c::<0001>`.
- [ ] `chunk_index` global sequential trong version.
- [ ] `heading_path` duoc gan theo Markdown headers.
- [ ] Moi chunk deu co `page_start`, `page_end`, `token_count`.
- [ ] `page_start <= page_end`.
- [ ] Small table van hien trong it nhat mot child chunk.
- [ ] Test chunker pass.

---

## 15. Loi De Gap

### Loi: import langchain sai

Nguyen nhan:

```text
Dung import cu `from langchain.text_splitter import ...`
```

Xu ly:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
```

### Loi: child chunk parent id khong ton tai

Nguyen nhan:

```text
parent_chunk_key bi set bang DB id truoc khi insert DB.
```

Xu ly:

```text
Trong chunker chi dung stable parent key.
Repository moi map stable key sang DB id.
```

### Loi: unique constraint chunk_index

Nguyen nhan:

```text
chunk_index reset rieng cho parent va child.
```

Xu ly:

```text
Dung chunk_index global sequential cho tat ca parent + child chunks trong cung version.
```

### Loi: table bi split

Nguyen nhan:

```text
Recursive splitter cat theo character/paragraph, khong hieu semantic table.
```

Xu ly MVP:

```text
Tang child_chunk_size va them test small table.
Neu van khong du, implement protect table blocks truoc khi split.
```
