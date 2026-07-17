# 22. Chunking–Retrieval Reconciliation Guide

**Status:** Normative final contract  
**Scope:** Normative target contract. Backend implementation và migration phải theo contract này.

Guide này tổng hợp 14 điểm reconciliation cuối. Nếu guide cũ mâu thuẫn, file này ưu tiên.

## 1. Page Marker Contract

- `PageBlock.content` bắt đầu sau `current_match.end()` và kết thúc trước `next_match.start()`.
- `<!-- page: n -->` đã được consume thành `PageBlock.page_number`; không thành StructuralBlock, paragraph hoặc embedding text.
- Markdown không có page marker tạo một `PageBlock(page_number=1, content=body)`; citation dùng page 1.
- HTML comment kỹ thuật bị bỏ qua.
- Số trang OCR đứng riêng và `---` chỉ bỏ khi nằm sát page boundary đã xác định; không xóa ở nội dung bình thường.

## 2. Parent Boundary — Phương Án A

- Mỗi Markdown heading mở một Parent mới.
- Parent hiện tại đóng ngay trước heading tiếp theo, bất kể heading level.
- Không merge Parent qua hai source heading khác nhau.
- Helper merge chỉ hợp lệ cho continuation fragment kỹ thuật không có heading boundary.

## 3. Heading-Only Content

- Nếu Parent không có body nhưng heading chứa nội dung độc lập/mệnh đề quy phạm, tạo `heading_content` Child nguyên văn và embedding.
- Heading thuần context như `Chương I`, `Phần II`, `Mục 1` có thể `context_only`.
- Mỗi Parent phải có Child hoặc `context_only_reason` rõ ràng.

## 4. Heading Kép

- Với `### Chương I` + `### TÊN CHƯƠNG` liên tiếp, không sửa raw Markdown.
- Derived `heading_path` của descendant giữ `Chương I — TÊN CHƯƠNG`.
- Không đủ chắc chắn thì tạo `heading_context` warning.

## 5. Canonical Markdown Validation

- Markdown heading có sẵn luôn là heading; backend không tự demote.
- Tạo warning cho heading quá dài, nhiều câu, level bất thường, hai heading cùng cấp liên tiếp không body, Parent không Child hoặc heading path bất thường.

## 6. Table Và Code

- Markdown table và fenced code luôn là atomic Child riêng.
- Không append table/code vào raw Child item.
- Nằm trong item thì kế thừa `heading_path`, `item_path`, `parent_item_key`; item stack vẫn được giữ.
- Parser consume table/fenced code trên một stream dòng có page metadata, nên block có thể đi qua page boundary và giữ đúng `page_start/page_end`.
- Fenced code không có closing fence tạo `unclosed_code_fence` error; không được parse các dòng bên trong thành item.
- Table dài split theo row group, lặp header + separator, không cắt row.
- Code dài split theo ranh giới dòng; mỗi split giữ opening/closing fence hợp lệ, cùng `logical_code_key` và `split_index/split_count`; không dùng generic splitter.

## 6.1 StructuralBlock Và Child Chunk

- `StructuralBlock` là đơn vị parser, không phải Chunk.
- numbered_item/lettered_item luôn thành Child riêng.
- Child chunker chỉ gộp bullet ngắn liền kề khi cùng `heading_path`, `parent_item_key` và tổng content không vượt `child_chunk_size`.
- Không gộp bullet qua heading, parent item, paragraph, table hoặc code.
- Bullet group có `block_type=bullet_group`, `logical_item_key=None`, `logical_item_keys` chứa key từng bullet; `item_path` là path item cha chung.

## 7. `legal_unit_type`

- `block_type` phản ánh hình thức marker.
- `legal_unit_type` chỉ gán article/clause/point/bullet khi có legal context xác nhận.
- Danh sách thông thường dùng `none`; không suy ra clause/point chỉ từ `1.`/`a)`.

## 8. Validation Severity

- Report có `severity`, `code`, `reason`, `page`, `selected_owner`, `candidate_owners`.
- `warning` không block publish mặc định; `error` mới block.
- Heading context kép và heading dài bất thường là warning; paragraph không emit report riêng.
- Missing page range, duplicate logical key, child thiếu parent chunk hoặc split phá boundary là error.

## 9. Structural Metadata Và PostgreSQL

- `Chunk.metadata` là metadata trong memory của pipeline.
- PostgreSQL persist canonical metadata nghiep vu, chunk content va parent relation; khong them cot `structural_metadata` trong MVP.
- Canonical Markdown storage la authoritative ingestion source.
- Qdrant la disposable retrieval index; payload persist structural metadata de filter, trace va expansion.
- Khi mat/recreate Qdrant collection, rebuild bang canonical Markdown -> parser -> chunker -> embedding -> Qdrant.
- Khong ho tro rebuild payload chi tu `document_chunks` trong MVP.

## 10. Qdrant Payload

Payload Child tối thiểu có:

```text
document_key
version_key
title
source_file
source_url
chunk_key
parent_chunk_key
postgres_chunk_id
postgres_parent_chunk_id
heading_path
page_start/page_end
logical_item_key
logical_item_keys
parent_item_key
logical_table_key
logical_code_key
split_index
split_count
chunk_index hoặc source_order
item_marker
item_level
item_path
legal_unit_type
block_type
```

Qdrant không giữ canonical content; content cuối hydrate từ PostgreSQL. Structural metadata tiếp tục lấy từ Qdrant payload. `parent_chunk_key` có thể derive qua `parent_chunk_id`/parent row khi hydrate. Status/audience trong payload chỉ là mirror để lọc candidate; khi hydrate phải kiểm tra lại eligibility canonical từ PostgreSQL và loại hit Qdrant bị stale.

## 11. Embedding Text

- `item_path` metadata giữ đầy đủ ancestor + current item.
- `embedding_text` chỉ prepend `heading_path` và ancestor labels = `item_path[:-1]`.
- Raw child content đã chứa current item nên không lặp `item_path[-1]`.
- Không dùng LLM, không tự tóm tắt, không sao chép toàn bộ item cha dài.

## 12. Retrieval Structural Expansion

```text
Qdrant dense + PostgreSQL FTS/BM25
→ attach Qdrant payload cho sparse-only candidates bang qdrant_point_id
→ RRF hoặc weighted fusion
→ hydrate fused candidates và revalidate eligibility từ PostgreSQL
→ rerank
→ parent/child/sibling/split expansion
→ hydrate expanded neighbors
→ deduplicate
→ source-order
→ context budget
```

- Hit bullet group → lấy parent context bằng `parent_item_key`; `logical_item_keys` chỉ dùng trace/citation member.
- Hit child → lấy parent context.
- Hit parent với query liệt kê → lấy direct children.
- Query “gồm gì/các trường hợp nào/cần gì” → có thể lấy siblings.
- Hit split → lấy split neighbor/cùng logical item trong budget.
- Không mở rộng toàn bộ Parent khi chỉ cần một nhánh.

## 12.1 Query Decision Và Answer Chain

- `complete_or_clarify_query()` chạy trước Retriever.
- Greeting/smalltalk và query mơ hồ không context trả response trực tiếp; không gọi Qdrant hoặc LLM.
- Retriever chỉ nhận resolved query qua `search_resolved_query()`.
- List rỗng sau resolved retrieval chỉ có nghĩa là no-result, không đại diện clarification.
- `current_document_key/current_version_key` được cộng vào student hard filter.

## 12.2 EligibilityPolicy — Contract Chung Dense Và Sparse

Dense (Qdrant) và sparse (PostgreSQL FTS) đang định nghĩa điều kiện eligibility độc lập:
Guide 15 §9 cho phép admin/internal dùng `build_context_filter()` không có status, còn Guide 16
§2 `search_sparse_documents()` luôn hard-code `review_status=approved` + `rag_status=published`
cho mọi audience. Kết quả là fusion admin có thể trộn hai candidate set thuộc hai eligibility
domain khác nhau. Mục này chốt contract chung, override Guide 15 §9 và Guide 16 §2 nếu khác.

- Dense và sparse phải dùng cùng một eligibility policy trước fusion; không được định nghĩa
  điều kiện status riêng ở từng phía.
- Policy sống tại `app/retrieval/eligibility.py`. Không đặt trong `app/vectorstore/repository.py`
  (chỉ chứa Qdrant plumbing) hay `app/retrieval/retriever.py` (chỉ orchestration, không phải nguồn
  policy).
- `EligibilityContext`:

  ```python
  @dataclass(frozen=True)
  class EligibilityContext:
      audience: str = "student"  # "student" | "admin" | "internal"
      document_key: str | None = None
      version_key: str | None = None
  ```

- `EligibilityPolicy.build_postgres_conditions(context: EligibilityContext) -> list[ColumnElement[bool]]`
  trả list điều kiện SQLAlchemy để `.where(*conditions)`.
- `EligibilityPolicy.build_qdrant_filter(context: EligibilityContext) -> Filter` trả
  `qdrant_client.models.Filter`.
- Hai điều kiện sau là **bắt buộc cho mọi audience**, không có tham số override, không có audience
  nào được miễn:
  - `review_status == "approved"`
  - `rag_status == "published"`
- `is_latest` là ranking preference, không nằm trong PostgreSQL `WHERE` hoặc Qdrant hard filter.
  Version bị thay thế phải chuyển `rag_status=deactivated`; retriever chỉ ưu tiên `is_latest=true`
  sau fusion/rerank khi relevance tương đương.
- Audience chỉ khác nhau ở điều kiện hiển thị, không phải ở status:
  - `audience == "student"` → cộng thêm điều kiện audience chứa `"sinh_vien"` hoặc `"cong_khai"`
    (Postgres: `Document.audience.overlap([...])`; Qdrant: `audience_student == true`).
  - `audience in {"admin", "internal"}` → không cộng điều kiện audience, nhưng vẫn giữ nguyên hai
    điều kiện status bắt buộc ở trên. Không có khái niệm "admin bypass status".
- `document_key`/`version_key` khi có trong context được cộng thêm ở cả hai phía như điều kiện
  context thuần, không thay thế hai điều kiện bắt buộc.
- `build_context_filter()`/`build_student_filter()` (Guide 15 §9) và `search_sparse_documents()`
  (Guide 16 §2) không còn tự định nghĩa điều kiện `review_status`/`rag_status`/`audience_student`;
  cả hai phải gọi `EligibilityPolicy.build_qdrant_filter()` /
  `EligibilityPolicy.build_postgres_conditions()` tương ứng rồi cộng thêm điều kiện context thuần
  (`document_type`, `domain`, `chunk_type`) tách riêng — các điều kiện context thuần này không
  thuộc EligibilityPolicy.
- Vi phạm cần tránh: dense dùng filter không status cho admin trong khi sparse vẫn hard-code status
  cho mọi audience; hoặc một phía hard-filter `is_latest` trong khi contract chỉ cho phép dùng nó
  làm ranking preference.

## 13. Golden Test `test_3266.md`

Golden fixture bao phủ page artifact, heading-only Điều, heading kép, heading bất thường, nested items Điều 18, cross-page item/table/code, paragraph ownership theo item đang mở, table Điều 19, legal/general list, structural payload và retrieval expansion.

Snapshot kiểm tra Parent/Child, heading/item path, logical/parent key, page range, split metadata, warning/error và source order.

## 14. Contradiction Sweep

Sau khi cập nhật phải search toàn guild để bảo đảm không còn:

- page marker nằm trong `PageBlock.content`;
- merge Parent qua heading boundary;
- table/code append vào Child item;
- mọi numbered item mặc định là legal clause;
- mọi warning đều block publish;
- Qdrant payload thiếu structural fields;
- retrieval thiếu PostgreSQL FTS/BM25 hoặc fusion;
- production retrieval bo qua rerank;
- retrieval chỉ vector search + hydrate mà không structural expansion;
- dense và sparse định nghĩa điều kiện `review_status`/`rag_status`/audience độc lập
  nhau thay vì cùng gọi `EligibilityPolicy` (§12.2);
- bất kỳ audience nào (kể cả admin/internal) bỏ qua `review_status=approved`,
  `rag_status=published`;
- bất kỳ dense/sparse path nào hard-filter `is_latest=true` thay vì dùng nó làm ranking preference.
