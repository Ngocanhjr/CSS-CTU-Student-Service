# CTU Service Spec Index

Current source of truth for implementation:

1. `01_PROJECT_OVERVIEW.md`
2. `02_REQUIREMENTS.md`
3. `03_SYSTEM_ARCHITECTURE.md`
4. `04_MODULE_SPEC.md`
5. `05_DATABASE_SPEC.md`
6. `06_API_SPEC.md`
7. `07_RAG_SPEC.md`
8. `08_OCR_INGESTION_SPEC.md`
9. `09_FRONTEND_SPEC.md`
10. `11_IMPLEMENTATION_PLAN.md`

Final decisions:

- Frontend: Flutter.
- Backend: FastAPI.
- OCR/parser: LlamaParse runs **externally**. This backend receives canonical Markdown that has already been OCR'd and reviewed.
- Schema: 9 tables.
- Retrieval: dense + sparse + RRF in MVP.
- API prefix: `/api/v1`.
- Security/governance rules are kept in `02_REQUIREMENTS.md`.
