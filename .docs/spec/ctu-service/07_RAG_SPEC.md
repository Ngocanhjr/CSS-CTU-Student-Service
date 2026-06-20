# 07. Đặc Tả RAG Pipeline

**Version:** 1.0  
**Last Updated:** 2026-06-16  
**Status:** Final

---

## Mục Lục

1. [RAG Stack Summary](#rag-stack-summary)
2. [Knowledge Base Lifecycle](#knowledge-base-lifecycle)
3. [Chunking Rules](#chunking-rules)
4. [Embedding Strategy](#embedding-strategy)
5. [Qdrant Configuration](#qdrant-configuration)
6. [Retrieval Pipeline](#retrieval-pipeline)
7. [Dense & Sparse Retrieval](#dense--sparse-retrieval)
8. [Hybrid Fusion](#hybrid-fusion)
9. [Parent Context Expansion](#parent-context-expansion)
10. [Prompt Construction](#prompt-construction)
11. [Answer Generation](#answer-generation)
12. [Citation Validation](#citation-validation)
13. [Evaluation Strategy](#evaluation-strategy)

---

## RAG Stack Summary

| Component | Technology | Notes |
|-----------|------------|-------|
| **OCR Tool** | ocr-pvl | PaddleOCR + VietOCR + LlamaParse |
| **Chunking Framework** | LangChain | Heading-aware parent-child |
| **Chunking Rules** | Parent-child | Parent: 800-1500 tokens, Child: 300-600 tokens |
| **Embedding Model** | BAAI/bge-m3 | 1024-dim, normalized |
| **Vector DB** | Qdrant | Cosine distance |
| **Retrieval** | Hybrid | Dense (Qdrant) + Sparse (PostgreSQL FTS) |
| **Fusion** | RRF | Reciprocal Rank Fusion |
| **Reranking** | Simple heuristics (MVP) | Cross-encoder (future) |
| **LLM** | TBD | OpenAI/Anthropic/Local |
| **HNSW Tuning** | Future only | Not in MVP |

---

## Knowledge Base Lifecycle

### Document States Flow

```
uploaded
  ↓
ocr_processing (ocr-pvl)
  ↓
ocr_done (output: Markdown)
  ↓
need_review (human review Markdown + metadata)
  ↓
approved (review_status = approved)
  ↓
chunked (LangChain parent-child chunking)
  ↓
embedded (BGE-M3 batch embedding)
  ↓
indexed (Qdrant upsert)
  ↓
published (rag_status = published, searchable)
```

### Markdown Document Format

**Structure:**
```markdown
---
# YAML Frontmatter (metadata)
---

# Document Body (Markdown)

<!-- page: 1 -->

## Heading 1

Content...

<!-- page: 2 -->

### Sub-heading

More content...
```

**Required Components:**
1. YAML frontmatter với required fields
2. Markdown body với proper heading hierarchy
3. Page markers (`<!-- page: N -->`) cho citation

---

### YAML Metadata Frontmatter

**Required Fields:**
```yaml
---
document_id: "quy-che-dao-tao-2024"
version_id: "quy-che-dao-tao-2024-v1"
title: "Quy Chế Đào Tạo Đại Học Chính Quy 2024"
document_type: "noi_quy"
department: "pdt"
---
```

**Optional Fields:**
```yaml
domain: "dao_tao"
audience: ["sinh_vien", "giang_vien"]
code: "QĐ 123/2024/ĐHCT"
version_label: "1.0"
issued_date: "2023-12-15"
effective_date: "2024-01-01"
expiry_date: null  # null = vô thời hạn
is_latest: true
version_role: "base"
validity_status: "unchecked"
collection_status: "collected"
ocr_status: "done"
review_status: "not_reviewed"
rag_status: "not_indexed"
confidentiality: "public"
language: "vi"
citation_type: "page"  # page | section | paragraph
replaces: []
replaced_by: []
amends: []
amended_by: []
supplements: []
supplemented_by: []
source_url: "https://..."
```

**Field Explanations:**
- `document_id`: Stable document identifier
- `version_id`: Stable version identifier
- `document_type`: noi_quy | quy_trinh | bieu_mau | hoi_dap | unknown
- `department`: pdt | hoc_vu | ctsv | thu_vien | ...
- `version_label`: Human-readable version (1.0, 1.1, 2.0)
- `effective_date`: YYYY-MM-DD; required before publishing/search
- `confidentiality`: public | internal | restricted
- `ocr_status`: no `not_required`; use `done` after OCR/parser validation completes
- Do not add `priority` or `chunking_strategy` metadata fields.

---

## Chunking Rules

### Parent-Child Chunking (LangChain)

**Framework:** LangChain `MarkdownHeaderTextSplitter`

Chunking is fixed service behavior for the MVP, not a `chunking_strategy` field in YAML/Pydantic metadata.

**Rules:**
- **Parent chunks:** Full sections (800-1500 tokens)
- **Child chunks:** Sub-sections (300-600 tokens)
- **Overlap:** 50-100 tokens
- **Preserve:** Headings, lists, tables, page markers

**Rationale:**
- Search on child chunks (smaller, more precise)
- Retrieve parent context for LLM (larger, more complete)

**Heading-Aware Rules:**

```python
from langchain.text_splitter import MarkdownHeaderTextSplitter

headers_to_split_on = [
    ("#", "h1"),      # Chương
    ("##", "h2"),     # Điều
    ("###", "h3"),    # Khoản
]

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False  # Keep headings in chunks
)
```

**Process:**
1. Split Markdown by headings → parent chunks
2. Each parent chunk = 1 major section
3. Further split parent → child chunks (by paragraph, ~500 tokens)
4. Preserve table structure (don't split tables)
5. Preserve page markers trong chunk text

**Example:**

```
Document: "Quy Chế Đào Tạo"
├─ Parent Chunk 1: "Chương 1: Quy Định Chung" (1200 tokens)
│  ├─ Child 1.1: "Điều 1: Phạm vi áp dụng" (400 tokens)
│  ├─ Child 1.2: "Điều 2: Đối tượng áp dụng" (450 tokens)
│  └─ Child 1.3: "Điều 3: Nguyên tắc" (350 tokens)
├─ Parent Chunk 2: "Chương 2: Điều Kiện Tốt Nghiệp" (900 tokens)
   ├─ Child 2.1: "Điều 4: Điều kiện về tín chỉ" (380 tokens)
   └─ Child 2.2: "Điều 5: Điều kiện về GPA" (420 tokens)
```

**Table Preservation:**

Tables stay intact trong 1 chunk:
```markdown
| Loại Học Bổng | Điều Kiện GPA | Mức Tiền |
|---------------|---------------|----------|
| A             | >= 3.6        | 2,000,000|
| B             | >= 3.2        | 1,500,000|
```

**Page Marker Preservation:**

Child chunk retains page markers:
```
<!-- page: 3 -->
Sinh viên cần nộp đơn xin học bổng trước ngày 30/9 hàng năm...
<!-- page: 4 -->
...kèm theo bảng điểm và xác nhận từ khoa.
```

---

## Embedding Strategy

### BGE-M3 Configuration

**Model:** `BAAI/bge-m3`

**Specs:**
- Dimension: 1024
- Max input tokens: 8192
- Normalize: True
- Distance metric: Cosine similarity

**Implementation:**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('BAAI/bge-m3')
embeddings = model.encode(
    texts,
    normalize_embeddings=True,
    batch_size=32,
    show_progress_bar=True
)
```

**Embedding Process:**
1. Load BGE-M3 model (cache locally)
2. Batch embed child chunks (batch_size=32)
3. Normalize vectors (L2 norm)
4. Store vectors trong Qdrant

### One Model Per Collection Rule

**Rule:** Một Qdrant collection chỉ dùng DUY NHẤT 1 embedding model.

**Rationale:** Vectors từ models khác nhau không comparable.

**Migration Strategy (Future):**
1. Create new collection: `ctu_chunks_bge_m3_v2`
2. Re-embed all chunks với model mới
3. Upsert vào collection mới
4. Update RAG Service config
5. Run benchmark comparison
6. Switch production traffic
7. Deactivate old collection

---

## Qdrant Configuration

### Collection Setup (MVP)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="ctu_chunks_bge_m3",
    vectors_config=VectorParams(
        size=1024,
        distance=Distance.COSINE
    )
    # HNSW: use defaults (no tuning in MVP)
)
```

**Collection Name:** `ctu_chunks_bge_m3`

**Vector Config:**
- Size: 1024 (BGE-M3 dimension)
- Distance: Cosine

**HNSW:** Use Qdrant defaults (no tuning in MVP)

### Payload Structure (Minimal)

Qdrant payload chỉ chứa metadata cần thiết cho filtering và tracing:

```json
{
  "chunk_id": "uuid",
  "parent_chunk_id": "uuid|null",
  "chunk_type": "child",
  "document_id": "quy-che-dao-tao-2024",
  "version_id": "quy-che-dao-tao-2024-v1",
  "review_status": "approved",
  "validity_status": "valid",
  "rag_status": "published",
  "confidentiality": "public",
  "is_latest": true,
  "page_start": 3,
  "page_end": 4
}
```

---

## Retrieval Pipeline

### Query Flow
```
User Query
→ Input validation
→ Vietnamese query normalization (LangChain-compatible)
→ Intent/entity extraction
→ Metadata filter
→ Hybrid retrieval (dense + sparse)
→ RRF fusion
→ Reranking
→ Parent context expansion
→ Context compression
→ LLM prompt construction
→ Answer generation
→ Citation validation
→ Response (answer + citations + assets)
```

---

## Metadata Filtering

### Production RAG Hard Filter
```text
review_status = "approved"
AND validity_status = "valid"
AND rag_status = "published"
AND confidentiality = "public"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

`published` status is only valid after `ocr_status = "done"` and successful indexing. There is no `ocr_status = "not_required"` state.

### Ranking Preference
_[Prefer is_latest=true khi conflict, allow older valid docs]_

---

## Dense Retrieval (Qdrant)

### Vector Search
_[Query embedding → cosine similarity → top-k results]_

### Top-k Configuration
_[Default: k=10, configurable]_

---

## Sparse Retrieval (PostgreSQL FTS/BM25)

### Full-Text Search
_[PostgreSQL tsvector search on chunk content]_

### BM25 Scoring
_[Optional: implement BM25 scoring]_

---

## Hybrid Retrieval & Fusion

### RRF (Reciprocal Rank Fusion)
_[Combine dense + sparse results]_

### Weighted Fusion Alternative
_[alpha * dense_score + (1-alpha) * sparse_score]_

---

## Reranking

### Reranker Model
_[Future: cross-encoder, MVP: simple heuristics]_

### Reranking Strategy
_[Re-score top-k based on query-chunk relevance]_

---

## Parent Context Expansion

### Expansion Logic
_[Child chunk → retrieve parent_id → fetch parent chunk from PostgreSQL]_

### Context Assembly
_[Send parent context to LLM instead of child only]_

---

## Prompt Construction

### Grounded Prompt Template
_[System prompt + retrieved context + user query + citation instructions]_

### Citation Instructions
_[Bắt buộc cite document + page khi claim quan trọng]_

---

## Answer Generation

### LLM Provider
_[TBD: OpenAI, Anthropic, local LLM]_

### Answer Constraints
- Chỉ trả lời dựa trên retrieved context
- Không hallucinate
- Kèm citations
- Nếu không đủ info → "Chưa có đủ thông tin"

---

## Citation Generation & Validation

### Citation Format
```json
{
  "document_id": "...",
  "version_id": "...",
  "title": "...",
  "page_start": 1,
  "page_end": 2,
  "section_title": "...",
  "source_file": "...",
  "quote_snippet": "..."
}
```

### Validation Rules
_[Citation phải match với retrieved chunks, verify document_id + page]_

---

## Evaluation Strategy

### Golden Question Set
_[10–20 real student questions với expected answers]_

### Metrics
- **Recall:** _[% questions answered correctly]_
- **Precision:** _[% answers có citations chính xác]_
- **Hallucination rate:** _[% answers có thông tin không có trong source]_

---

## Future Optimizations (Post-MVP)

### HNSW Tuning
_[m, ef_construct, ef_search parameters]_

### Advanced Reranker
_[Cross-encoder hoặc LLM-based reranker]_

### Query Expansion
_[Synonyms, related terms]_

---

**Status:** Skeleton — Cần điền chi tiết implementation  
**Priority:** P0 (Critical for MVP)

---

## Retrieval Pipeline

**Flow:**
```
Query → Normalize → Metadata Filter → Dense+Sparse → RRF Fusion → 
Rerank → Parent Expand → LLM Prompt → Answer → Citation Validate
```

**Metadata Filter (Hard):**
```python
review_status = "approved"
AND validity_status = "valid"
AND rag_status = "published"
AND confidentiality = "public"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

`published` status is only valid after `ocr_status = "done"` and successful indexing. There is no `ocr_status = "not_required"` state.

**Ranking Preference:** Prefer `is_latest=true`, but allow older valid docs.

---

## Dense & Sparse Retrieval

### Dense (Qdrant)
```python
query_vector = embed_model.encode(query, normalize=True)
results = qdrant_client.search(
    collection_name="ctu_chunks_bge_m3",
    query_vector=query_vector,
    query_filter=metadata_filter,
    limit=10
)
```

### Sparse (PostgreSQL FTS)
```sql
SELECT chunk_id, ts_rank(to_tsvector('simple', content), query) as score
FROM document_chunks
WHERE to_tsvector('simple', content) @@ query
AND [metadata_filters]
ORDER BY score DESC LIMIT 10;
```

---

## Hybrid Fusion

**RRF Formula:**
```
score(doc) = Σ 1 / (k + rank_i)
```
k=60 (default), rank_i = rank từ retriever i

---

## Parent Context Expansion

```python
child_chunks = retrieve_top_k()
parent_ids = [chunk.parent_id for chunk in child_chunks]
parent_chunks = db.query(document_chunks).filter(id.in_(parent_ids)).all()
context = "\n\n".join([p.content for p in parent_chunks])
```

---

## Prompt Construction

**Template:**
```
System: Bạn là trợ lý hỗ trợ sinh viên CTU. Chỉ trả lời dựa trên tài liệu được cung cấp.

Context: [retrieved_context]

Question: [user_query]

Instructions: Trả lời chính xác, kèm citations (document + page).
```

---

## Answer Generation

**LLM Call:**
```python
response = llm.generate(prompt, max_tokens=500, temperature=0.3)
```

**Constraints:**
- Chỉ dựa trên context
- Không hallucinate
- Bắt buộc cite sources
- Nếu không đủ info → "Chưa có đủ thông tin"

---

## Citation Validation

**Format:**
```json
{
  "document_id": "123",
  "title": "Quy Chế Đào Tạo 2024",
  "page_start": 12,
  "snippet": "...sinh viên cần nộp đơn..."
}
```

**Validation:** Verify citation matches retrieved chunks.

---

## Evaluation Strategy

**Metrics:**
- Recall: % questions answered correctly
- Precision: % citations chính xác
- Hallucination rate: % invalid claims

**Golden Set:** 10-20 real student questions

---

**References:** `.docs/RAG_RETRIEVAL.md`, `04_MODULE_SPEC.md`

**Next:** [08. OCR & Ingestion →](08_OCR_INGESTION_SPEC.md)
