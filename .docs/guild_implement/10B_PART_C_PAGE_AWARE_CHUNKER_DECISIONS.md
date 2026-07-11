# 10B. Part C - Hướng Dẫn Page-Aware Structural Chunker Decisions

**Last Updated:** 2026-07-10

File này chốt quyết định page-aware parent-child chunking sau guide 09A/10.

---

## 0. Flow Theo Dõi Nhanh

```text
Markdown body da validate tu markdown_reader
  -> page_markers.split_body_by_page_markers()
       - tao PageBlock(page_number, content)
       - khong tao page_blocks.py
  -> structural_parser.parse_page_blocks(PageBlock[])
       - chay dung mot lan trong chunk_markdown_body()
       - stateful theo source order, khong reset heading/item context khi doi page
       - tra StructuralParseResult(blocks, reports)
       - page marker da consume thanh PageBlock.page_number, khong thanh paragraph
       - fenced code block truoc
       - Markdown table truoc
       - Markdown heading truoc moi item regex
       - numbered_item / lettered_item / bullet_item / paragraph sau cung
  -> parent_chunker.build_parent_sections()
       - nhan parse_result.blocks, khong parse lai body
       - parent tao theo Markdown heading
       - ParentSection giu blocks cua section
       - content truoc heading dau tien vao document-root parent
       - page_start/page_end lay tu PageBlock va block range
       - heading_path cap nhat tu block_type="heading"
  -> khong merge Parent qua Markdown heading boundary
       - moi Markdown heading mo mot Parent moi
       - Parent cu dong ngay truoc heading tiep theo, bat ke heading level
  -> parent_chunker.make_parent_chunk()
       - chunk_type = parent
       - chunk_key = <version_key>::p::<0001>
       - parent_chunk_key = None
  -> child_chunker.build_child_units()
       - nhan ParentSection.blocks, khong parse lai parent_chunk.content
       - StructuralBlock boundary theo numbered_item / lettered_item / bullet_item
       - numbered/lettered tao Child rieng; bullet ngan lien ke co the gop khi cung heading_path/parent_item_key
       - table/code tao atomic Child rieng; paragraph gan theo ownership/context da chot
       - item_path, logical_item_key, parent_item_key va legal_unit_type duoc tinh truoc split
  -> child_chunker.make_child_chunks()
       - chunk_type = child
       - chunk_key = <version_key>::c::<0001>
       - parent_chunk_key = parent.chunk_key
       - heading_path ke thua parent
       - item_path ke thua structural context
  -> chunker.chunk_markdown_body()
       - dieu phoi tat ca buoc tren
       - chunk_index global sequential cho parent + child
       - tra ChunkingResult(parent_chunks, child_chunks, warnings, errors)
```

Rule cần nhớ:

```text
Markdown heading -> parent structure.
Dieu/Khoan/Diem/Bullet -> item structure va child boundary.
Khong convert 1., 2., a) thanh Markdown heading.
Khong demote Markdown heading co san thanh item.
Table/code chi parse truoc item regex va split o child layer.
RecursiveCharacterTextSplitter chi dung sau structural parsing cho item/paragraph dai. Table split theo row group; code dai split theo ranh gioi dong, moi split giu fence hop le va logical_code_key.
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
- ValidationReport
- StructuralParseResult
- parse_page_blocks()
- `_classify_line()`
- build_item_path()

chatbot/backend/app/ingestion/chunking/parent_chunker.py
- ParentSection
- build_parent_sections()
- khong dung merge_adjacent_parent_sections() trong normative flow; helper chi hop le cho continuation fragment ky thuat khong co heading boundary
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
- ChunkingResult
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
Gom tat ca structural blocks tu heading hien tai den truoc Markdown heading tiep theo, bat ke cap.
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

Parser nhận `PageBlock[]` đã tách sẵn. Trong từng `PageBlock`, order bắt buộc:

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

Page marker không đi vào `_classify_line()`: nó đã được consume thành `PageBlock.page_number`.
HTML comment khác không thành paragraph và không được đưa vào embedding.

Code/table/comment/paragraph da duoc outer loop xu ly truoc classifier.
`_classify_line()` chi nhan heading/item va tra
`tuple[StructuralBlock, ValidationReport | None]`. Implementation chuan, gom regex order,
`item_level`, `parent_item_key`, `item_path`, legal context va warning
`item_level_jump`, nam trong Guide 09A. Khong duy tri classifier thu hai tai file nay.

`MARKDOWN_HEADING_RE` phải chạy trước item regex.

Marker cần hỗ trợ:

```text
numbered_item: 1., 1), 1/, (1), 1.1., 1.1)
lettered_item: a., a), a/, A., A), A/
bullet_item: -, +, *
```

---

## 5. Legal Hierarchy

Mapping:

```text
Markdown heading "Điều ..." -> legal_unit_type = article
numbered_item / lettered_item / bullet_item -> legal_unit_type chi duoc gan khi nam trong legal context
paragraph / table / code -> legal_unit_type = none, hoac ke thua legal context da xac nhan
danh sach thong thuong -> legal_unit_type = none
```

Khong duoc suy ra `clause`/`point`/`bullet` chi tu hinh dang marker. `block_type` moi la truong
phan anh hinh thuc marker.

Hierarchy:

```text
Điều
└── Khoản
    └── Điểm
        └── Bullet
```

`item_path` ví dụ:

```text
["1. Hồ sơ gồm:", "a) Đơn đăng ký."]
```

Rule:

```text
item_path giu marker va nhan ngu nghia ngan lay tu dong item goc.
Khong chi luu ["1.", "a)"].
Khong sao chep toan bo noi dung dai cua item cha vao item_path.
Khong dung LLM de tom tat hoac tu sinh nhan.
logical_item_key, logical_item_keys va parent_item_key luu trong `Chunk.metadata` trong memory va truyen sang Qdrant payload.
Khong duoc noi PostgreSQL da persist cac field nay neu schema `document_chunks` chua co JSONB metadata.
Khong tao migration trong pham vi guide nay.
Khong tu tao migration.
```

Nếu item nhảy cấp, mất parent, hoặc page mới làm mất context, ghi ValidationReport warning/error tuy muc do.

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
StructuralBlock khong phai Chunk. numbered_item/lettered_item la ChildUnit rieng, ke ca item ngan hoac ket thuc bang ":".
Chi gop bullet ngan lien ke khi cung heading_path, parent_item_key va tong content khong vuot chunk_size.
Khong gop numbered/lettered; khong gop bullet khac parent, qua table/code/paragraph/heading.
Bullet group giu logical_item_keys cua tat ca bullet thanh vien.
Item cha co item con van tao Child rieng.
Item con tao Child rieng va link ve item cha bang parent_item_key.
Item cha dong thoi lam context cho item con trong embedding_text co gioi han.
Child item cha khong chua noi dung item con.
Paragraph sau item gan vao item hien tai.
Paragraph dung khi gap heading moi hoac bat ky item moi.
Neu item moi co cap thap hon thi item do thanh item con.
Page marker khong lam ket thuc item hoac lam mat item_path.
Paragraph khong thuoc item nao tao paragraph Child trong Parent hien tai.
Neu paragraph khong ro thuoc item cuoi hay item cha, dung fallback bao thu va ghi ValidationReport warning/error tuy muc do.
```

Item quá dài:

```text
Chi split ben trong item do.
Giu logical_item_key, parent_item_key, item_path, legal_unit_type, heading_path.
Gan split_index va split_count.
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
Code block nho giu nguyen; code dai split theo ranh gioi dong, moi split giu opening/closing fence hop le, cung logical_code_key va split_index/split_count.
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
logical_item_key
logical_item_keys
parent_item_key
split_index
split_count
```

Có thể giữ thêm trong JSON metadata:

```text
raw_content
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
item_path va nhan cac item cha co gioi han
legal_unit_type
raw child content
```

Không đưa page marker vào embedding text.
Không đưa HTML comment kỹ thuật khác vào embedding text.
Không thêm thông tin suy diễn, không tự tóm tắt. Raw content của Child giữ nguyên.

---

## 10. Tests Cần Có

- [ ] Danh sách 5 numbered/lettered item dưới một heading tạo 1 parent và 5 child.
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
- [ ] Item con có `parent_item_key`.
- [ ] `item_path` giữ marker và nhãn ngắn, không chỉ lưu marker.
- [ ] Mỗi bullet tạo StructuralBlock; bullet ngắn đủ điều kiện có thể gộp Child và giữ `logical_item_keys`.
- [ ] Item quá dài chỉ split nội bộ và giữ `logical_item_key`.
- [ ] Split child có `split_index` và `split_count`.
- [ ] Không Child chứa hai numbered/lettered item hoặc bullet khác parent; bullet group hợp lệ là ngoại lệ.
- [ ] Marker trong table không bị parse thành item.
- [ ] Marker trong fenced code không bị parse thành item.
- [ ] Nội dung trước heading đầu tiên thuộc `document-root` parent.
- [ ] Table/code trong item kế thừa đúng context.
- [ ] Child ngắn có `embedding_text` chứa context thật.
- [ ] Paragraph không rõ parent xuất ValidationReport warning.
- [ ] Item qua page mới vẫn giữ đúng `item_path`.
- [ ] Page marker không bị đưa vào embedding text.
- [ ] HTML comment kỹ thuật khác không bị đưa vào embedding text.

## 13. Parent Context, Heading-Only Content Và Heading Kép

```text
Mỗi Markdown heading mở một Parent mới; không merge Parent qua heading boundary.
Parent không có body nhưng heading chứa mệnh đề độc lập phải tạo heading_content Child nguyên văn.
Heading thuần context như "Chương I", "Phần II", "Mục 1" có thể đánh dấu context_only.
Mỗi Parent phải có ít nhất một Child hoặc có context_only_reason rõ ràng.
```

Với cặp heading liên tiếp cùng cấp:

```markdown
### Chương I
### NHỮNG VẤN ĐỀ CHUNG
```

nếu heading đầu là nhãn cấu trúc và không có body ở giữa, derived `heading_path` của descendant phải giữ:

```text
Chương I — NHỮNG VẤN ĐỀ CHUNG
```

Không sửa raw Markdown. Nếu không chắc, emit `heading_context` warning thay vì âm thầm đoán.
