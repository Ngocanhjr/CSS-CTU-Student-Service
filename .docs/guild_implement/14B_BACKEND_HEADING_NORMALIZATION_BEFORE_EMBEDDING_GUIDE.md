# 14B. Huong Dan Normalize Heading Nghiep Vu O Backend Truoc Embedding

**Last Updated:** 2026-06-26

File nay bo sung cho guide 14/14A.

Muc tieu:

```text
Lam chunk dung cau truc nghiep vu hon truoc khi embedding/retrieval.
Sua page_start/page_end de citation dung trang.
Khong dua rule nay vao OCR.
Khong sua truc tiep markdown goc.
```

---

## 1. Quyet Dinh

Normalize heading nghiep vu phai lam o backend ingestion/parsing, khong lam trong OCR.

Flow chot:

```text
OCR/loader
  -> raw Markdown body
  -> split_body_by_page_markers()
  -> backend parsing normalize_structural_headings()
  -> page-aware parent chunker
  -> page-aware child chunker
  -> enriched embedding text
  -> embedding
  -> Qdrant
```

Ly do:

```text
OCR chi nen doc chu/layout co ban.
Nhan dien dong "2. Doi moi noi dung..." la heading nghiep vu la logic ingestion/chunking.
Neu doi OCR engine hoac input la .md/.docx/html thi rule heading van dung lai duoc.
Neu rule sai, chi can re-chunk/re-index, khong can chay lai OCR.
```

---

## 2. Van De Dang Gap

MarkdownHeaderTextSplitter chi tach cac heading Markdown:

```markdown
# KẾ HOẠCH
## I. MỤC ĐÍCH, YÊU CẦU
#### A/ Nội dung:
```

Nhung nhieu tai lieu hanh chinh co heading nghiep vu dang plain text:

```text
2. Đổi mới nội dung, phương pháp và hình thức giáo dục
3. Nâng cao năng lực đội ngũ cán bộ, giảng viên
4. Tăng cường sự phối hợp giữa gia đình, nhà trường, xã hội
```

Neu khong normalize, cac muc nay bi gom vao section truoc do, vi no khong co dau `#`.

Ket qua xau:

```text
Parent chunk qua rong.
heading_path sai ngu canh.
Retrieval search duoc nhung context khong gon.
Citation/page expansion kho hon.
page_start/page_end sai lam citation sai trang.
```

---

## 3. Khong Sua OCR Output

Khong convert heading trong OCR.

Khong sua file markdown goc theo cach ghi de:

```text
raw_body -> modified_body overwrite file .md
```

Dung 3 lop text rieng:

```text
raw_body
- Lay tu markdown_reader.
- Giu de trace/debug/citation.

normalized_body
- Sinh trong backend parsing.
- Dung cho parent/child chunking.

embedding_text
- Sinh tu chunk + metadata.
- Clean noise va enrich heading/title/page truoc khi embed.
```

---

## 4. File Can Tao

Tao file:

```text
chatbot/backend/app/ingestion/parsing/heading_normalizer.py
```

Tao/cap nhat them cac file page-aware:

```text
chatbot/backend/app/ingestion/parsing/page_blocks.py
chatbot/backend/app/ingestion/chunking/parent_chunker.py
chatbot/backend/app/ingestion/chunking/child_chunker.py
chatbot/backend/app/ingestion/chunking/chunker.py
```

Function chinh:

```python
def normalize_structural_headings(body: str) -> str:
    ...
```

Function page-aware:

```python
def split_body_by_page_markers(body: str) -> list[PageBlock]:
    ...

def build_parent_sections(body: str) -> list[ParentSection]:
    ...

def split_parent_chunk_to_child_texts_page_aware(parent_chunk: Chunk) -> list[ChildText]:
    ...
```

Goi function nay trong:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

Vi tri goi:

```python
def build_parent_sections(body: str) -> list[ParentSection]:
    page_blocks = split_body_by_page_markers(body)
    sections: list[ParentSection] = []

    for page_block in page_blocks:
        normalized_content = normalize_structural_headings(page_block.content)
        docs = splitter.split_text(normalized_content)
        ...
    ...
```

Normalize nen nam trong tung page block truoc buoc split heading, nhung khong duoc lam mat page marker.

---

## 5. Sua Citation/Page Range Cung Luc

Loi can sua:

```text
Neu MarkdownHeaderTextSplitter split heading truoc, page marker co the bi gan vao section sai.
Khi page_start/page_end sai, citation sau nay trong retrieval cung sai.
```

Vi du sai:

```text
#### A/ Nội dung:
noi dung cuoi page 1

<!-- page: 2 -->
noi dung tiep page 2

#### B/ Hình thức:
...
```

Neu detect page bang marker nam trong section sau split heading, section `A/ Nội dung` co the bi gan thanh:

```text
page_start=2
page_end=2
```

Dung hon phai la:

```text
page_start=1
page_end=2
```

Rule chot:

```text
Tach page block truoc.
Moi PageBlock biet chinh xac page_number.
Trong tung page block, normalize heading nghiep vu.
Trong tung page block, split heading.
Neu page block moi khong co heading moi, ke thua heading_path dang active tu page truoc.
Sau do merge cac section lien ke co cung heading_path.
page_start cua section merge = page dau.
page_end cua section merge = page cuoi.
```

Flow:

```text
raw body
  -> PageBlock(page=1, content=...)
  -> PageBlock(page=2, content=...)
  -> split heading trong tung PageBlock
  -> ParentSection(page_start=1, page_end=1)
  -> ParentSection(page_start=2, page_end=2)
  -> merge same heading_path
  -> ParentSection(page_start=1, page_end=2)
```

Day la phan sua citation goc, vi retrieval/citation guide 16 chi format citation tu `page_start/page_end`; neu chunker gan page sai thi 16 khong sua duoc.

---

## 6. Page-Aware Parent Section

File:

```text
chatbot/backend/app/ingestion/parsing/page_blocks.py
```

Skeleton:

```python
from dataclasses import dataclass
import re

PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->", re.IGNORECASE)


@dataclass(frozen=True)
class PageBlock:
    page_number: int
    content: str


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

File:

```text
chatbot/backend/app/ingestion/chunking/parent_chunker.py
```

`build_parent_sections()` nen lam:

```python
def build_parent_sections(body: str) -> list[ParentSection]:
    page_blocks = split_body_by_page_markers(body)
    sections: list[ParentSection] = []
    active_heading_path: list[str] = ["Document"]

    for page_block in page_blocks:
        normalized_content = normalize_structural_headings(page_block.content)
        docs = splitter.split_text(normalized_content)

        for doc in docs:
            content = doc.page_content.strip()
            if not content:
                continue

            heading_path = heading_path_from_metadata(
                doc.metadata,
                fallback=active_heading_path,
            )
            active_heading_path = heading_path

            sections.append(
                ParentSection(
                    content=content,
                    heading_path=heading_path,
                    page_start=page_block.page_number,
                    page_end=page_block.page_number,
                )
            )

    return merge_adjacent_sections_with_same_heading_path(sections)
```

`heading_path_from_metadata()` phai co fallback:

```python
def heading_path_from_metadata(
    metadata: dict,
    *,
    fallback: list[str],
) -> list[str]:
    heading_path = [
        str(metadata[key]).strip()
        for key in ("h1", "h2", "h3", "h4", "h5", "h6")
        if metadata.get(key)
    ]
    return heading_path or fallback or ["Document"]
```

Ly do can `active_heading_path`:

```text
Page 1 co heading "A/ Noi dung".
Page 2 chi tiep tuc bullet cua "A/ Noi dung", khong lap lai heading.
Neu khong ke thua heading_path, page 2 se bi gan thanh "Document" va khong merge duoc voi page 1.
```

`merge_adjacent_sections_with_same_heading_path()`:

```python
def merge_adjacent_sections_with_same_heading_path(
    sections: list[ParentSection],
) -> list[ParentSection]:
    merged: list[ParentSection] = []

    for section in sections:
        if merged and merged[-1].heading_path == section.heading_path:
            previous = merged[-1]
            merged[-1] = ParentSection(
                content="\n\n".join([previous.content, section.content]),
                heading_path=previous.heading_path,
                page_start=previous.page_start,
                page_end=section.page_end,
            )
            continue

        merged.append(section)

    return merged
```

---

## 7. Page-Aware Child Chunk Cho Citation Chinh Xac Hon

MVP co the cho child fallback theo parent range:

```text
child page_start/page_end = parent page_start/page_end
```

Nhung neu parent trai qua nhieu page, citation cua child se rong hon can thiet.

De citation chinh xac hon, child splitter nen page-aware:

```text
parent chunk
  -> tach lai thanh page segments
  -> split child trong tung page segment
  -> child chunk lay page_start/page_end cua segment
```

File:

```text
chatbot/backend/app/ingestion/chunking/child_chunker.py
```

Them dataclass:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ChildText:
    content: str
    page_start: int
    page_end: int
```

Function:

```python
def split_parent_chunk_to_child_texts_page_aware(
    parent_chunk: Chunk,
    *,
    child_chunk_size: int,
    child_chunk_overlap: int,
) -> list[ChildText]:
    page_blocks = split_body_by_page_markers(parent_chunk.content)
    child_texts: list[ChildText] = []

    for page_block in page_blocks:
        texts = recursive_splitter.split_text(page_block.content)
        for text in texts:
            if text.strip():
                child_texts.append(
                    ChildText(
                        content=text.strip(),
                        page_start=page_block.page_number,
                        page_end=page_block.page_number,
                    )
                )

    return child_texts
```

Neu parent content khong con marker nhung parent chi nam tren 1 page, co the fallback:

```python
ChildText(
    content=text.strip(),
    page_start=parent_chunk.page_start,
    page_end=parent_chunk.page_end,
)
```

Khong fallback im lang cho parent multi-page neu muon citation chinh xac. Neu parent multi-page ma khong co marker trong content, nen raise de sua chunker truoc.

---

## 8. Rule Normalize De Xuat

Rule chuyen plain heading thanh Markdown heading:

```text
Roman heading: I. II. III. IV. -> ##
Numbered heading cap 1: 1. 2. 3. -> ###
Letter heading: A/ B/ C/ hoac A. B. C. -> ####
Sub-number dang 1/ 2/ -> giu nguyen trong section truoc, tru khi tai lieu cho thay no la heading that.
```

Vi du:

```text
II. NHIỆM VỤ VÀ GIẢI PHÁP
```

Thanh:

```markdown
## II. NHIỆM VỤ VÀ GIẢI PHÁP
```

Vi du:

```text
2. Đổi mới nội dung, phương pháp và hình thức giáo dục
```

Thanh:

```markdown
### 2. Đổi mới nội dung, phương pháp và hình thức giáo dục
```

Vi du:

```text
A/ Nội dung:
```

Thanh:

```markdown
#### A/ Nội dung:
```

---

## 9. Guard De Tranh Convert Sai

Khong bien moi dong bat dau bang `1.` thanh heading.

Chi convert khi dong thoa cac dieu kien:

```text
Dong dung mot minh.
Khong phai bullet bat dau bang "- ".
Khong phai dong bang Markdown.
Khong nam trong fenced code block.
Do dai vua phai, vi du <= 160 ky tu.
Khong ket thuc bang dau "." neu do la cau van dai, tru pattern heading hanh chinh ro rang.
Dong sau thuong la paragraph, bullet list, hoac heading cap thap hon.
```

Nen uu tien precision hon recall:

```text
Convert it nhung dung tot hon convert nhieu ma sai.
```

---

## 10. Regex Goi Y

Dat regex trong `heading_normalizer.py`.

```python
import re

ROMAN_RE = re.compile(r"^(?P<num>[IVXLCDM]+)\.\s+(?P<title>.+)$")
NUMBER_RE = re.compile(r"^(?P<num>\d+)\.\s+(?P<title>.+)$")
LETTER_RE = re.compile(r"^(?P<num>[A-ZĐ])[/\.]\s*(?P<title>.+)$")

MAX_HEADING_LENGTH = 160
```

Helper:

```python
def is_probable_heading_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", "-", "|", "<!--")):
        return False
    if len(stripped) > MAX_HEADING_LENGTH:
        return False
    return True
```

Skeleton:

```python
def normalize_structural_headings(body: str) -> str:
    lines = body.splitlines()
    normalized: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            normalized.append(line)
            continue

        if in_code_block or not is_probable_heading_line(line):
            normalized.append(line)
            continue

        if ROMAN_RE.match(stripped):
            normalized.append(f"## {stripped}")
            continue

        if NUMBER_RE.match(stripped):
            normalized.append(f"### {stripped}")
            continue

        if LETTER_RE.match(stripped):
            normalized.append(f"#### {stripped}")
            continue

        normalized.append(line)

    return "\n".join(normalized)
```

Luu y:

```text
Skeleton tren la diem bat dau.
Khi test tren document that, neu convert sai thi them guard, khong nen bo het rule.
```

---

## 11. Vi Du Voi File 02_1470KHTH

Input dang plain text:

```text
#### B/ Hình thức:
...
2. Đổi mới nội dung, phương pháp và hình thức giáo dục
...
3. Nâng cao năng lực đội ngũ cán bộ, giảng viên
...
4. Tăng cường sự phối hợp giữa gia đình, nhà trường, xã hội
```

Sau normalize:

```markdown
#### B/ Hình thức:
...
### 2. Đổi mới nội dung, phương pháp và hình thức giáo dục
...
### 3. Nâng cao năng lực đội ngũ cán bộ, giảng viên
...
### 4. Tăng cường sự phối hợp giữa gia đình, nhà trường, xã hội
```

Ket qua mong doi:

```text
B/ Hinh thuc khong con gom het muc 2, 3, 4, 5, 6, 7.
Moi muc nghiep vu co parent chunk rieng.
heading_path cua child chunk dung ngu canh hon.
Page range cua section trai qua page marker phai dung, vi du A/ Noi dung page_start=1 page_end=2.
Embedding enriched text co "Muc: ... > 3. Nang cao..." nen search chinh xac hon.
```

---

## 12. Lien He Voi Guide 14/14A

Guide 14/14A khong nen sua logic OCR.

Truoc khi embed:

```text
chunk content phai co heading_path dung.
embedding_text phai enrich bang title + department + document_type + domain + heading_path + page.
```

Neu heading_path sai, embedding enriched text van thieu ngu canh dung.

Vi vay, heading normalizer la buoc can lam truoc khi danh gia chat luong retrieval 14A mot cach nghiem tuc.

Tuong tu, page-aware chunker la buoc can lam truoc khi danh gia citation. Neu 14A search dung nhung `page_start/page_end` sai, retrieval co the dung ve semantic nhung sai citation.

---

## 13. Checklist

- [ ] Tao `app/ingestion/parsing/heading_normalizer.py`.
- [ ] Tao/cap nhat `app/ingestion/parsing/page_blocks.py`.
- [ ] Co `normalize_structural_headings(body)`.
- [ ] Co `split_body_by_page_markers(body)`.
- [ ] Khong overwrite markdown goc.
- [ ] Khong xu ly trong OCR.
- [ ] Tach page block truoc khi split heading.
- [ ] Goi normalizer trong tung page block truoc `MarkdownHeaderTextSplitter`.
- [ ] Khong lam mat `<!-- page: n -->`.
- [ ] Co `active_heading_path` de page tiep theo ke thua heading neu khong lap lai heading.
- [ ] Merge adjacent `ParentSection` co cung `heading_path`.
- [ ] Test tren `02_1470KHTH_06-05-2024.md`.
- [ ] Cac muc `2.`, `3.`, `4.` trong section II tach thanh parent rieng.
- [ ] Cac muc `1.`, `2.`, `3.`, `4.` trong section IV tach thanh parent rieng.
- [ ] Section qua page marker co `page_start/page_end` dung, vi du `1-2`, `2-3`, `3-4`.
- [ ] Child chunk khong bi citation sai trang; neu parent multi-page thi uu tien page-aware child split.
- [ ] Chay lai chunk output va kiem tra `heading_path`.
- [ ] Chay lai chunk output va kiem tra `page_start/page_end`.
