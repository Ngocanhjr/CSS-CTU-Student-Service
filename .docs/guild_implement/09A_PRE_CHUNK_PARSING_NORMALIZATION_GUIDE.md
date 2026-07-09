# 09A. Hướng Dẫn Pre-Chunk Structural Parsing

**Last Updated:** 2026-07-09

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
  -> structural_parser.parse_structural_blocks() tung PageBlock
       1. page marker
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

---

## 3. Data Structures

Suggested pattern:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StructuralBlock:
    block_type: str  # heading | numbered_item | lettered_item | bullet_item | paragraph | table | code
    raw_text: str
    page_start: int
    page_end: int
    heading_level: int | None = None
    heading_text: str | None = None
    item_marker: str | None = None
    item_level: int | None = None
    item_path: list[str] = field(default_factory=list)
    legal_unit_type: str = "none"  # article | clause | point | bullet | none
    confidence: float = 1.0
```

Ambiguous report:

```python
@dataclass(frozen=True)
class AmbiguousBlockReport:
    file: str | None
    page: int
    raw_text: str
    current_heading_path: list[str]
    current_item_path: list[str]
    candidate_parent: list[str]
    selected_parent: list[str] | None
    candidate_types: list[str]
    selected_type: str | None
    reason: str
    confidence: float
```

---

## 4. Parser Order

Parser phải chạy theo thứ tự:

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

Lý do:

```text
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
NUMBERED_ITEM_RE = re.compile(r"^(\(?\d+(?:\.\d+)*[\.\)/]?)\s+(.+)$")
LETTERED_ITEM_RE = re.compile(r"^([A-Za-zĐđ][\.\)/])\s+(.+)$")
BULLET_ITEM_RE = re.compile(r"^([-+*])\s+(.+)$")
```

Mapping:

```text
Dieu trong Markdown heading -> legal_unit_type = article
1., 2., 1.1.             -> numbered_item, legal_unit_type = clause
a), b), A.               -> lettered_item, legal_unit_type = point
-, +, *                  -> bullet_item, legal_unit_type = bullet
Khac                     -> legal_unit_type = none
```

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
Neu marker nhay cap bat thuong, ghi ambiguous report.
```

Ví dụ:

```text
1. Hồ sơ gồm:
a) Đơn đăng ký.
b) Bản sao căn cước.
```

Child metadata:

```text
item_path = ["Khoản 1. Hồ sơ gồm", "Điểm a) Đơn đăng ký"]
legal_unit_type = point
```

Item cha kết thúc bằng `:` và chỉ dẫn vào item con:

```text
Dung lam context.
Khong tao child rong.
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
numbered_item, lettered_item, bullet_item la atomic child boundary.
Khong gop noi dung cua hai item khac nhau de dat child_chunk_size.
RecursiveCharacterTextSplitter chi chay sau structural parsing.
Neu item qua dai, split ben trong item do va giu item_path.
```

Paragraph sau item:

```text
Neu ro rang tiep tuc giai thich item cuoi, gan vao item cuoi.
Neu ro rang ap dung cho Khoan cha, tao child paragraph cap Khoan.
Neu khong chac, ghi ambiguous report, khong am tham doan.
```

---

## 8. Table Và Code

Rule:

```text
Table va fenced code duoc nhan dien truoc item regex.
Marker 1. hoac a) trong table/code khong parse thanh item.
Table/code nam trong item ke thua context item.
Table ngan giu nguyen.
Table dai split theo row group va lap lai header.
Code block giu nguyen hoac split bang logic rieng.
```

Table chỉ xử lý ở child layer vì parent phải giữ full section.

---

## 9. Embedding Preparation

Raw child content giữ nguyên.

`embedding_text` được tạo thêm, không ghi đè raw content:

```text
heading_path
item_path
legal_unit_type
raw child content
```

Không thêm thông tin suy diễn.

Ví dụ:

```text
Raw:
a) Don dang ky.

Embedding text:
Dieu kien ho so > Khoan 1. Ho so gom > Diem a) Don dang ky.
```

Page marker không được đưa vào `embedding_text`.

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
- [ ] Paragraph được gắn đúng item hoặc sinh ambiguous report.
- [ ] Item con kế thừa context cha.
- [ ] Item cha kết thúc bằng `:` không tạo child rỗng.
- [ ] Bullet `-`, `+`, `*` tạo atomic child.
- [ ] Item quá dài chỉ split nội bộ.
- [ ] Không child nào chứa nội dung của hai item khác nhau.
- [ ] Marker trong table/code không bị parse thành item.
- [ ] Nội dung trước heading đầu tiên thuộc `document-root` parent.
- [ ] Table/code trong item kế thừa đúng context.
- [ ] Child ngắn có `embedding_text` chứa context thật.
- [ ] Page marker không bị đưa vào `embedding_text`.

---

## 11. Done Khi

- [ ] Không còn logic convert `1.`, `a)` thành Markdown heading.
- [ ] Có structural block parser.
- [ ] Markdown heading được nhận diện trước item regex.
- [ ] Parent chunker chỉ dựa trên Markdown heading.
- [ ] Child chunker dựa trên structural item/table/code/paragraph boundary.
- [ ] Ambiguous cases có report.
- [ ] Tests parser/chunker pass.
