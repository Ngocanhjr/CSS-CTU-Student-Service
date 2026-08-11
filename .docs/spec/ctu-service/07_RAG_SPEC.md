# 07. Đặc Tả RAG Pipeline

**Version:** 3.0  
**Status:** Final theo quyết định schema hiện tại

## Stack

| Component | Decision |
|---|---|
| OCR/parser input | LlamaParse only |
| Chunking | LangChain / `langchain-text-splitters` |
| Embedding | `BAAI/bge-m3`, 1024 dimensions, normalized |
| Vector DB | Qdrant |
| Sparse search | PostgreSQL FTS/BM25 |
| Fusion | RRF |
| Advanced reranker | Post-MVP |
| HNSW tuning | Post-MVP |

## Lifecycle

```text
upload
-> LlamaParse
-> canonical Markdown review
-> metadata validation
-> chunking
-> embedding
-> Qdrant upsert
-> rag_status = published
```

Search is allowed only after:

```text
ocr_status = done
AND review_status = approved
AND rag_status = published
```

## Markdown metadata

Required:

```yaml
document_key: ""
version_key: ""
title: ""
document_type: ""
domain: ""
audience: []
```

Optional:

```yaml
code: ""
issued_date: ""
source_url: ""
source_path: ""
canonical_markdown_path: ""
language: "vi"
issuing_authority: ""
signer_name: ""
accessed_date: ""
ocr_status: "done"
review_status: "not_reviewed"
rag_status: "not_indexed"
status_note: ""
```

Do not add `rag_status`, `chunking_strategy`, or relationship fields to YAML.

## Chunking

- Parent chunks represent major Markdown sections.
- Child chunks are embedded and searched.
- Parent-child DB relation uses `document_chunks.parent_chunk_id`.
- Payload relation uses `parent_chunk_key`.
- `chunk_type` is `parent` or `child`.

Stable keys:

```text
<version_key>::p::<parent_index>
<version_key>::c::<child_index>
```

## Retrieval flow

```text
Query
-> normalize Vietnamese text
-> apply metadata filter
-> dense retrieval in Qdrant
-> sparse retrieval in PostgreSQL
-> RRF fusion
-> parent context expansion
-> prompt construction
-> answer generation
-> citation validation
```

Hybrid retrieval is required in MVP. Dense-only retrieval is not enough for official procedure lookup.

## Qdrant payload

```json
{
  "chunk_key": "quy-che-dao-tao-2024-v1::c::0001",
  "parent_chunk_key": "quy-che-dao-tao-2024-v1::p::0001",
  "postgres_chunk_id": 123,
  "chunk_type": "child",
  "document_key": "quy-che-dao-tao-2024",
  "version_key": "quy-che-dao-tao-2024-v1",
  "review_status": "approved",
  "rag_status": "published",
  "is_latest": true,
  "page_start": 3,
  "page_end": 4
}
```

## API

Canonical API details are maintained in `06_API_SPEC.md`.

The response must include:

- grounded answer;
- citations from retrieved chunks;
- related assets from `document_assets` + `assets`;
- trace id for debugging.

## Citation rules

- Every important procedural claim needs a citation.
- Citation must match a retrieved chunk and known `document_key` / `version_key`.
- If evidence is missing, answer that the system does not have enough source information.

## Post-MVP

- Cross-encoder or LLM reranker.
- HNSW tuning.
- Advanced query expansion.
