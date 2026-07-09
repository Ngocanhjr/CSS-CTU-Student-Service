# Flowchart Report - guild_implement

Generated diagrams for implementation flows found in `chatbot/.docs/guild_implement`.

| Diagram | Source guide(s) | Purpose |
|---|---|---|
| `09a_pre_chunk_parsing_normalization_flow.mmd` | `09A_PRE_CHUNK_PARSING_NORMALIZATION_GUIDE.md` | Main flow from OCR/loader to Qdrant, including page-aware normalization and chunking. |
| `09a_page_range_citation_fix_flow.mmd` | `09A_PRE_CHUNK_PARSING_NORMALIZATION_GUIDE.md` | Shows why page blocks must be split before heading split, then merged by `heading_path` for correct citation pages. |
| `07_13_ingestion_pipeline_publish_modes_flow.mmd` | `07_DETAILED_RAG_INGESTION_IMPLEMENTATION_GUIDE.md`, `13_PART_F_PIPELINE_ORCHESTRATION_GUIDE.md` | End-to-end ingestion orchestration with `publish=false` and `publish=true` branches. |
| `08_chunk_key_db_qdrant_contract_flow.mmd` | `08_PART_A_DB_SCHEMA_CONTRACT_GUIDE.md` | Stable `chunk_key` contract across schema, repository, PostgreSQL, Qdrant, and retrieval hydration. |
| `14_15_embedding_qdrant_indexing_flow.mmd` | `14_PART_G_EMBEDDING_GUIDE.md`, `15_PART_H_QDRANT_VECTORSTORE_GUIDE.md` | Child chunk embedding, Qdrant upsert, payload trace fields, and DB indexing update. |
| `16_retrieval_citation_flow.mmd` | `16_PART_I_RETRIEVAL_GUIDE.md` | Retrieval decision flow, student filter, Qdrant search, PostgreSQL hydration, and citation building. |

Checked guide folder:

```text
chatbot/.docs/guild_implement
```

The most explicit flow blocks were in `06`, `07`, `08`, `09A`, `13`, `14`, `15`, and `16`. The diagrams above avoid duplicating the same pipeline text by grouping related guides into canonical flows.
