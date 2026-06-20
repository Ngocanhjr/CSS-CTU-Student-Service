# RAG Retrieval Guide


## Current RAG stack summary

| Area | Current decision |
|---|---|
| OCR/parser source | `ocr-pvl` output reviewed as canonical Markdown |
| OCR internals | PaddleOCR + VietOCR + LlamaParse through `ocr-pvl` |
| Chunking/orchestration | LangChain with local CTU-specific heading/page/table/citation rules |
| Embedding | `BAAI/bge-m3` |
| Vector store | Qdrant with cosine distance |
| HNSW | Future optimization only, not current MVP |

## Chunking strategy

Use **Structure/Heading-aware Parent-Child Chunking**.

Implementation framework: **LangChain**.

This is a service-level decision, not a YAML/Pydantic metadata field. Do not add `chunking_strategy` to `DocumentMetadata` or Qdrant payload for the MVP.

Use LangChain document objects, text splitters, and retrieval chain primitives where they fit, but keep project-specific rules for CTU headings, page markers, tables, and citations in local service code. LangChain is the framework for orchestration; PostgreSQL remains the metadata source of truth and Qdrant remains the vector store.

Parent chunk:

- full procedure or major section;
- used for context expansion.

Child chunk:

- smaller section such as conditions, required documents, steps, location, processing time, forms;
- used for embedding and search.

Recommended sizes:

| Chunk type | Size |
|---|---|
| Child chunk | 300–600 tokens |
| Overlap | 50–100 tokens |
| Parent chunk | 800–1500 tokens |

Preserve tables, lists, `ocr-pvl` page markers, headings, article/clause structure, and form links.

## Child chunk metadata

```json
{
  "chunk_id": "",
  "parent_id": "",
  "chunk_level": "child",
  "document_id": "",
  "document_version_id": "",
  "department_code": "",
  "document_type_code": "",
  "domain": "",
  "audience": ["student"],
  "heading_path": [],
  "section_title": "",
  "page_start": 1,
  "page_end": 1,
  "validity_status": "valid",
  "version_role": "base",
  "is_latest": true,
  "replaces": [],
  "amends": [],
  "supplements": [],
  "rag_status": "published",
  "source_file": "",
  "checksum": "",
  "qdrant_point_id": ""
}
```

**Note:** `is_latest` is stored as metadata for ranking preference. It is NOT a hard filter. Older versions (`is_latest: false`) may still be indexed and retrieved if they remain valid, published, and provide supplementary, amended, or referenced context.

## Embedding rule

Use exactly **one embedding model per Qdrant collection**.

Production default:

```yaml
embedding_model: BAAI/bge-m3
embedding_dimension: 1024
normalize_embeddings: true
qdrant_distance: cosine
```

BGE-M3 is the required vector embedding model for the first runnable implementation. Query embeddings and document embeddings must use the same BGE-M3 configuration.

Do not mix vectors from multiple embedding models in one collection.

If changing embedding model:

1. create a new Qdrant collection or clear the old one;
2. re-embed all chunks;
3. upsert all points;
4. update RAG Service config;
5. rerun benchmark.

## Qdrant configuration for current MVP

```yaml
qdrant:
  collection: ctu_chunks_bge_m3
  vector_size: 1024
  distance: cosine
```

The current runnable-code phase must create and use the Qdrant collection with BGE-M3 vectors and cosine distance only. Do not add HNSW tuning parameters to the MVP config.

## Future HNSW optimization

HNSW is a future retrieval-performance optimization after the end-to-end RAG pipeline runs successfully.

Apply HNSW tuning only after:

1. OCR → Markdown → metadata validation → LangChain chunking → BGE-M3 embedding → Qdrant indexing → `/rag/answer` works locally;
2. there is enough data to measure retrieval latency and recall;
3. benchmark questions show a concrete speed/quality trade-off to optimize.

Future example configuration, not for current MVP:

```yaml
qdrant_future_optimization:
  hnsw:
    m: 16
    ef_construct: 100
    hnsw_ef_search: 128
```

## Retrieval pipeline

```text
User Query
→ input validation
→ LangChain-compatible Vietnamese query normalization
→ intent classification
→ entity extraction
→ metadata filter
→ hybrid retrieval on child chunks: BM25/FTS + Qdrant dense vector
→ RRF or weighted fusion
→ rerank top-k
→ version relationship expansion from PostgreSQL
→ parent context expansion
→ context compression
→ grounded LLM generation
→ citation validation
→ answer + related assets + trace
```

LangChain may orchestrate query normalization, retriever composition, reranker calls, context assembly, and generation chains. The retrieval filters, publish rules, citation validation, and PostgreSQL joins must remain explicit project code.

## Metadata filter

**Production RAG hard filter** — Always filter out documents/chunks unless:

```text
review_status = approved
validity_status = valid
rag_status = published
effective_date <= today
expiry_date IS NULL OR expiry_date >= today
```

`rag_status = published` is only reachable after `ocr_status = done`, review approval, validity check, and successful indexing. There is no `ocr_status = not_required` shortcut in the schema.

**Ranking and version preference:**

- Prefer `is_latest = true` when multiple versions of the same document exist and may conflict.
- Allow older documents if they remain valid, published, and serve as supplementary, amended, referenced, or required context for newer procedures.
- Exclude older documents only when they are explicitly expired, replaced (via `validity_status`), unpublished, invalid, or not approved.
- If a retrieved version is `version_role = supplement` or `version_role = amendment`, query PostgreSQL relationships and add the valid base version it supplements/amends.
- If a retrieved version is a valid base version with `supplemented_by` or `amended_by` relationships, add the valid related supplement/amendment versions.
- If a retrieved version is replaced, drop it and prefer the replacement version only when the replacement is valid, approved, published, and public.

## Version relationship expansion

PostgreSQL owns version governance. Qdrant may carry `version_role`, `is_latest`, and relationship IDs in payload for tracing, but retrieval must verify relationships against PostgreSQL before building context.

Use this post-processing rule after dense/sparse retrieval:

```text
1. Keep only chunks passing the hard filter.
2. Group candidates by version_id.
3. Load document_versions and document_version_relationships for those version IDs.
4. Remove versions with validity_status = replaced or rag_status != published.
5. For amendment/supplement hits, add the valid base version.
6. For base hits, add valid amendment/supplement versions.
7. Use is_latest only as a reranking tie-breaker when sources conflict.
```

## RAG endpoint contract

```http
POST /rag/answer
```

Request:

```json
{
  "query": "Em muốn xin cấp bảng điểm thì cần gì?",
  "user_role": "student",
  "domain_filter": ["pdt", "hoc_vu"],
  "prefer_latest": true,
  "session_id": "..."
}
```

Response:

```json
{
  "answer": "...",
  "citations": [
    {
      "document_id": "...",
      "version_id": "...",
      "title": "...",
      "page_start": 1,
      "page_end": 2,
      "heading_path": "...",
      "source_file": "..."
    }
  ],
  "related_assets": [
    {
      "asset_id": "...",
      "title": "...",
      "file_path": "...",
      "download_url": "..."
    }
  ],
  "trace_id": "...",
  "retrieval_debug": {
    "top_k": 8,
    "filters": {}
  }
}
```

## Anti-hallucination

- If sources are insufficient, say the system does not currently have enough source information.
- Important procedural claims must have citations.
- Do not invent fees, deadlines, required forms, departments, or eligibility conditions.
- If sources conflict, prefer explicit replacement relationships first, then `is_latest=true` and newer `effective_date`; if conflict remains, warn that verification is needed.
