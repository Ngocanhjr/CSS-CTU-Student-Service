# Unified Flowchart Report — `guild_implement`

Các sơ đồ trong thư mục này đã được đồng bộ theo flow cuối cùng:

```text
validated Markdown
→ PageBlock[]
→ one stateful StructuralParser
→ parent_chunker + child_chunker dùng chung StructuralBlock[]
→ split chỉ trong atomic unit
→ Parent/Child Chunk
→ persist canonical content + parent relation vào PostgreSQL
→ Child embedding + structural Qdrant payload
→ Qdrant dense + PostgreSQL FTS/BM25
→ attach Qdrant payload cho sparse-only candidates
→ RRF/weighted fusion + PostgreSQL hydration + rerank
→ structural retrieval expansion
```

## Sơ đồ chuẩn

| Diagram | Purpose |
|---|---|
| `00_unified_chunking_retrieval_flow.mmd` | Tổng quan end-to-end từ Markdown đến publish và retrieval. Đây là sơ đồ overview chuẩn. |
| `09a_pre_chunk_parsing_normalization_flow.mmd` | Page marker consumption và một StructuralParser stateful chạy xuyên toàn bộ PageBlock. |
| `09a_page_range_citation_fix_flow.mmd` | Parent nhiều trang được tạo trực tiếp theo block range, không merge theo `heading_path`. |
| `10_structural_parent_child_flow.mmd` | Quy tắc Parent/Child, item hierarchy, paragraph, table/code và heading-only fallback. |
| `10_oversized_atomic_unit_split_flow.mmd` | Split item/paragraph/table/code quá dài mà không phá boundary. |
| `07_13_ingestion_pipeline_publish_modes_flow.mmd` | Orchestration, warning/error severity, preview và publish modes. |
| `08_chunk_key_db_qdrant_contract_flow.mmd` | Stable keys, PostgreSQL canonical content, Qdrant structural metadata và hydration. |
| `14_15_embedding_qdrant_indexing_flow.mmd` | Child embedding text, deterministic point id và payload đầy đủ. |
| `16_retrieval_citation_flow.mmd` | Hybrid retrieval thật sự, fusion, rerank, PostgreSQL hydration, structural expansion và citation. |
| `16a_hybrid_retrieval_sequence_flow.mmd` | Chi tiết hai nhánh Qdrant dense + PostgreSQL FTS hội tụ qua payload attach, fusion, rerank và expansion. |
| `17_validation_golden_tests_flow.mmd` | Validation severity, invariants và runnable regression/golden tests. |

## Flow cũ đã loại bỏ

- Không còn dùng `MarkdownHeaderTextSplitter` trên từng `PageBlock` trong production flow.
- Không còn `normalize_structural_headings()` để sửa canonical Markdown.
- Không còn merge Parent chỉ vì hai fragment có cùng `heading_path`.
- Không parse Parent lần hai để tạo Child.
- Không reset heading/item context khi đổi trang.
- Không append table/code vào raw content của Child item.
- Không bỏ item ngắn hoặc item kết thúc bằng `:`.
- Không suy `legal_unit_type` chỉ từ marker.
- Warning không chặn publish mặc định; error mới chặn.
- Hydration không làm rơi structural metadata từ Qdrant.

## Quy tắc quan trọng được bổ sung

- Mỗi Markdown heading mở một Parent mới; Parent cũ đóng trước heading tiếp theo.
- Heading-only Parent: nội dung độc lập tạo `heading_content` Child; heading cấu trúc dùng `context_only_reason`.
- `Chương I` + tên chương cùng cấp có derived context kết hợp nhưng không sửa raw Markdown.
- Numbered/lettered item tạo Child riêng; bullet ngắn liền kề cùng `heading_path` + `parent_item_key` có thể group và giữ `logical_item_keys`.
- Table/code luôn là atomic Child riêng, kể cả khi nằm trong item.
- Table dài split theo row group; code dài split theo line và giữ fence hợp lệ.
- PostgreSQL là canonical source cho metadata nghiệp vụ, chunk content và relations; canonical Markdown storage là authoritative ingestion source; Qdrant là disposable retrieval index giữ structural payload.
- Khi recreate Qdrant, chạy lại canonical Markdown qua parser/chunker/embedding; MVP không rebuild payload chỉ từ `document_chunks`.
- Retrieval expansion có điều kiện, sau đó deduplicate, source-order, rerank và context budget.

## Lưu ý triển khai

Các `.mmd` mô tả contract mục tiêu. Chúng không tự khẳng định backend hiện tại đã implement đầy đủ. Khi code được triển khai, cần đối chiếu diff và runnable tests với các sơ đồ này.
