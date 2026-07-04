# Legacy Implementation Notes

This file is kept only as an old working note.

Current source of truth:

- `chatbot/.docs/spec/ctu-service/05_DATABASE_SPEC.md`
- `chatbot/.docs/CODING_RULES.md`
- `chatbot/.docs/spec/ctu-service/07_RAG_SPEC.md`

Final decisions:

- Schema has 9 tables.
- OCR/parser is LlamaParse only.
- Use `chunk_type`, not `chunk_type`.
- Use `parent_chunk_id`, not `parent_chunk_id`.
- Use `current_step`, not `current_step`.
- Use `/api/v1/rag/answer`.
