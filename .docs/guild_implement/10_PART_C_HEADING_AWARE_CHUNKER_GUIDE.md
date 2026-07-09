# 10. Part C - Hướng Dẫn Implement Structural Parent-Child Chunker

**Last Updated:** 2026-06-20

File này tách chi tiết từ guide 07, phần C.

Mục tiêu:

```text
Nhan Markdown body da validate
tach page marker truoc structural parsing
parent tao theo Markdown heading
child tao theo Dieu/Khoan/Diem/Bullet structural boundary
RecursiveCharacterTextSplitter chi dung cho item/paragraph/table/code qua dai
giu heading_path, item_path, legal_unit_type, page range, table/page marker neu co
tra ve list[Chunk] voi stable chunk keys
```

Chunker không đọc file, không parse YAML, không ghi DB, không tạo DB id.

---

## 1. File Cần Tạo/Sửa

```text
chatbot/backend/app/ingestion/chunking/__init__.py
chatbot/backend/app/ingestion/chunking/chunker.py
chatbot/backend/app/ingestion/chunking/parent_chunker.py
chatbot/backend/app/ingestion/chunking/child_chunker.py
chatbot/backend/app/ingestion/chunking/table_blocks.py
chatbot/backend/app/ingestion/chunking/text_stats.py
chatbot/backend/app/ingestion/parsing/__init__.py
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/app/ingestion/parsing/structural_parser.py
chatbot/backend/test/ingestion/test_chunker.py
chatbot/backend/test/ingestion/test_structural_parser.py
chatbot/backend/requirements.txt
```

Chunker nhận input từ:

```text
app.ingestion.markdown_reader.MarkdownDocument
```

Dependency cần có:

```text
langchain-text-splitters>=0.2
```

Import đề xuất trong từng file:

```python
# parent_chunker.py
from langchain_text_splitters import MarkdownHeaderTextSplitter

# child_chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

# parent_chunker.py va child_chunker.py
from app.ingestion.chunking.text_stats import count_units
```

---

## 1.1 Tách File Theo Trách Nhiệm

Dùng cấu trúc:

```text
app/ingestion/chunking/
    __init__.py
    chunker.py
    parent_chunker.py
    child_chunker.py
    table_blocks.py
    text_stats.py
```

Trách nhiệm:

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
- ChildUnit dataclass
- build_child_units()
- split_long_child_unit()
- make_child_chunks()

table_blocks.py
- TextBlock dataclass
- split_markdown_table_blocks()
- split_large_table_block()
- protect Markdown table truoc khi child splitter cat text

text_stats.py
- count_units()

parsing/structural_parser.py
- StructuralBlock dataclass
- AmbiguousBlockReport dataclass
- parse_structural_blocks()
- classify_line()
- build_item_path()
```

Không tách nhỏ hơn nữa trong MVP. Các file này đủ để clean code mà không làm structure quá phân mảnh.

## 2. Contract Quan Trọng

Trong MVP:

```text
Chunk.chunk_key = stable key trong memory/preview/DB/Qdrant
Chunk.parent_chunk_key = stable parent key trong memory/preview/DB/Qdrant
DocumentChunk.id = internal PostgreSQL primary key sau khi insert DB
DocumentChunk.parent_chunk_id = internal FK sau khi repository map parent_chunk_key -> DB id
```

Chunker tạo stable key, không tạo DB id.

Stable key đề xuất:

```text
<version_key>::p::<parent_index>
<version_key>::c::<child_index>
```

Ví dụ:

```text
qd3266-2024::p::0001
qd3266-2024::c::0001
```

Lưu ý quan trọng:

```text
parent_index va child_index chi dung de tao stable key rieng tung loai.
chunk_index trong Chunk/DocumentChunk phai la global sequential index trong version.
Khong reset chunk_index rieng cho parent/child, vi DB unique(document_version_id, chunk_index).
```

---

## 3. Chiến Lược Chunking

MVP dùng 3 lớp:

```text
Layer 1: Page-aware structural parser
  -> PageBlock[]
  -> StructuralBlock[]
  -> nhan dien code/table/heading/item/paragraph theo thu tu bat buoc

Layer 2: Parent chunker
  -> tao parent theo Markdown heading
  -> noi dung truoc heading dau tien vao document-root parent

Layer 3: Child chunker
  -> tao child theo numbered_item / lettered_item / bullet_item / table / code / paragraph boundary
  -> RecursiveCharacterTextSplitter chi split ben trong mot child unit qua dai

Project code
  -> gan stable chunk_key, parent_chunk_key, page_start/page_end, heading_path, item_path, legal_unit_type, chunk_index
```

Lý do:

```text
Markdown heading la parent boundary.
Dieu/Khoan/Diem/Bullet la child boundary.
Khong convert item thanh Markdown heading.
Project code van giu quyen kiem soat metadata, citation, DB mapping.
Khong dua DB id vao chunker.
```

---

## 4. Public API Đề Xuất

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

Hàm core:

```python
DEFAULT_CHILD_CHUNK_SIZE = 1000
DEFAULT_CHILD_CHUNK_OVERLAP = 100


def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int = DEFAULT_CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = DEFAULT_CHILD_CHUNK_OVERLAP,
) -> list[Chunk]:
    ...
```

Trong MVP, `child_chunk_size` và `child_chunk_overlap` tính theo ký tự vì `RecursiveCharacterTextSplitter` mặc định dùng length function theo character.

Giá trị default lấy từ runtime settings (xem `21_RUNTIME_SETTINGS_GUIDE.md`):

```text
chunking.child_chunk_size = 1000
chunking.child_chunk_overlap = 100
```

Không dùng fallback kiểu `settings.chunking.child_chunk_size or 1000`. Default nằm trong settings model, config YAML chỉ override.

---

## 5. ParentSection Dataclass

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

`ParentSection` nằm trong `parent_chunker.py` vì nó là output của bước tách parent section. Không đặt trong `chunker.py`, vì `chunker.py` chỉ nên điều phối orchestration.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ParentSection:
    content: str
    heading_path: list[str]
    page_start: int
    page_end: int
```

Nếu `child_chunker.py` cần type hint `ParentSection`, import:

```python
from app.ingestion.chunking.parent_chunker import ParentSection
```

`ParentSection` không phải schema/API public; nó chỉ là dataclass nội bộ của ingestion chunking.

---

## 6. Page Marker

OCR/canonical Markdown phải giữ marker:

```markdown
<!-- page: 1 -->
```

Page marker helper được tách riêng ở:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Xem chi tiết tại:

```text
chatbot/.docs/guild_implement/10A_PART_C_PAGE_MARKER_HELPER_GUIDE.md
```

Trong `parent_chunker.py` và `child_chunker.py`, import:

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

MVP dùng word count đơn giản để gán `token_count`. Sau này có thể thay bằng tokenizer thật nếu cần.

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

## 7. Tạo Parent Sections Bằng MarkdownHeaderTextSplitter

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Header config đề xuất:

```python
HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]
```

Helper nhỏ để code gọn hơn:

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

Function chính:

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

Lưu ý:

```text
LangChain metadata chi giu heading theo header config.
Neu can level 4-6 sau nay, them ("####", "h4")... vao config.
Khong dua langchain Document ra khoi chunker; output public van la list[Chunk].
Can test case page marker nam truoc heading. Neu MarkdownHeaderTextSplitter lam roi marker khoi section dau tien, `require_page_range(content)` se fail. Khi do can preprocess de gan current page marker vao section hoac giu marker trong content truoc khi tao ParentSection.
```

---

## 8. Tạo Parent Chunk

Parent chunk lưu full section trong PostgreSQL, không embed trong MVP.

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

## 9. Protect Markdown Table Blocks Trước Khi Split Child

Markdown table không được để `RecursiveCharacterTextSplitter` cắt tùy ý theo từng dòng, vì row table mất header sẽ mất ngữ cảnh retrieval.

Ví dụ cần bảo vệ:

```markdown
| Điểm số<br>theo thang điểm 10 | Điểm chữ | Điểm số<br>theo thang điểm 4 |
| --- | --- | --- |
| 9,0 - 10,0 | A | 4,0 |
| 8,0 - 8,9 | B+ | 3,5 |
```

Rule:

```text
Bang ngan hon child_chunk_size thi giu nguyen thanh 1 child text rieng.
Bang khong duoc tron chung voi cau truoc/sau neu co the tach rieng.
Bang dai hon child_chunk_size thi split theo nhom row, moi child table phai lap lai header + separator.
Khong split ngang mot row table.
Page marker nam gan bang phai duoc giu de child table resolve page_start/page_end.
```

File nên đặt helper:

```text
chatbot/backend/app/ingestion/chunking/table_blocks.py
```

Dataclass gợi ý:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TextBlock:
    content: str
    block_type: str  # "text" | "table"
```

Detect Markdown table block:

```python
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
```

Heuristic:

```text
Mot table block can co it nhat:
- 1 dong header bat dau/ket thuc bang "|"
- 1 dong separator ngay sau header
- 0..n dong data lien tiep bat dau/ket thuc bang "|"
```

API gợi ý:

```python
def split_markdown_table_blocks(text: str) -> list[TextBlock]:
    ...


def split_large_table_block(
    table: str,
    *,
    child_chunk_size: int,
) -> list[str]:
    ...
```

`split_large_table_block()` phải giữ:

```text
header
separator
row group
```

trong từng child table.

---

## 10. Tạo Child Units Theo Structural Boundary

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

Child boundary:

```text
numbered_item
lettered_item
bullet_item
table
code
paragraph ro rang doc lap
```

Không gộp hai item khác nhau chỉ để đạt `child_chunk_size`.

Dataclass gợi ý:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ChildUnit:
    content: str
    block_type: str
    page_start: int
    page_end: int
    item_marker: str | None
    item_level: int | None
    item_path: list[str]
    legal_unit_type: str
```

Recursive splitter chỉ dùng cho một unit quá dài:

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

Build child units:

```python
def build_child_units(
    parent_chunk: Chunk,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> list[ChildUnit]:
    units = build_structural_child_units(parent_chunk.content)
    result: list[ChildUnit] = []

    for unit in units:
        if unit.block_type == "table":
            result.extend(split_table_child_unit(unit, child_chunk_size=child_chunk_size))
            continue

        if len(unit.content) > child_chunk_size:
            result.extend(
                split_long_child_unit(
                    unit,
                    child_chunk_size=child_chunk_size,
                    child_chunk_overlap=child_chunk_overlap,
                )
            )
            continue

        result.append(unit)

    return result
```

Lý do split bằng `parent_chunk` thay vì `ParentSection`:

```text
Sau khi da tao parent Chunk, child pipeline chi nen lam viec voi parent Chunk.
ParentSection chi la object tam de build parent Chunk.
Dung parent_chunk.content giup flow don gian hon:
ParentSection -> parent Chunk -> ChildUnit -> child Chunks
```

Lưu ý về table:

```text
RecursiveCharacterTextSplitter khong hieu semantic table cua du an.
Phai detect table truoc item regex va truoc recursive splitter.
Table ngan thanh 1 child chunk rieng.
Table dai split theo row group va lap lai header/separator.
```

---

## 11. Tạo Child Chunks

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

```python
def make_child_chunks(
    *,
    child_units: list[ChildUnit],
    parent_chunk: Chunk,
    document_key: str,
    version_key: str,
    child_start_index: int,
    chunk_start_index: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for offset, unit in enumerate(child_units):
        child_number = child_start_index + offset

        chunks.append(
            Chunk(
                document_key=document_key,
                version_key=version_key,
                chunk_key=f"{version_key}::c::{child_number:04d}",
                parent_chunk_key=parent_chunk.chunk_key,
                chunk_type="child",
                content=unit.content,
                heading_path=parent_chunk.heading_path,
                item_marker=unit.item_marker,
                item_level=unit.item_level,
                item_path=unit.item_path,
                legal_unit_type=unit.legal_unit_type,
                block_type=unit.block_type,
                page_start=unit.page_start,
                page_end=unit.page_end,
                chunk_index=chunk_start_index + offset,
                token_count=count_units(unit.content),
            )
        )
    return chunks
```

Lý do không truyền `section` vào `make_child_chunks()`:

```text
ParentSection chi la object tam sau buoc tach heading.
parent_chunk la Chunk cha chinh thuc da tao tu ParentSection.
Child chunk chi can parent_chunk de lay:
- parent_chunk.chunk_key lam parent_chunk_key
- parent_chunk.heading_path
- parent_chunk.page_start/page_end lam fallback khi structural unit thieu page
```

Sau khi đã có `parent_chunk`, child pipeline không cần đưa `section` tiếp vào nữa.

---

## 12. Hàm Core `chunk_markdown_body`

File:

```text
chatbot/backend/app/ingestion/chunking/chunker.py
```

Suggested pattern:

```python
from app.ingestion.chunking.child_chunker import (
    build_child_units,
    make_child_chunks,
)
from app.ingestion.chunking.parent_chunker import (
    build_parent_sections,
    make_parent_chunk,
)


DEFAULT_CHILD_CHUNK_SIZE = 1000
DEFAULT_CHILD_CHUNK_OVERLAP = 100


def chunk_markdown_body(
    *,
    body: str,
    document_key: str,
    version_key: str,
    child_chunk_size: int = DEFAULT_CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = DEFAULT_CHILD_CHUNK_OVERLAP,
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

        child_units = build_child_units(
            parent,
            child_chunk_size=child_chunk_size,
            child_chunk_overlap=child_chunk_overlap,
        )
        children = make_child_chunks(
            child_units=child_units,
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

Trong production caller, truyền `child_chunk_size` và `child_chunk_overlap` từ `get_rag_settings().chunking`. Function vẫn có default để test/unit call đơn giản, nhưng không rải magic number ở pipeline.

---

## 13. Test Cần Có

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

Table test:

```python
def test_chunker_keeps_small_table_as_one_child_chunk():
    chunks = chunk_markdown_body(body=SAMPLE_BODY, document_key="doc", version_key="doc-v1")
    table_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_type == "child" and "| Cot A | Cot B |" in chunk.content
    ]

    assert len(table_chunks) == 1
    assert "|---|---|" in table_chunks[0].content
    assert "| A | B |" in table_chunks[0].content
```

Với table lớn hơn `child_chunk_size`, test phải assert mỗi child table vẫn có header + separator:

```python
def test_large_table_chunks_repeat_header_and_separator():
    ...
    table_chunks = [...]

    assert len(table_chunks) > 1
    for chunk in table_chunks:
        assert "| Cot A | Cot B |" in chunk.content
    assert "|---|---|" in chunk.content
```

Structural parser/chunker tests bắt buộc:

```text
1. Danh sách 5 mục dưới một heading tạo 1 parent và 5 child.
2. Item không bị convert thành heading.
3. `### 1. Mục đích` vẫn là heading.
4. `### 1) Phạm vi` vẫn là heading.
5. `### a) Đối tượng` vẫn là heading.
6. `### - Nội dung` vẫn là heading.
7. Markdown heading không bị demote thành numbered_item/lettered_item/bullet_item.
8. Điều -> Khoản -> Điểm -> Bullet tạo đúng item_path.
9. Paragraph được gắn đúng item hoặc sinh ambiguous report.
10. Item con kế thừa context cha.
11. Item cha kết thúc bằng ":" không tạo child rỗng.
12. Bullet -, +, * tạo atomic child.
13. Item quá dài chỉ split nội bộ.
14. Không child nào chứa nội dung của hai item khác nhau.
15. Marker trong table/code không bị parse thành item.
16. Nội dung trước heading đầu tiên thuộc document-root parent.
17. Table/code trong item kế thừa đúng context.
18. Child ngắn có embedding_text chứa context thật.
19. Page marker không bị đưa vào embedding_text.
```

---

## 14. Lệnh Test

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/ingestion/test_chunker.py
```

---

## 15. Done Khi

- [ ] Có dependency `langchain-text-splitters`.
- [ ] Chunker không mất nội dung body.
- [ ] Parent chunk không có `parent_chunk_key`.
- [ ] Child chunk có `parent_chunk_key` là stable parent key.
- [ ] `chunk_key` theo pattern `<version_key>::p/c::<0001>`.
- [ ] `chunk_index` global sequential trong version.
- [ ] `heading_path` được gán theo Markdown headers.
- [ ] Mọi chunk đều có `page_start`, `page_end`, `token_count`.
- [ ] `page_start <= page_end`.
- [ ] Small table thành đúng một child chunk riêng.
- [ ] Large table nếu bị split thì mỗi child table có header + separator.
- [ ] Test chunker pass.

---

## 16. Lỗi Dễ Gặp

### Lỗi: import langchain sai

Nguyên nhân:

```text
Dung import cu `from langchain.text_splitter import ...`
```

Xử lý:

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
```

### Lỗi: child chunk parent id không tồn tại

Nguyên nhân:

```text
parent_chunk_key bi set bang DB id truoc khi insert DB.
```

Xử lý:

```text
Trong chunker chi dung stable parent key.
Repository moi map stable key sang DB id.
```

### Lỗi: unique constraint chunk_index

Nguyên nhân:

```text
chunk_index reset rieng cho parent va child.
```

Xử lý:

```text
Dung chunk_index global sequential cho tat ca parent + child chunks trong cung version.
```

### Lỗi: table bị split

Nguyên nhân:

```text
Recursive splitter cat theo character/paragraph, khong hieu semantic table.
```

Xử lý MVP:

```text
Tang child_chunk_size va them test small table.
Neu van khong du, implement protect table blocks truoc khi split.
```
