# 12. Câu Hỏi Chưa Giải Quyết

## LLM Provider

**Question:** LLM provider nào sẽ dùng cho answer generation?

**Options:**
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Local LLM (Llama, Mistral)
- Google (Gemini)

**Decision needed:** _[TBD]_

**Impact:** API costs, latency, answer quality

---

## Embedding Model Alternatives

**Question:** Có nên thử embedding models khác không?

**Current:** BAAI/bge-m3 (1024-dim)

**Alternatives:**
- OpenAI text-embedding-3-large (3072-dim)
- Cohere embed-multilingual-v3.0
- Local Vietnamese embedding models

**Decision needed:** _[Keep BGE-M3 cho MVP, evaluate alternatives sau]_

**Impact:** Retrieval quality, costs, latency

---

## Reranker Model

**Question:** Reranker model nào dùng?

**Options:**
- Cross-encoder (e.g., ms-marco-MiniLM)
- LLM-based reranker
- Simple heuristics (BM25, TF-IDF)
- Skip reranker trong MVP

**Decision needed:** _[TBD — MVP có thể skip reranker]_

**Impact:** Retrieval precision

---

## Hybrid Retrieval Priority

**Question:** Hybrid retrieval (dense + sparse) có cần cho MVP không?

**Current plan:** Dense only (Qdrant vector search)

**Alternative:** Add PostgreSQL FTS + RRF fusion

**Decision needed:** _[Evaluate sau khi dense retrieval tested]_

**Impact:** Retrieval recall

---

## Backend Framework Details

**Question:** FastAPI version và dependencies?

**Current:** FastAPI (latest stable)

**Clarifications needed:**
- ASGI server: Uvicorn or Hypercorn?
- Database ORM: SQLAlchemy or SQLModel?
- Migration tool: Alembic?

**Decision needed:** _[TBD]_

---

## Frontend State Management

**Question:** Riverpod hay BLoC cho Flutter?

**Options:**
- Riverpod (simpler, modern)
- BLoC (strict event/state separation)

**Decision needed:** _[TBD — recommend Riverpod cho MVP]_

**Impact:** Developer experience, code structure

---

## Storage Path Conventions

**Question:** File storage path structure?

**Current suggestion:**
```
storage/
├── raw/              # Original uploads
├── ocr_output/       # OCR Markdown
├── canonical/        # Reviewed Markdown
└── assets/           # Forms, attachments
```

**Decision needed:** _[Confirm structure]_

**Impact:** File organization, backup strategy

---

## Deployment Target

**Question:** Final deployment target?

**MVP:** Docker Compose (local)

**Production options:**
- Self-hosted VPS
- AWS (ECS, RDS, S3)
- Google Cloud
- Azure
- Hybrid (backend on-prem, Qdrant cloud)

**Decision needed:** _[TBD after MVP]_

**Impact:** Infrastructure costs, scaling strategy

---

## Authentication Strategy

**Question:** CTU SSO integration?

**MVP:** Simple username/password

**Future:** CTU SSO (LDAP, SAML, OAuth)

**Decision needed:** _[TBD — MVP skip SSO]_

**Impact:** User experience, security

---

## Metadata Schema Finalization

**Question:** Metadata fields đã đầy đủ chưa?

**Current fields:** _[Xem 05_DATABASE_SPEC.md]_

**Potential additions:**
- `author` field
- `tags` or `keywords` array
- `related_procedures` links
- `approval_history` JSON

**Decision needed:** _[Start minimal, add khi cần]_

---

## HNSW Tuning Timeline

**Question:** Khi nào tune HNSW?

**Answer:** Sau khi MVP chạy thành công và có benchmark data

**Trigger conditions:**
- Dataset > 10,000 documents
- Retrieval latency > 500ms P95
- Recall drops below threshold

**Decision needed:** _[Monitor metrics first]_

---

## Document Version Strategy

**Question:** Có giữ hết older versions trong Qdrant không?

**Current plan:** Index all valid versions (không chỉ latest)

**Rationale:** Older docs có thể cần reference

**Alternative:** Only index `is_latest=true`

**Decision needed:** _[Keep current plan]_

**Impact:** Vector DB size, retrieval complexity

---

## Confidentiality Levels

**Question:** Có cần thêm confidentiality levels không?

**Current:** public, internal, confidential

**Potential additions:**
- `restricted` (specific roles only)
- `department_only` (department-specific)

**Decision needed:** _[Start với 3 levels, expand nếu cần]_

---

## LlamaParse Usage

**Question:** LlamaParse có cần cho tất cả documents không?

**Current plan:** Chỉ dùng cho table-heavy pages

**Alternative:** Dùng LlamaParse cho all pages

**Decision needed:** _[Router logic inside ocr-pvl decides]_

**Impact:** OCR quality vs. cost/latency

---

## Evaluation Metrics

**Question:** Metrics nào dùng để đánh giá RAG quality?

**Suggested:**
- Recall@k
- Precision@k
- MRR (Mean Reciprocal Rank)
- Hallucination rate
- Citation accuracy

**Decision needed:** _[Define golden question set]_

---

## Chat History Persistence

**Question:** Chat history lưu bao lâu?

**Options:**
- Session-based (clear on logout)
- 30 days
- 90 days
- Unlimited với user account

**Decision needed:** _[TBD]_

**Impact:** Database size, privacy

---

## Asset Management

**Question:** Assets được store ở đâu?

**MVP:** Local filesystem

**Future options:**
- MinIO (S3-compatible)
- AWS S3
- Azure Blob Storage

**Decision needed:** _[Local MVP, cloud sau]_

---

## Monitoring và Observability

**Question:** Monitoring stack cho production?

**MVP:** File-based logs

**Future options:**
- Prometheus + Grafana
- ELK Stack
- Datadog
- Cloud-native monitoring (AWS CloudWatch, GCP Stackdriver)

**Decision needed:** _[TBD after MVP]_

---

**Status:** Living document — Cập nhật khi có quyết định mới  
**Priority:** P2
