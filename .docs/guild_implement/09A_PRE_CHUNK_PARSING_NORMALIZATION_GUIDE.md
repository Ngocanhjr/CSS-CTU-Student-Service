# 09A. Hướng Dẫn Pre-Chunk Structural Parsing

**Last Updated:** 2026-07-10

File này bổ sung cho guide 09/10. Bước này chạy sau markdown reader và trước parent/child chunker.

Mục tiêu:

```text
Khong sua Markdown nguon.
Giu raw OCR/Markdown de audit.
Xu ly page marker truoc structural parsing.
Nhan dien heading/table/code/item theo thu tu on dinh.
Tao representation trung gian de parent/child chunker dung chung.
```

---

## 1. Quyết Định Chốt

Không convert item như `1.`, `2.`, `a)` thành Markdown heading.

Mô hình thống nhất:

```text
Markdown heading -> cau truc parent
Dieu/Khoan/Diem/Bullet -> cau truc item va ranh gioi child
```

Flow chốt:

```text
MarkdownDocument.body
  -> page_markers.split_body_by_page_markers()
  -> structural_parser.parse_page_blocks(PageBlock[])
       1. page marker da consume truoc parser
       2. fenced code block
       3. Markdown table
       4. Markdown heading
       5. numbered_item
       6. lettered_item
       7. bullet_item
       8. paragraph
  -> parent_chunker build parent theo Markdown heading
  -> child_chunker build child theo item/table/code/paragraph boundary
  -> embedding_text enrich bang heading_path + item_path
```

Page marker đã được consume thành `PageBlock.page_number`, không tạo `StructuralBlock`
và không được phân loại thành `paragraph`.
HTML comment khác cũng không được phân loại thành paragraph và không được đưa vào embedding.

Hard rule:

```text
Dong da bat dau bang Markdown heading marker (#, ##, ###, ####, ...)
luon la block_type = "heading".
Khong demote thanh numbered_item, lettered_item, bullet_item.
Item regex chi chay tren dong khong co Markdown heading marker.
```

Ví dụ:

```text
### 1. Muc dich       -> heading
1. Muc dich           -> numbered_item

### a) Doi tuong      -> heading
a) Doi tuong          -> lettered_item

### - Noi dung        -> heading
- Noi dung            -> bullet_item
```

---

## 2. File Cần Tạo/Sửa

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
chatbot/backend/app/ingestion/parsing/structural_parser.py
chatbot/backend/app/ingestion/chunking/parent_chunker.py
chatbot/backend/app/ingestion/chunking/child_chunker.py
chatbot/backend/app/ingestion/chunking/table_blocks.py
chatbot/backend/app/ingestion/chunking/chunker.py
chatbot/backend/test/ingestion/test_structural_parser.py
chatbot/backend/test/ingestion/test_chunker.py
```

Không tạo:

```text
page_blocks.py
module rieng chi de bien item thanh heading
```

`PageBlock` và `split_body_by_page_markers()` nằm trong `page_markers.py`.

### Code placement: `parse_page_blocks()`

`parse_page_blocks()` nằm trong `backend/app/ingestion/parsing/structural_parser.py`.
Hàm này là entrypoint của structural parser.

Input là `list[PageBlock]`. `PageBlock` được tạo bởi
`split_body_by_page_markers()` trong `backend/app/ingestion/parsing/page_markers.py`.

Output là `StructuralParseResult`, gồm:

```python
blocks: list[StructuralBlock]
reports: list[ValidationReport]
```

Flow sử dụng:

```python
page_blocks = split_body_by_page_markers(markdown_body)
parse_result = parse_page_blocks(page_blocks)
```

Trách nhiệm của `parse_page_blocks()`:

1. Duyệt `PageBlock[]` theo thứ tự gốc.
2. Không tạo block cho page marker vì page marker đã thành `PageBlock.page_number`.
3. Không reset `heading_path` và `item_path` khi đổi trang.
4. Nhận diện block theo đúng thứ tự: fenced code block, Markdown table,
   Markdown heading, numbered item, lettered item, bullet item, paragraph.
5. Tạo `StructuralBlock` cho mỗi block nội dung.
6. Tạo `ValidationReport` khi gặp cấu trúc mơ hồ hoặc lỗi.

Không đặt `parse_page_blocks()` trong `page_markers.py`, `parent_chunker.py`,
`child_chunker.py`, hoặc `chunker.py`.

### Implementation guide: `parse_page_blocks()`

Trong `structural_parser.py`, implement theo thứ tự nhỏ nhất:

1. Khai báo regex ở đầu file.
2. Khai báo `StructuralBlock`, `ValidationReport`, `StructuralParseResult`.
3. Viết helper nhận diện block atomic: fenced code, table.
4. Viết helper classify một dòng thường: heading, numbered item, lettered item,
   bullet item, paragraph.
5. Viết `parse_page_blocks()` giữ state qua toàn bộ tài liệu.

Suggested pattern:

```python
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
NUMBERED_ITEM_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[.)/])\s+(.+)$")
LETTERED_ITEM_RE = re.compile(r"^([A-Za-zĐđ][.)/])\s+(.+)$")
BULLET_ITEM_RE = re.compile(r"^([-+*])\s+(.+)$")
HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
```

Skeleton:

```python
def parse_page_blocks(page_blocks: list[PageBlock]) -> StructuralParseResult:
    blocks: list[StructuralBlock] = []
    reports: list[ValidationReport] = []
    heading_stack: list[tuple[int, str]] = []
    item_stack: list[StructuralBlock] = []
    source_order = 0

    # Flatten once so atomic code/table and paragraphs may cross a page boundary.
    lines = [
        (page_block.page_number, line)
        for page_block in page_blocks
        for line in page_block.content.splitlines()
    ]
    index = 0

    while index < len(lines):
        page_number, line = lines[index]
        stripped = line.strip()

        if not stripped or HTML_COMMENT_RE.match(stripped):
            index += 1
            continue

        # 1. fenced code block
        if stripped.startswith("```"):
            raw_content, page_start, page_end, index, report = _consume_fenced_code(lines, index)
            blocks.append(_make_code_block(raw_content, page_start, page_end, source_order, heading_stack, item_stack))
            if report is not None:
                reports.append(report)
            source_order += 1
            continue

        # 2. Markdown table
        if _looks_like_table_start(lines, index):
            raw_content, page_start, page_end, index = _consume_table(lines, index)
            blocks.append(_make_table_block(raw_content, page_start, page_end, source_order, heading_stack, item_stack))
            source_order += 1
            continue

        # A paragraph is adjacent nonblank text, not one block per OCR line.
        if not _starts_structural_block(lines, index):
            raw_content, page_start, page_end, index = _consume_paragraph(lines, index)
            block, report = _make_paragraph_block(
                raw_content, page_start, page_end, source_order, heading_stack, item_stack
            )
            blocks.append(block)
            if report is not None:
                reports.append(report)
            source_order += 1
            continue

        # 3-7. line-level classification
        block, report = _classify_line(
            stripped,
            page_number,
            source_order,
            heading_stack,
            item_stack,
        )
        blocks.append(block)
        if report is not None:
            reports.append(report)

        _update_state(block, heading_stack, item_stack)
        source_order += 1
        index += 1

    return StructuralParseResult(blocks=blocks, reports=reports)
```

Helper contract cần chốt:

```text
`lines` la list[(page_number, line)] theo source order; khong reset state khi page_number doi.
`_consume_fenced_code()` doc den closing ``` ke ca qua trang. Khong co closing fence: emit
code block den EOF va report error `unclosed_code_fence`.
`_looks_like_table_start()` chi true khi current line va separator line ke tiep tao Markdown table hop le.
`_consume_table()` doc cac row lien tiep, cho phep page_number doi; dung tai blank line hoac non-table line.
`_consume_paragraph()` gom cac dong nonblank lien tiep den heading/item/table/code/HTML comment/blank.
`page_start/page_end` cua block atomic/paragraph la min/max page da consume.
```

`_classify_line()` phải check theo đúng thứ tự:

```python
heading_match = MARKDOWN_HEADING_RE.match(line)
if heading_match:
    return _make_heading_block(...), None

numbered_match = NUMBERED_ITEM_RE.match(line)
if numbered_match:
    return _make_numbered_item_block(...), None

lettered_match = LETTERED_ITEM_RE.match(line)
if lettered_match:
    return _make_lettered_item_block(...), None

bullet_match = BULLET_ITEM_RE.match(line)
if bullet_match:
    return _make_bullet_item_block(...), None

return _make_paragraph_block(...), maybe_ambiguous_owner_report(...)
```

State update rule:

```text
heading block:
  - pop heading_stack cho toi khi top_level < heading_level
  - push (heading_level, heading_text)
  - clear item_stack

item block:
  - `item_level` la depth structural, khong phai legal_unit_type:
    numbered `1.` = 1, `1.1.` = 2; lettered/bullet = parent depth + 1 neu co parent,
    nguoc lai = 1
  - pop item_stack cho toi parent item dung cap
  - parent_item_key = item_stack[-1].logical_item_key neu co parent
  - push item hien tai

paragraph/table/code block:
  - khong doi heading_stack
  - khong doi item_stack
  - ke thua heading_path va item_path hien tai
```

Key va report toi thieu:

```text
Parser tao key deterministic tu source_order: `item:000001`, `table:000002`, `code:000003`.
Chunker chi copy key nay; khong tao lai key sau khi split.
`item_level_jump` va `ambiguous_paragraph_owner` la warning.
`unclosed_code_fence` la error.
Duplicate logical key va split boundary la error o child/chunker layer, khong phai parser line-level.
```

Lazy rule:

```text
Dung helper nho, khong tao class parser rieng trong MVP.
Chi tao class ParserState neu tham so helper bat dau qua dai hoac test kho doc.
```

---

## 3. Data Structures

Suggested pattern:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StructuralBlock:
    block_type: str  # heading | numbered_item | lettered_item | bullet_item | paragraph | table | code
    raw_content: str
    page_start: int
    page_end: int
    source_order: int
    heading_path: list[str] = field(default_factory=list)
    heading_level: int | None = None
    heading_text: str | None = None
    item_marker: str | None = None
    item_level: int | None = None
    item_path: list[str] = field(default_factory=list)
    logical_item_key: str | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    legal_unit_type: str = "none"  # article | clause | point | bullet | none
    confidence: float = 1.0
```

Validation report:

```python
@dataclass(frozen=True)
class ValidationReport:
    severity: str  # warning | error
    code: str
    reason: str
    page: int
    raw_content: str
    current_heading_path: list[str]
    current_item_path: list[str]
    selected_owner: list[str] | None
    candidate_owners: list[list[str]]
    candidate_types: list[str]
    selected_type: str | None
    confidence: float
    file: str | None = None
```

Parse result:

```python
@dataclass(frozen=True)
class StructuralParseResult:
    blocks: list[StructuralBlock]
    reports: list[ValidationReport] = field(default_factory=list)
```

---

## 4. Parser Order

Parser nhận `PageBlock[]` đã tách sẵn và chạy stateful đúng một lần theo source order.
Không reset heading/item context khi đổi trang. Trong từng `PageBlock`, parser chạy theo thứ tự:

```text
1. page marker da consume truoc parser
2. fenced code block
3. Markdown table
4. Markdown heading
5. numbered_item
6. lettered_item
7. bullet_item
8. paragraph
```

Lý do:

```text
Page marker da thanh PageBlock.page_number, khong thanh StructuralBlock.
HTML comment khac bi bo qua hoac tao non-embedding technical block, khong thanh paragraph.
Marker nhu 1. hoac a) trong table/code khong duoc parse thanh item.
Markdown heading phai thang item regex.
Paragraph chi la fallback cuoi cung.
```

---

## 5. Block Classification Rules

Markdown heading:

```python
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
```

Nếu match, luôn tạo:

```python
block_type = "heading"
heading_level = len(match.group(1))
heading_text = match.group(2).strip()
legal_unit_type = "article" nếu heading_text bắt đầu bằng "Điều "
```

Item regex chỉ chạy khi line không phải heading/table/code/comment/page marker.

Suggested pattern:

```python
NUMBERED_ITEM_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[.)/])\s+(.+)$")
LETTERED_ITEM_RE = re.compile(r"^([A-Za-zĐđ][.)/])\s+(.+)$")
BULLET_ITEM_RE = re.compile(r"^([-+*])\s+(.+)$")
```

Marker cần hỗ trợ:

```text
numbered_item: 1., 1), 1/, (1), 1.1., 1.1)
lettered_item: a., a), a/, A., A), A/
bullet_item: -, +, *
```

Mapping block type và legal unit phải tách biệt:

```text
Markdown heading "Điều ..." -> block_type = heading; legal_unit_type = article
1., 2., 1.1.              -> block_type = numbered_item
a), b), A.                -> block_type = lettered_item
-, +, *                   -> block_type = bullet_item
```

`legal_unit_type` không được suy ra chỉ từ marker. Chỉ gán `clause`, `point`,
`bullet` khi item nằm trong legal context đã được xác nhận, ví dụ ancestor heading
`Điều ...` hoặc structural ancestor pháp lý. Danh sách thông thường dùng
`legal_unit_type = none`.

---

## 6. Legal Hierarchy Và item_path

Cấu trúc:

```text
Điều
└── Khoản
    └── Điểm
        └── Gạch đầu dòng
```

Rule:

```text
Item con ke thua item_path cua item cha.
Item cung cap dong item truoc do.
Item cap cao hon dong cac item con ben duoi.
Neu marker nhay cap bat thuong, ghi ValidationReport warning/error tuy muc do.
```

Ví dụ:

```text
1. Hồ sơ gồm:
a) Đơn đăng ký.
b) Bản sao căn cước.
```

Child metadata:

```text
item_path = ["1. Hồ sơ gồm:", "a) Đơn đăng ký."]
legal_unit_type = point  # chi khi legal context da xac nhan
logical_item_key = stable key cua item hien tai
parent_item_key = stable key cua item cha neu co
```

`item_path` phải lấy từ dòng item gốc:

```text
Giu marker.
Bo marker khi tao semantic label noi bo neu can, nhung output item_path van giu marker + nhan ngan.
Giu noi dung goc, co the gioi han do dai.
Khong dung LLM de tom tat hoac tu sinh nhan.
Khong chi luu ["1.", "a)"].
Khong sao chep toan bo noi dung dai cua item cha vao item_path.
```

---

## 7. Parent Và Child Boundary

Parent:

```text
Tao theo Markdown heading.
Noi dung truoc heading dau tien thuoc document-root parent.
Parent giu full section, heading_path, page_start, page_end.
Parent khong embed trong MVP.
```

Child:

```text
numbered_item, lettered_item, bullet_item luon tao it nhat mot Child rieng.
Moi Child deu duoc embedding, ke ca item ngan hoac item ket thuc bang ":".
Khong gop noi dung cua hai item khac nhau de dat child_chunk_size.
RecursiveCharacterTextSplitter chi chay sau structural parsing.
Neu item qua dai, split ben trong item do va giu logical_item_key, parent_item_key, item_path.
Item cha co item con van tao Child rieng.
Item con tao Child rieng va link ve item cha bang parent_item_key.
Child item cha khong chua noi dung item con.
```

Paragraph sau item:

```text
Gan vao Child item hien tai.
Dung khi gap heading moi hoac bat ky item moi.
Neu item moi co cap thap hon thi item do thanh item con.
Page marker khong lam ket thuc item va khong lam mat item_path.
Neu paragraph khong thuoc item nao, tao paragraph Child trong Parent hien tai.
Neu paragraph sau danh sach khong ro thuoc item cuoi hay item cha, dung fallback bao thu va ghi ValidationReport warning/error tuy muc do.
Khong am tham gan sai.
```

Item/paragraph quá dài:

```text
Chi split ben trong chinh don vi do.
Khong split sang item ke tiep.
Moi phan split dung chung logical_item_key.
Giu cung heading_path, item_path, parent_item_key.
Gan split_index va split_count trong metadata.
```

---

## 8. Table Và Code

Rule:

```text
Table va fenced code duoc nhan dien truoc item regex.
Marker 1. hoac a) trong table/code khong parse thanh item.
Table/code nam trong item ke thua heading_path, item_path va parent_item_key.
Table va fenced code luon tao atomic Child rieng, khong append vao raw content cua Child item.
Truoc khi emit table/code Child, flush Child item hien tai nhung giu item stack de ke thua context.
Table ngan giu nguyen.
Table dai split theo row group, lap lai header + separator va khong cat giua row.
Code block nho giu nguyen. Code block dai split theo ranh gioi dong; moi split giu opening/closing fence hop le, cung logical_code_key va split_index/split_count. Khong cat bang generic recursive splitter.
```

Table chỉ xử lý ở child layer vì parent phải giữ full section.

---

## 9. Embedding Preparation

Raw child content giữ nguyên.

`embedding_text` được tạo thêm, không ghi đè raw content:

```text
heading_path
ancestor item labels = item_path[:-1]
limited parent item context neu Child con qua ngan
legal_unit_type
raw child content
```

Không thêm thông tin suy diễn. Không tự tóm tắt. Context prepend cho child quá ngắn chỉ lấy
nguyên văn có giới hạn từ `heading_path` và nhãn các item cha; raw content của Child giữ nguyên.

Ví dụ:

```text
Raw:
a) Don dang ky.

Embedding text:
Dieu kien ho so > Khoan 1. Ho so gom > Diem a) Don dang ky.
```

Page marker và HTML comment kỹ thuật khác không được đưa vào `embedding_text`.

---

## 10. Tests Bắt Buộc

- [ ] Danh sách 5 mục dưới một heading tạo 1 parent và 5 child.
- [ ] Item không bị convert thành heading.
- [ ] `### 1. Mục đích` vẫn là heading.
- [ ] `### 1) Phạm vi` vẫn là heading.
- [ ] `### a) Đối tượng` vẫn là heading.
- [ ] `### - Nội dung` vẫn là heading.
- [ ] Markdown heading không bị demote thành item.
- [ ] Điều -> Khoản -> Điểm -> Bullet tạo đúng `item_path`.
- [ ] Paragraph được gắn đúng item hoặc sinh ValidationReport warning.
- [ ] Item con kế thừa context cha.
- [ ] Item cha kết thúc bằng `:` vẫn tạo child riêng.
- [ ] Item cha có item con không chứa nội dung item con.
- [ ] Item con có `parent_item_key` trỏ về item cha.
- [ ] `item_path` giữ marker và nhãn ngắn, không chỉ lưu marker.
- [ ] Bullet `-`, `+`, `*` tạo atomic child.
- [ ] Item quá dài chỉ split nội bộ và giữ `logical_item_key`.
- [ ] Split child có `split_index` và `split_count`.
- [ ] Không child nào chứa nội dung của hai item khác nhau.
- [ ] Marker trong table/code không bị parse thành item.
- [ ] Nội dung trước heading đầu tiên thuộc `document-root` parent.
- [ ] Table/code trong item kế thừa đúng context.
- [ ] Child ngắn có `embedding_text` chứa context thật.
- [ ] Page marker không bị đưa vào `embedding_text`.
- [ ] HTML comment kỹ thuật khác không bị đưa vào `embedding_text`.
- [ ] Paragraph nhiều dòng tạo một `StructuralBlock` và giữ đúng page range.
- [ ] Fenced code/table qua page tạo đúng một block atomic với `page_start/page_end`.
- [ ] Fenced code không đóng tạo `unclosed_code_fence` error.
- [ ] `logical_item_key`, `logical_table_key`, `logical_code_key` deterministic theo `source_order`.

---

## 11. Done Khi

- [ ] Không còn logic convert `1.`, `a)` thành Markdown heading.
- [ ] Có structural block parser.
- [ ] Markdown heading được nhận diện trước item regex.
- [ ] Parent chunker chỉ dựa trên Markdown heading.
- [ ] Child chunker dựa trên structural item/table/code/paragraph boundary.
- [ ] Ambiguous cases có report.
- [ ] Tests parser/chunker pass.

## 11. Validation Severity Và Canonical Markdown Warning

`ValidationReport` phải có tối thiểu:

```text
severity: warning | error
code
reason
page
selected_owner
candidate_owners
```

```text
warning không tự động chặn publish.
error mới chặn publish theo mặc định.
paragraph ownership mơ hồ, heading context kép và heading dài bất thường là warning.
missing page range, duplicate logical_item_key, child thiếu parent_chunk_key hoặc split phá boundary là error.
```

Markdown heading có sẵn vẫn luôn là heading. Parser không tự demote heading sai, nhưng phải tạo
`canonical_markdown_warning` cho heading quá dài, nhiều câu, level bất thường, hai heading cùng cấp
liên tiếp không có body hoặc Parent không có Child.
