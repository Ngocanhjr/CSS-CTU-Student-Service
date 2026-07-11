# 22. Chunking–Retrieval Reconciliation Guide

**Status:** Normative final contract  
**Scope:** Normative target contract. Backend implementation và migration phải theo contract này.

Guide này tổng hợp 14 điểm reconciliation cuối. Nếu guide cũ mâu thuẫn, file này ưu tiên.

## 1. Page Marker Contract

- `PageBlock.content` bắt đầu sau `current_match.end()` và kết thúc trước `next_match.start()`.
- `<!-- page: n -->` đã được consume thành `PageBlock.page_number`; không thành StructuralBlock, paragraph hoặc embedding text.
- `page_markers.py` chỉ consume page marker và boundary artifact để tạo `PageBlock` sạch.
- `structural_parser.py` chịu trách nhiệm bỏ qua HTML comment kỹ thuật.
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

## 6.1 Item Và Bullet Grouping

- `numbered_item` và `lettered_item` luôn tạo Child riêng; không merge hai marker khác nhau.
- Các `bullet_item` ngắn, liền kề, có cùng `heading_path` và cùng `parent_item_key` có thể group vào một Child.
- Bullet group giữ thứ tự nguồn và `logical_item_keys` chứa stable key của mọi bullet thành viên.
- Bullet không thỏa điều kiện grouping vẫn tạo Child riêng và dùng `logical_item_key`.
- Split chỉ chạy sau grouping và không được thay đổi membership của bullet group.

## 7. `legal_unit_type`

- `block_type` phản ánh hình thức marker.
- `legal_unit_type` chỉ gán article/clause/point/bullet khi có legal context xác nhận.
- Danh sách thông thường dùng `none`; không suy ra clause/point chỉ từ `1.`/`a)`.

## 8. Validation Severity

- Report có `severity`, `code`, `reason`, `page`, `selected_owner`, `candidate_owners`.
- `warning` không block publish mặc định; `error` mới block.
- Paragraph ownership, heading context kép, heading dài bất thường là warning.
- Missing page range, duplicate logical key, child thiếu parent chunk hoặc split phá boundary là error.

## 9. Structural Metadata Và PostgreSQL

- `Chunk.metadata` là metadata trong memory của pipeline.
- `document_chunks.structural_metadata JSONB NOT NULL DEFAULT '{}'` persist đầy đủ structural metadata trước khi index.
- PostgreSQL là source of truth cho canonical content, relations và structural metadata.
- Qdrant payload được rebuild từ PostgreSQL; restart/re-index không được phụ thuộc metadata chỉ còn trong process memory.
- Migration thêm `structural_metadata` là bắt buộc trước khi contract này được xem là implemented.

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

Qdrant không giữ canonical content; content cuối và structural metadata chuẩn hydrate từ PostgreSQL. `parent_chunk_key` có thể derive qua `parent_chunk_id`/parent row khi rebuild payload.

## 11. Embedding Text

- `item_path` metadata giữ đầy đủ ancestor + current item.
- `embedding_text` chỉ prepend `heading_path` và ancestor labels = `item_path[:-1]`.
- Raw child content đã chứa current item nên không lặp `item_path[-1]`.
- Không dùng LLM, không tự tóm tắt, không sao chép toàn bộ item cha dài.

## 12. Retrieval Structural Expansion

```text
Qdrant dense + PostgreSQL FTS/BM25
→ RRF hoặc weighted fusion
→ hydrate fused candidates từ PostgreSQL
→ rerank
→ parent/child/sibling/split expansion
→ hydrate expanded neighbors
→ deduplicate
→ source-order
→ context budget
```

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

## 13. Golden Test `test_3266.md`

Golden fixture bao phủ page artifact, heading-only Điều, heading kép, heading bất thường, nested items Điều 18, cross-page item/table/code, ambiguous paragraph, table Điều 19, legal/general list, structural payload và retrieval expansion.

Snapshot kiểm tra Parent/Child, heading/item path, logical/parent key, page range, split metadata, warning/error và source order.

## 14. Contradiction Sweep

Sau khi cập nhật phải search toàn guild để bảo đảm không còn:

- page marker nằm trong `PageBlock.content`;
- merge Parent qua heading boundary;
- table/code append vào Child item;
- mọi numbered item mặc định là legal clause;
- mọi warning đều block publish;
- structural metadata chỉ tồn tại trong memory/Qdrant;
- migration thiếu `document_chunks.structural_metadata`;
- Qdrant payload thiếu structural fields;
- retrieval thiếu PostgreSQL FTS/BM25 hoặc fusion;
- retrieval chỉ vector search + hydrate mà không structural expansion.
