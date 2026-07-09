# 10B. Part C - Hướng Dẫn Page-Aware Structural Chunker Decisions

**Last Updated:** 2026-07-09

File này chốt quyết định page-aware parent-child chunking sau guide 09A/10.

---

## 0. Flow Theo Dõi Nhanh

```text
Markdown body da validate tu markdown_reader
  -> page_markers.split_body_by_page_markers()
       - tao PageBlock(page_number, content)
       - khong tao page_blocks.py
  -> structural_parser.parse_structural_blocks() tung PageBlock
       - fenced code block truoc
       - Markdown table truoc
       - Markdown heading truoc moi item regex
       - numbered_item / lettered_item / bullet_item / paragraph sau cung
  -> parent_chunker.build_parent_sections()
       - parent tao theo Markdown heading
       - content truoc heading dau tien vao document-root parent
       - page_start/page_end lay tu PageBlock va block range
       - heading_path cap nhat tu block_type="heading"
  -> parent_chunker.merge_adjacent_parent_sections()
       - gop section lien ke cung heading_path
       - giu page_start dau va page_end cuoi
  -> parent_chunker.make_parent_chunk()
       - chunk_type = parent
       - chunk_key = <version_key>::p::<0001>
       - parent_chunk_key = None
  -> child_chunker.build_child_units()
       - child boundary theo numbered_item / lettered_item / bullet_item
       - table/code/paragraph gan vao item/context dung
       - item_path va legal_unit_type duoc tinh truoc split
  -> child_chunker.make_child_chunks()
       - chunk_type = child
       - chunk_key = <version_key>::c::<0001>
       - parent_chunk_key = parent.chunk_key
       - heading_path ke thua parent
       - item_path ke thua structural context
  -> chunker.chunk_markdown_body()
       - dieu phoi tat ca buoc tren
       - chunk_index global sequential cho parent + child
```

Rule cần nhớ:

```text
Markdown heading -> parent structure.
Dieu/Khoan/Diem/Bullet -> item structure va child boundary.
Khong convert 1., 2., a) thanh Markdown heading.
Khong demote Markdown heading co san thanh item.
Table/code chi parse truoc item regex va split o child layer.
RecursiveCharacterTextSplitter chi dung sau structural parsing, trong mot item/paragraph/table/code dai.
```

---

## 1. File Layout

```text
chatbot/backend/app/ingestion/parsing/page_markers.py
- PAGE_RE
- PageBlock
- extract_page_numbers()
- extract_page_range()
- require_page_range()
- split_body_by_page_markers()

chatbot/backend/app/ingestion/parsing/structural_parser.py
- StructuralBlock
- AmbiguousBlockReport
- parse_structural_blocks()
- classify_line()
- build_item_path()

chatbot/backend/app/ingestion/chunking/parent_chunker.py
- ParentSection
- build_parent_sections()
- merge_adjacent_parent_sections()
- make_parent_chunk()

chatbot/backend/app/ingestion/chunking/child_chunker.py
- ChildUnit
- build_child_units()
- split_long_child_unit()
- make_child_chunks()

chatbot/backend/app/ingestion/chunking/table_blocks.py
- detect Markdown table
- split large table by row group

chatbot/backend/app/ingestion/chunking/chunker.py
- orchestration only

chatbot/backend/test/ingestion/test_structural_parser.py
chatbot/backend/test/ingestion/test_chunker.py
```

Không tạo:

```text
page_blocks.py
logic convert item thanh heading
logic parent chunk dua tren numbered_item/lettered_item
```

---

## 2. Vấn Đề Cần Xử Lý

Nếu split heading toàn document trước page marker, marker page mới có thể dính vào section cũ.

Nếu convert `1.`, `a)` thành Markdown heading, parent bị sai: item con trở thành parent mới.

Kết quả đúng:

```text
Page marker quyet dinh page range.
Markdown heading quyet dinh parent.
Item marker quyet dinh child boundary.
```

---

## 3. Page-Aware Parent Section

Parent section chỉ tạo từ Markdown heading.

Hard rule:

```text
### 1. Muc dich  -> heading, tao/cap nhat parent heading_path
1. Muc dich      -> numbered_item, khong tao parent

### a) Doi tuong -> heading
a) Doi tuong     -> lettered_item

### - Noi dung   -> heading
- Noi dung       -> bullet_item
```

Parent content:

```text
Gom tat ca structural blocks tu heading hien tai den truoc heading cung/higher level tiep theo.
Noi dung truoc heading dau tien thuoc document-root parent.
```

Page range:

```text
page_start = min page cua cac block trong parent
page_end = max page cua cac block trong parent
```

Không lấy page range bằng cách đoán marker sau khi heading splitter đã cắt text.

---

## 4. Structural Block Parser

Parser order bắt buộc:

```text
1. page marker
2. fenced code block
3. Markdown table
4. Markdown heading
5. numbered_item
6. lettered_item
7. bullet_item
8. paragraph
```

Suggested classification:

```python
def classify_line(line: str, *, in_code: bool, in_table: bool) -> str:
    if in_code:
        return "code"
    if in_table:
        return "table"
    if is_page_marker(line) or is_html_comment(line):
        return "paragraph"
    if MARKDOWN_HEADING_RE.match(line):
        return "heading"
    if NUMBERED_ITEM_RE.match(line):
        return "numbered_item"
    if LETTERED_ITEM_RE.match(line):
        return "lettered_item"
    if BULLET_ITEM_RE.match(line):
        return "bullet_item"
    return "paragraph"
```

`MARKDOWN_HEADING_RE` phải chạy trước item regex.

---

## 5. Legal Hierarchy

Mapping:

```text
Markdown heading "Điều ..." -> legal_unit_type = article
numbered_item              -> legal_unit_type = clause
lettered_item              -> legal_unit_type = point
bullet_item                -> legal_unit_type = bullet
paragraph/table/code       -> legal_unit_type = none, hoac ke thua context item
```

Hierarchy:

```text
Điều
└── Khoản
    └── Điểm
        └── Bullet
```

`item_path` ví dụ:

```text
["Điều 18", "Khoản 2", "Điểm c)", "Bullet 1"]
```

Nếu item nhảy cấp, mất parent, hoặc page mới làm mất context, ghi ambiguous report.

---

## 6. Child Chunk Boundary

Atomic boundary:

```text
numbered_item
lettered_item
bullet_item
```

Rule:

```text
Moi item la mot child unit rieng neu co noi dung doc lap.
Khong gop hai item khac nhau de dat chunk_size.
Item cha ket thuc bang ":" va chi dan vao item con thi chi lam context, khong tao child rong.
Paragraph sau item gan vao item hien tai neu ro rang tiep tuc item.
Neu paragraph khong ro parent, ghi ambiguous report.
```

Item quá dài:

```text
Chi split ben trong item do.
Giu item_path, legal_unit_type, heading_path.
Overlap chi trong pham vi item hien tai.
```

---

## 7. Table Và Code

Table/code phải được nhận diện trước item regex.

Rule:

```text
Marker 1. hoac a) trong table/code khong parse thanh item.
Table/code nam trong item thi ke thua item_path.
Table ngan giu nguyen thanh mot child unit.
Table dai split theo row group, moi chunk lap lai header + separator.
Code block giu nguyen hoac split bang logic rieng, khong cat vo nghia.
```

Table chỉ xử lý ở child layer. Parent vẫn giữ full section.

---

## 8. Child Metadata

Mỗi child cần giữ:

```text
heading_path
item_marker
item_level
item_path
legal_unit_type
page_start
page_end
parent_chunk_key
block_type
```

Có thể giữ thêm trong JSON metadata:

```text
raw_text
embedding_text
split_index
split_count
source_url
```

Không đổi schema DB nếu metadata có thể lưu JSON.

---

## 9. Embedding Text

Raw child content giữ nguyên.

`embedding_text` tạo từ context thật:

```text
heading_path
item_path
legal_unit_type
raw child content
```

Không đưa page marker vào embedding text.
Không thêm thông tin suy diễn.

---

## 10. Tests Cần Có

- [ ] Danh sách 5 mục dưới một heading tạo 1 parent và 5 child.
- [ ] Item không bị convert thành heading.
- [ ] `### 1. Mục đích` vẫn là heading.
- [ ] `### 1) Phạm vi` vẫn là heading.
- [ ] `### a) Đối tượng` vẫn là heading.
- [ ] `### - Nội dung` vẫn là heading.
- [ ] Markdown heading không bị demote thành item.
- [ ] Điều -> Khoản -> Điểm -> Bullet tạo đúng `item_path`.
- [ ] Paragraph được gắn đúng item hoặc sinh ambiguous report.
- [ ] Item con kế thừa context cha.
- [ ] Item cha kết thúc bằng `:` không tạo child rỗng.
- [ ] Bullet `-`, `+`, `*` tạo atomic child.
- [ ] Item quá dài chỉ split nội bộ.
- [ ] Không child nào chứa nội dung của hai item khác nhau.
- [ ] Marker trong table không bị parse thành item.
- [ ] Marker trong fenced code không bị parse thành item.
- [ ] Nội dung trước heading đầu tiên thuộc `document-root` parent.
- [ ] Table/code trong item kế thừa đúng context.
- [ ] Child ngắn có `embedding_text` chứa context thật.
- [ ] Paragraph không rõ parent xuất ambiguous report.
- [ ] Item qua page mới vẫn giữ đúng `item_path`.
- [ ] Page marker không bị đưa vào embedding text.
