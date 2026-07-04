# 10B. Part C - Huong Dan Page-Aware Chunker Decisions

**Last Updated:** 2026-06-25

File nay ghi rieng cac quyet dinh moi sau guide `10_PART_C_HEADING_AWARE_CHUNKER_GUIDE.md`.

Guide 10 giu vai tro MVP structural parent-child chunker. File nay chi mo ta chien luoc nang cap de xu ly dung cac case page marker nam giua section cu va heading moi.

---

## 1. File Layout

Them/sua cac function theo dung file sau:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
- PageBlock
- split_body_by_page_markers()

chatbot/backend/app/ingestion/chunking/parent_chunker.py
- build_parent_sections()
- merge_adjacent_parent_sections()
- current_heading_path logic nam trong build_parent_sections()

chatbot/backend/app/ingestion/chunking/child_chunker.py
- ChildText
- split_parent_chunk_to_child_texts_page_aware()
- neu dung ChildText thi cap nhat make_child_chunks()

chatbot/backend/app/ingestion/chunking/chunker.py
- chi orchestration, goi build_parent_sections()
- neu sau MVP dung ChildText thi doi cach goi make_child_chunks()

chatbot/backend/test/ingestion/test_chunker.py
- test_page_marker_before_new_heading_belongs_to_new_heading()
- test_page_continuation_inherits_previous_heading_until_new_heading()
```

Rule tach file:

```text
page_markers.py chi parse marker/page block.
parent_chunker.py chi build ParentSection va parent Chunk.
child_chunker.py chi split child text va tao child Chunk.
chunker.py chi dieu phoi, khong dat logic split page/heading phuc tap o day.
```

---

## 2. Van De Can Xu Ly

Input co the co dang:

```markdown
<!-- page: 1 -->
## Muc 2
Noi dung cua muc 2 o page 1.

<!-- page: 2 -->
# Xin giay khai sinh
## Dieu kien
Noi dung dieu kien o page 2.
```

Neu split heading tren toan bo body ngay tu dau, `MarkdownHeaderTextSplitter` co the gan marker `<!-- page: 2 -->` vao section truoc.

Ket qua sai:

```text
Section "Muc 2" bi dinh marker page 2.
Section "Xin giay khai sinh" khong con marker page.
```

Ket qua dung:

```text
Section "Muc 2" page_start=1, page_end=1
Section "Xin giay khai sinh / Dieu kien" page_start=2, page_end=2
```

---

## 3. Chien Luoc Page-Aware Parent Section

Khong de `MarkdownHeaderTextSplitter` tu quyet dinh page marker thuoc section nao.

Flow dung:

```text
Markdown body
  -> split_body_by_page_markers()
  -> PageBlock[]
  -> split heading trong tung PageBlock
  -> ParentSection[]
  -> merge adjacent sections neu cung heading_path
```

Parent section lay page range tu `PageBlock`, khong lay bang:

```python
require_page_range(content)
```

Ly do:

```text
Content sau khi split heading co the khong con marker dung.
PageBlock da biet chac noi dung do thuoc page nao.
```

---

## 4. PageBlock Helper

File:

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
```

Them import:

```python
from dataclasses import dataclass
```

Dataclass:

```python
@dataclass(frozen=True)
class PageBlock:
    page_number: int
    content: str
```

Function:

```python
def split_body_by_page_markers(body: str) -> list[PageBlock]:
    matches = list(PAGE_RE.finditer(body))
    if not matches:
        raise ValueError("Markdown body requires page marker before chunking")

    blocks: list[PageBlock] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if content:
            blocks.append(PageBlock(page_number=page_number, content=content))

    return blocks
```

---

## 5. Carry Heading Context Across Pages

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Case can xu ly:

```markdown
<!-- page: 1 -->
## Muc 2
Noi dung cua muc 2 o page 1.

<!-- page: 2 -->
Noi dung cua muc 2 o page 2.
abc

# Xin giay khai sinh
## Dieu kien
Noi dung dieu kien o page 2.
```

Dau page 2 chua co heading moi, nen content:

```text
Noi dung cua muc 2 o page 2.
abc
```

phai ke thua heading cuoi cua page truoc:

```python
["Muc 2"]
```

Dung bien:

```python
current_heading_path: list[str] = ["Document"]
```

Rule:

```python
heading_path = heading_path_from_metadata(doc.metadata or {})
if heading_path == ["Document"]:
    heading_path = current_heading_path
else:
    current_heading_path = heading_path
```

---

## 6. Build Parent Sections Page-Aware

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Can import:

```python
from app.ingestion.parsing.page_markers import split_body_by_page_markers
```

```python
def build_parent_sections(body: str) -> list[ParentSection]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )

    sections: list[ParentSection] = []
    current_heading_path: list[str] = ["Document"]

    for page_block in split_body_by_page_markers(body):
        docs = splitter.split_text(page_block.content)

        if not docs:
            content = page_block.content.strip()
            if content:
                sections.append(
                    ParentSection(
                        content=content,
                        heading_path=current_heading_path,
                        page_start=page_block.page_number,
                        page_end=page_block.page_number,
                    )
                )
            continue

        for doc in docs:
            content = doc.page_content.strip()
            if not content:
                continue

            heading_path = heading_path_from_metadata(doc.metadata or {})
            if heading_path == ["Document"]:
                heading_path = current_heading_path
            else:
                current_heading_path = heading_path

            sections.append(
                ParentSection(
                    content=content,
                    heading_path=heading_path,
                    page_start=page_block.page_number,
                    page_end=page_block.page_number,
                )
            )

    return merge_adjacent_parent_sections(sections)
```

---

## 7. Merge Adjacent Parent Sections

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Neu mot heading keo dai qua nhieu page, sau khi split theo page se co nhieu section cung `heading_path`.

Can merge section lien ke co cung heading:

```python
def merge_adjacent_parent_sections(sections: list[ParentSection]) -> list[ParentSection]:
    merged: list[ParentSection] = []

    for section in sections:
        if not merged:
            merged.append(section)
            continue

        previous = merged[-1]
        if previous.heading_path == section.heading_path:
            merged[-1] = ParentSection(
                content=f"{previous.content}\n\n{section.content}",
                heading_path=previous.heading_path,
                page_start=previous.page_start,
                page_end=section.page_end,
            )
            continue

        merged.append(section)

    return merged
```

---

## 8. Child Chunk MVP

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

Child chunk MVP khong can doi lon.

Rule hien tai:

```text
Child text co page marker -> lay page tu marker.
Child text khong co page marker -> fallback ve parent_chunk.page_start/page_end.
```

```python
page_start, page_end = require_page_range(
    text,
    fallback=(parent_chunk.page_start, parent_chunk.page_end),
)
```

Cach nay dam bao `page_start/page_end` khong null, nhung citation co the rong neu parent chunk trai qua nhieu page.

---

## 9. Sau MVP: Page-Aware Child Splitter

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

Neu can citation chinh xac hon, nang cap child splitter thanh page-aware.

Flow:

```text
parent_chunk.content
  -> split thanh PageBlock/PageSegment theo marker
  -> split tung page segment thanh child texts
  -> tao child chunk voi page_start/page_end cua segment
```

Pattern:

```python
from dataclasses import dataclass

from app.ingestion.parsing.page_markers import split_body_by_page_markers


@dataclass(frozen=True)
class ChildText:
    content: str
    page_start: int
    page_end: int


def split_parent_chunk_to_child_texts_page_aware(
    parent_chunk: Chunk,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> list[ChildText]:
    splitter = build_child_splitter(
        child_chunk_size=child_chunk_size,
        child_chunk_overlap=child_chunk_overlap,
    )

    child_texts: list[ChildText] = []
    for page_block in split_body_by_page_markers(parent_chunk.content):
        texts = splitter.split_text(page_block.content)
        for text in texts:
            content = text.strip()
            if not content:
                continue
            child_texts.append(
                ChildText(
                    content=content,
                    page_start=page_block.page_number,
                    page_end=page_block.page_number,
                )
            )

    return child_texts
```

Khi dung `ChildText`, `make_child_chunks()` se gan page truc tiep:

```python
page_start=child_text.page_start
page_end=child_text.page_end
content=child_text.content
```

---

## 10. Cap Nhat Orchestration Neu Dung Page-Aware Child

File:

```text
chatbot/backend/app/ingestion/chunking/chunker.py
```

Neu chi dung page-aware parent section, `chunker.py` khong can doi nhieu vi van goi:

```python
sections = build_parent_sections(body)
```

Neu nang cap page-aware child splitter, flow trong `chunker.py` doi thanh:

```python
child_texts = split_parent_chunk_to_child_texts_page_aware(
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
```

Luc nay `make_child_chunks()` trong `child_chunker.py` phai doc:

```python
child_text.content
child_text.page_start
child_text.page_end
```

thay vi coi moi item trong `child_texts` la `str`.

---

## 11. Test Can Co

File:

```text
chatbot/backend/test/ingestion/test_chunker.py
```

Test marker page moi nam truoc heading moi:

```python
def test_page_marker_before_new_heading_belongs_to_new_heading():
    body = """<!-- page: 1 -->

## Muc 2
Noi dung page 1.

<!-- page: 2 -->
# Xin giay khai sinh
## Dieu kien
Noi dung page 2.
"""
    chunks = chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1")

    xin_giay_chunks = [
        chunk
        for chunk in chunks
        if "Xin giay khai sinh" in chunk.heading_path
    ]

    assert xin_giay_chunks
    assert all(chunk.page_start == 2 for chunk in xin_giay_chunks)
```

Test dau page moi tiep noi heading cu truoc khi gap heading moi:

```python
def test_page_continuation_inherits_previous_heading_until_new_heading():
    body = """<!-- page: 1 -->
## Muc 2
Noi dung cua muc 2 o page 1.

<!-- page: 2 -->
Noi dung cua muc 2 o page 2.
abc

# Xin giay khai sinh
## Dieu kien
Noi dung dieu kien o page 2.
"""
    chunks = chunk_markdown_body(body=body, document_key="doc", version_key="doc-v1")

    muc_2_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_type == "parent" and chunk.heading_path == ["Muc 2"]
    ]
    xin_giay_chunks = [
        chunk
        for chunk in chunks
        if chunk.chunk_type == "parent"
        and chunk.heading_path == ["Xin giay khai sinh", "Dieu kien"]
    ]

    assert len(muc_2_chunks) == 1
    assert muc_2_chunks[0].page_start == 1
    assert muc_2_chunks[0].page_end == 2
    assert "abc" in muc_2_chunks[0].content

    assert len(xin_giay_chunks) == 1
    assert xin_giay_chunks[0].page_start == 2
    assert xin_giay_chunks[0].page_end == 2
```
