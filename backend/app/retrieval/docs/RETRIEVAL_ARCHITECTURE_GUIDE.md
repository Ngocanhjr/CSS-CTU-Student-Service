# Cấu Trúc Tổng Quát Cho Retrieval Trong Hệ Thống RAG

## 1. Mục tiêu

Tài liệu này mô tả cấu trúc tổng quát của tầng **Retrieval** trong hệ thống RAG.

Retrieval có nhiệm vụ:

```text
Nhận câu hỏi đã được xử lý
→ tìm các đoạn tài liệu liên quan
→ lọc tài liệu hợp lệ
→ kết hợp nhiều phương pháp tìm kiếm
→ lấy nội dung chuẩn từ cơ sở dữ liệu
→ mở rộng ngữ cảnh theo cấu trúc tài liệu
→ sắp xếp và giới hạn context
→ trả về danh sách kết quả cho tầng sinh câu trả lời
```

Retrieval **không trực tiếp sinh câu trả lời cuối cùng**. Kết quả retrieval được chuyển sang tầng prompt/LLM để tạo câu trả lời.

---

## 2. Kiến trúc tổng quát

```text
User Query
    │
    ▼
Query Resolver
    │
    ├── Greeting / Smalltalk
    │       └── Không retrieval
    │
    ├── Query mơ hồ
    │       └── Hỏi lại hoặc bổ sung context
    │
    └── Query hợp lệ
            │
            ▼
    Dense Retrieval - Qdrant
            +
    Sparse Retrieval - PostgreSQL FTS/BM25
            │
            ▼
       Fusion - RRF
            │
            ▼
    Hydration từ PostgreSQL
            │
            ▼
          Rerank
            │
            ▼
    Structural Expansion
            │
            ▼
 Deduplicate + Source Order
            │
            ▼
       Context Budget
            │
            ▼
   list[RetrievalResult]
            │
            ▼
        Prompt + LLM
```

---

## 3. Cấu trúc thư mục đề xuất

```text
chatbot/backend/app/
├── retrieval/
│   ├── __init__.py
│   ├── models.py
│   ├── eligibility.py
│   ├── query_resolver.py
│   ├── dense_retriever.py
│   ├── sparse_retriever.py
│   ├── payload.py
│   ├── fusion.py
│   ├── hydration.py
│   ├── reranker.py
│   ├── expansion.py
│   ├── finalizer.py
│   └── retriever.py
│
├── embedding/
│   └── embedder.py
│
├── vectorstore/
│   └── repository.py
│
├── databases/
│   └── models.py
│
└── llm/
    └── prompts.py

chatbot/backend/test/retrieval/
├── test_eligibility.py
├── test_query_resolver.py
├── test_dense_retriever.py
├── test_sparse_retriever.py
├── test_fusion.py
├── test_hydration.py
├── test_expansion.py
├── test_finalizer.py
└── test_retriever.py
```

Có thể gộp một số file khi dự án còn nhỏ, nhưng nên giữ rõ trách nhiệm của từng phần.

---

## 4. Chức năng từng file

## 4.1. `retrieval/models.py`

Chứa các model dữ liệu của retrieval.

Các model chính:

```text
RetrievalContext
QueryDecision
RetrievalResult
ExpansionReason
```

### Nhiệm vụ

- Chuẩn hóa dữ liệu truyền giữa các bước.
- Tránh trả kết quả bằng dictionary không có cấu trúc.
- Giữ metadata phục vụ citation, expansion và debug.

### Ví dụ

```python
from dataclasses import dataclass
from typing import Literal


ExpansionReason = Literal[
    "direct_hit",
    "parent_context",
    "child_expansion",
    "sibling_expansion",
    "split_neighbor",
]


@dataclass(frozen=True)
class RetrievalContext:
    current_document_key: str | None = None
    current_version_key: str | None = None
    recent_topic: str | None = None


@dataclass(frozen=True)
class QueryDecision:
    should_search: bool
    query: str
    clarification_question: str | None = None
    document_key: str | None = None
    version_key: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    postgres_chunk_id: int
    postgres_parent_chunk_id: int | None
    document_key: str
    version_key: str
    chunk_key: str
    parent_chunk_key: str | None
    score: float
    content: str
    title: str
    page_start: int | None
    page_end: int | None
    source_file: str
    source_url: str
    citation: str
    heading_path: list[str]
    item_path: list[str]
    legal_unit_type: str
    block_type: str | None = None
    logical_item_key: str | None = None
    logical_item_keys: list[str] | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    split_index: int = 0
    split_count: int = 1
    chunk_index: int | None = None
    item_marker: str | None = None
    item_level: int | None = None
    expansion_reason: ExpansionReason = "direct_hit"
```

---

## 4.2. `retrieval/eligibility.py`

Là nguồn duy nhất định nghĩa tài liệu nào được phép xuất hiện trong retrieval.

### Nhiệm vụ

- Tạo điều kiện lọc cho PostgreSQL.
- Tạo hoặc cung cấp dữ liệu để xây dựng filter Qdrant.
- Bảo đảm dense retrieval và sparse retrieval dùng cùng chính sách.

### Các điều kiện cơ bản

```text
review_status = approved
rag_status = published
is_latest = true
```

Với audience sinh viên:

```text
audience_student = true
```

### Nguyên tắc

```text
Không tự định nghĩa eligibility riêng trong dense retrieval.
Không tự định nghĩa eligibility riêng trong sparse retrieval.
Mọi phía đều phải gọi cùng EligibilityPolicy.
```

---

## 4.3. `retrieval/query_resolver.py`

Xử lý câu hỏi trước khi retrieval.

### Nhiệm vụ

- Phát hiện greeting hoặc smalltalk.
- Phát hiện câu hỏi thiếu đối tượng.
- Bổ sung context từ giao diện hoặc lịch sử hội thoại.
- Trả về `QueryDecision`.

### Ví dụ xử lý

```text
"hi"
→ should_search = false

"điều kiện là gì" không có context
→ hỏi lại người dùng

"điều kiện là gì" với recent_topic="xin giấy khai sinh"
→ rewrite thành "điều kiện là gì cho xin giấy khai sinh"

"điều kiện là gì" khi đang xem document cụ thể
→ giữ query và thêm document_key filter
```

### Lưu ý

Không dùng rule substring quá rộng như:

```python
if "hồ sơ" in query:
```

vì câu rõ nghĩa như `hồ sơ xin cấp bảng điểm gồm gì` vẫn phải được search bình thường.

---

## 4.4. `embedding/embedder.py`

Chứa logic tạo embedding cho tài liệu và câu hỏi.

### Nhiệm vụ

- `embed_texts()` hoặc `embed_documents()` cho nhiều đoạn văn bản.
- `embed_query()` cho câu hỏi.
- Có thể quản lý cache embedding.
- Có thể cung cấp fake embedder để test.

### LangChain adapter

Nếu embedder của dự án không implement interface `Embeddings`, cần adapter:

```python
from langchain_core.embeddings import Embeddings


class LangChainEmbeddingsAdapter(Embeddings):
    def __init__(self, embedder):
        self._embedder = embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed_query(text)
```

---

## 4.5. `retrieval/dense_retriever.py`

Thực hiện semantic search bằng Qdrant.

### Nhiệm vụ

- Khởi tạo `QdrantVectorStore`.
- Truyền đúng embedding adapter.
- Truyền đúng named vector.
- Gắn eligibility filter.
- Truyền context filter như `document_key`, `version_key`.
- Lấy top-k dense candidates.

### Điểm quan trọng

```python
vector_name=VECTOR_NAME
```

Không nên hard-code tên vector ở nhiều nơi.

### Output

```text
list[LangChainDocument]
```

Mỗi document cần giữ được hoặc truy ra:

```text
qdrant_point_id
chunk_key
postgres_chunk_id
score
structural metadata
```

---

## 4.6. `retrieval/sparse_retriever.py`

Thực hiện keyword search bằng PostgreSQL Full Text Search hoặc BM25.

### Nhiệm vụ

- Tạo `tsquery` từ câu hỏi.
- Tìm trong `DocumentChunk.content`.
- Tính rank.
- Áp dụng cùng eligibility policy như dense retrieval.
- Trả về candidate có `qdrant_point_id` để lấy structural payload.

### Output tối thiểu

```text
postgres_chunk_id
qdrant_point_id
chunk_key
parent_chunk_id
document_key
version_key
score
```

### Lưu ý

Cần có GIN index cho biểu thức Full Text Search phù hợp với schema thực tế.

---

## 4.7. `retrieval/payload.py`

Xử lý metadata từ Qdrant.

### Nhiệm vụ

- Chuyển `_id` của LangChain document thành `qdrant_point_id`.
- Refetch full flat payload từ Qdrant.
- Gắn structural metadata vào candidate.

### Vì sao cần file này

LangChain thường mặc định mong payload có dạng:

```text
page_content
metadata
```

Nhưng project có thể lưu payload flat:

```text
chunk_key
heading_path
logical_item_key
parent_item_key
page_start
page_end
...
```

Do đó dense candidate và sparse candidate đều nên đi qua cùng bước attach payload trước fusion hoặc expansion.

---

## 4.8. `retrieval/fusion.py`

Kết hợp kết quả dense và sparse.

### Nhiệm vụ

- Kết hợp hai danh sách candidate.
- Deduplicate theo `chunk_key`.
- Tính fusion score.
- Chọn candidate tốt nhất trước hydration.

### Phương pháp đề xuất

```text
Reciprocal Rank Fusion - RRF
```

Công thức đơn giản:

```text
score(chunk) += 1 / (rank_constant + rank)
```

### Input

```text
dense_docs
sparse_docs
```

### Output

```text
fused_docs
```

---

## 4.9. `retrieval/hydration.py`

Lấy nội dung canonical từ PostgreSQL.

### Nhiệm vụ

- Đọc `postgres_chunk_id` từ candidate.
- Tải `DocumentChunk` từ PostgreSQL.
- Dùng `DocumentChunk.content` làm nội dung chính thức.
- Giữ structural metadata lấy từ Qdrant.
- Tạo citation.
- Fallback `parent_chunk_key` qua `parent_chunk_id`.
- Chuyển candidate thành `RetrievalResult`.

### Nguyên tắc quan trọng

```text
Qdrant dùng để search và lưu structural metadata.
PostgreSQL là nguồn canonical content.
```

Không nên tin `LangChainDocument.page_content` là nguồn cuối cùng.

---

## 4.10. `retrieval/reranker.py`

Xếp hạng lại các direct hit sau fusion và hydration.

### Nhiệm vụ

- Nhận danh sách `RetrievalResult`.
- Tính lại độ liên quan với query.
- Sắp xếp kết quả trước structural expansion.

### Có thể dùng

```text
Cross-encoder
LLM reranker
NVIDIA rerank endpoint
Rule-based deterministic reranker trong test
```

### Nguyên tắc

Production flow nên luôn có rerank.

Trong unit test có thể dùng:

```python
rerank=lambda results: results
```

---

## 4.11. `retrieval/expansion.py`

Mở rộng ngữ cảnh theo cấu trúc tài liệu.

### Nhiệm vụ

Từ direct hit, tìm thêm các chunk liên quan theo quan hệ cấu trúc:

```text
parent context
child expansion
sibling expansion
split neighbor
```

### Các helper chính

```python
find_parent_item()
find_direct_children()
find_siblings()
find_split_neighbors()
```

### Ví dụ

Nếu query là:

```text
"Hồ sơ gồm những giấy tờ gì?"
```

và retrieval chỉ trúng một bullet, expansion có thể lấy thêm các bullet cùng nhóm để context đầy đủ hơn.

### Scope bắt buộc

Lookup nên giới hạn ít nhất theo:

```text
version_key
```

Khi có thể, thêm:

```text
parent_chunk_key
```

để tránh nối nhầm cấu trúc giữa các section hoặc version khác nhau.

---

## 4.12. `retrieval/finalizer.py`

Hoàn thiện kết quả retrieval trước khi trả về.

### Nhiệm vụ

- Deduplicate theo `chunk_key`.
- Ưu tiên `direct_hit` hơn result do expansion.
- Sắp xếp theo thứ tự nguồn.
- Áp dụng context budget.

### Thứ tự xử lý

```text
deduplicate
→ source-order
→ context budget
```

### Source order

Có thể sắp xếp theo:

```text
version_key
chunk_index
split_index
```

### Context budget

Giới hạn tổng số ký tự hoặc token được chuyển sang LLM.

Nên thống nhất một đơn vị rõ ràng:

```text
character budget
hoặc token budget
```

---

## 4.13. `retrieval/retriever.py`

Là lớp điều phối toàn bộ retrieval pipeline.

### Nhiệm vụ

- Nhận query đã được resolver xác nhận có thể search.
- Gọi dense retrieval.
- Gọi sparse retrieval.
- Attach Qdrant payload.
- Fusion.
- Hydration.
- Rerank.
- Structural expansion.
- Finalize.
- Trả `list[RetrievalResult]`.

### Pseudocode

```python
async def search_resolved_query(query):
    if not query.strip():
        return []

    dense_docs = dense_search(query)
    dense_docs = attach_qdrant_payloads(dense_docs)

    sparse_docs = await sparse_search(query)
    sparse_docs = attach_qdrant_payloads(sparse_docs)

    fused_docs = reciprocal_rank_fusion(
        dense_docs,
        sparse_docs,
    )

    direct_hits = await hydrate_from_postgres(fused_docs)
    reranked_hits = rerank(query, direct_hits)

    expanded = await expand_structural_context(
        query,
        reranked_hits,
    )

    return finalize_retrieval_results(expanded)
```

### Lưu ý

`Retriever.search_resolved_query()` chỉ xử lý query đã được quyết định là hợp lệ để search.

Greeting và clarification nên được xử lý trước đó ở tầng orchestration hoặc API.

---

## 4.14. `vectorstore/repository.py`

Chứa logic giao tiếp mức thấp với Qdrant.

### Nhiệm vụ

- Định nghĩa collection name.
- Định nghĩa vector name.
- Khởi tạo Qdrant client.
- Tạo collection.
- Upsert/delete points.
- Xây dựng Qdrant filter.
- Có thể cung cấp helper retrieve payload theo point ID.

### Các hằng số nên tập trung ở đây

```python
DEFAULT_COLLECTION = "..."
VECTOR_NAME = "embedding"
```

Không hard-code lại các giá trị này trong retrieval layer.

---

## 4.15. `databases/models.py`

Chứa SQLAlchemy models.

### Những model thường được retrieval dùng

```text
Document
DocumentVersion
DocumentChunk
```

### Dữ liệu quan trọng

```text
document_key
version_key
review_status
rag_status
is_latest
audience_student
chunk_key
parent_chunk_id
content
heading_path
page_start
page_end
qdrant_point_id
index_status
chunk_type
```

---

## 4.16. `llm/prompts.py`

Không thuộc retrieval, nhưng là nơi nhận kết quả retrieval để build prompt.

### Nhiệm vụ

- Định nghĩa RAG answer prompt.
- Yêu cầu LLM chỉ trả lời dựa trên context.
- Hướng dẫn citation.
- Quy định khi context không đủ.

Retrieval chỉ trả data; file prompt quyết định cách LLM sử dụng data đó.

---

## 5. Luồng dữ liệu chi tiết

## Bước 1: Resolve query

```text
Input:
"điều kiện là gì"

Context:
recent_topic = "xin giấy khai sinh"

Output:
query = "điều kiện là gì cho xin giấy khai sinh"
should_search = true
```

## Bước 2: Dense retrieval

```text
Query
→ embedding
→ Qdrant vector search
→ top dense candidates
```

## Bước 3: Sparse retrieval

```text
Query
→ PostgreSQL FTS/BM25
→ top sparse candidates
```

## Bước 4: Attach payload

```text
Candidate qdrant_point_id
→ Qdrant retrieve payload
→ structural metadata
```

## Bước 5: Fusion

```text
Dense candidates + Sparse candidates
→ RRF
→ fused candidates
```

## Bước 6: Hydration

```text
postgres_chunk_id
→ PostgreSQL DocumentChunk
→ canonical content
→ RetrievalResult
```

## Bước 7: Rerank

```text
Query + direct hits
→ relevance reranker
→ reordered direct hits
```

## Bước 8: Structural expansion

```text
direct hit
→ parent / children / siblings / split neighbors
→ expanded candidates
```

## Bước 9: Finalization

```text
expanded candidates
→ deduplicate
→ source order
→ context budget
→ final retrieval results
```

---

## 6. Phân chia trách nhiệm

| Thành phần       | Trách nhiệm chính                      |
| ------------------ | ----------------------------------------- |
| Query resolver     | Quyết định có search hay không       |
| Eligibility policy | Quyết định tài liệu nào hợp lệ    |
| Dense retriever    | Tìm theo ngữ nghĩa                     |
| Sparse retriever   | Tìm theo từ khóa                       |
| Payload helper     | Gắn structural metadata từ Qdrant       |
| Fusion             | Kết hợp dense và sparse                |
| Hydration          | Lấy canonical content từ PostgreSQL     |
| Reranker           | Xếp hạng lại direct hits               |
| Expansion          | Mở rộng context theo cấu trúc         |
| Finalizer          | Deduplicate, order, budget                |
| Retriever          | Điều phối toàn bộ pipeline           |
| Prompt/LLM         | Sinh câu trả lời từ retrieval results |

---

## 7. Cấu trúc tối thiểu khi mới triển khai

Nếu chưa muốn tách nhiều file, có thể bắt đầu với:

```text
app/retrieval/
├── models.py
├── eligibility.py
├── query_resolver.py
└── retriever.py
```

Trong `retriever.py`, tạm thời chứa:

```text
Embedding adapter
Dense retrieval
Sparse retrieval
Payload attachment
Fusion
Hydration
Citation
Expansion
Finalization
Retriever class
```

Khi file lớn, tách dần theo cấu trúc đầy đủ ở trên.

---

## 8. Thứ tự triển khai đề xuất

## Giai đoạn 1: Retrieval cơ bản

```text
Query resolver
Dense Qdrant retrieval
Eligibility filter
Hydration PostgreSQL
Citation
```

## Giai đoạn 2: Hybrid retrieval

```text
PostgreSQL sparse retrieval
Attach Qdrant payload
RRF fusion
Rerank
```

## Giai đoạn 3: Structural retrieval

```text
Parent expansion
Child expansion
Sibling expansion
Split neighbor
Deduplicate
Source order
Context budget
```

---

## 9. Test cần có

## Query resolver

```text
Greeting không search
Query rỗng không search
Query mơ hồ không context thì hỏi lại
Query có recent topic được rewrite
Document/version context được truyền xuống
```

## Eligibility

```text
Student bắt buộc approved/published/is_latest/audience_student
Admin vẫn bắt buộc approved/published/is_latest
Dense và sparse dùng cùng policy
```

## Dense retrieval

```text
Đúng collection
Đúng VECTOR_NAME
Có eligibility filter
Có document/version filter
```

## Sparse retrieval

```text
FTS trả đúng candidate
Có qdrant_point_id
Áp dụng đúng eligibility conditions
```

## Payload

```text
Dense candidate được attach flat payload
Sparse candidate được attach flat payload
Không có point ID thì xử lý an toàn
```

## Fusion

```text
Dense + sparse được kết hợp
Deduplicate theo chunk_key
Fusion score đúng
```

## Hydration

```text
Content lấy từ PostgreSQL
Không dùng payload content làm canonical
Citation đúng
Fallback parent_chunk_key đúng
```

## Expansion

```text
Lấy parent context
List query lấy children
List query lấy siblings
Split chunk lấy split neighbor
Lookup scope theo version_key
```

## Finalization

```text
Ưu tiên direct_hit
Source order đúng
Context budget không vượt
```

## Retriever orchestration

```text
Blank query không gọi Qdrant
Rerank chạy trước expansion
Pipeline chạy đúng thứ tự
Trả list[RetrievalResult]
```

---

## 10. Các nguyên tắc quan trọng

### 10.1. Không trộn Retrieval với Generation

```text
Retrieval trả tài liệu.
LLM sinh câu trả lời.
```

Không nên để retrieval tự gọi LLM answer generation nếu muốn kiến trúc dễ test và dễ bảo trì.

### 10.2. PostgreSQL là nguồn nội dung chuẩn

```text
Qdrant = search index + structural metadata
PostgreSQL = canonical content
```

### 10.3. Dense và sparse phải cùng eligibility domain

Nếu hai phía dùng filter khác nhau, fusion sẽ trộn các candidate không cùng điều kiện hợp lệ.

### 10.4. Rerank trước structural expansion

Chỉ nên expansion từ các direct hit đã được xếp hạng lại.

### 10.5. Structural expansion không được mở rộng vô hạn

Phải có:

```text
scope
source order
context budget
```

### 10.6. Mọi result cần trace được nguồn gốc

Nên giữ:

```text
chunk_key
postgres_chunk_id
qdrant_point_id nếu cần debug
document_key
version_key
citation
expansion_reason
score
```

---

## 11. Ví dụ orchestration ở tầng ứng dụng

```python
decision = complete_or_clarify_query(
    question,
    context=retrieval_context,
)

if not decision.should_search:
    return {
        "answer": decision.clarification_question,
        "retrieval_results": [],
    }

results = await retriever.search_resolved_query(
    session,
    query=decision.query,
    audience="student",
    document_key=decision.document_key,
    version_key=decision.version_key,
    top_k=5,
    context_budget=6000,
)

context = "\n\n".join(
    f"[{item.chunk_key}]\n"
    f"{item.content}\n"
    f"Nguồn: {item.citation}"
    for item in results
)

answer = await answer_chain.ainvoke(
    {
        "question": decision.query,
        "context": context,
    }
)
```

---

## 12. Kết luận

Một retrieval layer hoàn chỉnh nên có cấu trúc:

```text
Query Resolution
→ Eligibility
→ Dense Retrieval
→ Sparse Retrieval
→ Payload Enrichment
→ Fusion
→ Hydration
→ Rerank
→ Structural Expansion
→ Finalization
→ RetrievalResult
```

Cách tổ chức này giúp hệ thống:

```text
Dễ test
Dễ debug
Dễ thay vector database
Dễ thay reranker
Dễ kiểm soát quyền truy cập tài liệu
Dễ mở rộng citation và structural retrieval
Không phụ thuộc chặt vào LLM generation
```
