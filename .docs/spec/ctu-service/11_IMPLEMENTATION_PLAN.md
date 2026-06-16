# 11. Kế Hoạch Triển Khai

**Version:** 1.0  
**Timeline:** 2026-06-08 to 2026-06-19  
**Goal:** End-to-end vertical slice với 3-5 documents

---

## Phase 1: Setup (Jun 8-9)

**Tasks:**
- Docker Compose (PostgreSQL, Qdrant)
- Backend skeleton (FastAPI folders)
- Frontend skeleton (Flutter)
- Select 3-5 seed documents

**Done:** ✅ Services running, projects initialized

---

## Phase 2: OCR + Cleaning (Jun 10-11)

**Tasks:**
- Run ocr-pvl on 3-5 documents
- Verify page markers + tables
- Clean Markdown → 01_Dataset/

**Done:** ✅ Clean Markdown với page markers

---

## Phase 3: Metadata + Validation (Jun 12-13)

**Tasks:**
- Add YAML frontmatter
- Implement metadata validation
- Create PostgreSQL tables
- Validate 3-5 documents

**Done:** ✅ Metadata validated, stored in DB

---

## Phase 4: Chunking + Embedding (Jun 14-15)

**Tasks:**
- Implement LangChain chunking (parent-child)
- Implement BGE-M3 embedding
- Create document_chunks table
- Chunk + embed 3-5 documents

**Done:** ✅ Chunks stored with embeddings

---

## Phase 5: Qdrant Indexing (Jun 16)

**Tasks:**
- Setup Qdrant collection
- Implement upsert logic
- Index 3-5 documents
- Verify vectors searchable

**Done:** ✅ Vectors indexed in Qdrant

---

## Phase 6: RAG /answer Endpoint (Jun 17-18)

**Tasks:**
- Implement dense + sparse retrieval
- Implement RRF fusion
- Implement parent context expansion
- Build /rag/answer endpoint
- Test with real questions

**Done:** ✅ /rag/answer returns answers + citations

---

## Phase 7: Frontend Chat UI (Jun 19)

**Tasks:**
- Flutter chat screen
- Call /rag/answer API
- Display answer + citations
- Test end-to-end

**Done:** ✅ Student can ask question and get answer

---

## Testing Milestones

- [ ] 3-5 documents searchable
- [ ] 5-10 test queries return correct answers
- [ ] Citations accurate (document + page)
- [ ] No hallucinations detected

---

**References:** `.docs/IMPLEMENTATION_ORDER.md`

**Next:** [12. Open Questions →](12_OPEN_QUESTIONS.md)
- ✅ Backend validates metadata successfully
- ✅ Metadata stored in PostgreSQL

---

### Phase 4: LangChain Chunking + BGE-M3 Embedding (2026-06-14 to 2026-06-15)

**Goal:** _[Parent/child chunks persisted, embeddings generated]_

**Tasks:**
- [ ] Implement LangChain chunking (`app/ingestion/chunking`)
- [ ] Parent-child strategy: 800–1500 / 300–600 tokens
- [ ] Store chunks in PostgreSQL (`document_chunks` table)
- [ ] Implement BGE-M3 embedding service (`app/embedding`)
- [ ] Embed child chunks (1024-dim vectors)
- [ ] Store embeddings temporarily (in-memory or file)

**Output:**
- Chunks table populated
- Child chunks embedded với BGE-M3
- Embeddings ready for Qdrant indexing

**Done Criteria:**
- ✅ All 3–5 documents chunked into parent/child
- ✅ Child chunks embedded successfully
- ✅ Total chunks: ~50–200 (estimate)

---

### Phase 5: Qdrant Indexing + Retrieval POC (2026-06-16 to 2026-06-17)

**Goal:** _[Qdrant collection created, vectors indexed, retrieval works]_

**Tasks:**
- [ ] Implement Qdrant client (`app/vectorstore`)
- [ ] Create collection `ctu_chunks_bge_m3` (1024-dim, cosine)
- [ ] Upsert child chunks with minimal payload
- [ ] Implement dense retrieval (`app/retrieval`)
- [ ] Apply production RAG hard filter (6 conditions)
- [ ] Test retrieval: query → top-k chunks
- [ ] Implement parent context expansion

**Output:**
- Qdrant collection với 50–200 points
- Retrieval service returns relevant chunks
- Hard filter applied correctly

**Done Criteria:**
- ✅ All child chunks indexed in Qdrant
- ✅ Test queries return relevant chunks
- ✅ Metadata filtering works (approved, valid, published, public, dates)

---

### Phase 6: `/rag/answer` Vertical Slice (2026-06-18)

**Goal:** _[Backend answer endpoint returns grounded answer với citations]_

**Tasks:**
- [ ] Implement LLM prompt builder (`app/llm`)
- [ ] Implement answer generator (`app/llm`)
- [ ] Implement citation extraction and validation (`app/llm`)
- [ ] Implement `/rag/answer` endpoint (`app/api`)
- [ ] Test với 10–20 real student questions
- [ ] Verify citations match retrieved chunks
- [ ] Add related assets logic

**Output:**
- `/rag/answer` endpoint working
- Returns: answer + citations + related assets
- Grounded answers, no hallucination

**Done Criteria:**
- ✅ Endpoint responds to queries
- ✅ Answers include citations
- ✅ Citations traceable to source documents
- ✅ No hallucinated information

---

### Phase 7: Run and Verify Code (2026-06-19)

**Goal:** _[Local code path runs end-to-end, smoke test passed]_

**Tasks:**
- [ ] Create Flutter chat screen (basic)
- [ ] Chat screen calls `/rag/answer`
- [ ] Display answer + citations
- [ ] Citation drawer (click to view detail)
- [ ] Test end-to-end với 10–20 questions
- [ ] Fix bugs
- [ ] Document known issues

**Output:**
- Flutter chat UI working locally
- End-to-end flow: question → answer → citations
- Smoke test passed

**Done Criteria:**
- ✅ 3–5 documents fully indexed
- ✅ 10–20 test questions answered correctly
- ✅ Citations displayed in Flutter UI
- ✅ No critical bugs blocking demo

---

## Implementation Order: Backend Modules

**Suggested coding order:**

1. `app/config` — Settings, environment loading
2. `app/databases` — PostgreSQL session, base models, core tables
3. `app/schemas` — Pydantic DTOs
4. `app/api` — Health check, basic routers
5. `app/ingestion` — Metadata validation, job tracking
6. `app/ingestion` — ocr-pvl integration, LangChain chunking
7. `app/embedding` — BGE-M3 service
8. `app/vectorstore` — Qdrant client, collection setup, upsert/search
9. `app/retrieval` — Metadata filters, dense retrieval, parent expansion
10. `app/llm` — Prompt builder, answer generator, citations
11. `app/api/rag.py` — `/rag/answer` endpoint
12. Flutter UI — Chat screen, citation drawer

---

## Testing Milestones

### Unit Tests
- Metadata validation logic
- Chunking logic
- Embedding service
- Citation extraction

### Integration Tests
- `/rag/answer` endpoint
- Metadata validation endpoint
- Ingestion job workflow

### End-to-End Test
- Full vertical slice: upload → OCR → review → chunk → embed → index → query → answer

---

## Risk Mitigation

### Risk: OCR quality low
**Mitigation:** Manual review required, re-OCR with different settings

### Risk: Retrieval returns irrelevant chunks
**Mitigation:** Tune metadata filters, add query normalization, check embedding quality

### Risk: LLM hallucination
**Mitigation:** Strict grounded prompts, citation validation, test với golden questions

### Risk: Qdrant connection fails
**Mitigation:** Retry logic, fallback to PostgreSQL FTS only

---

## Out of Scope for MVP (Post-2026-06-19)

❌ **Not in vertical slice:**
- HNSW tuning
- Advanced reranker (cross-encoder)
- Full RBAC với nhiều roles
- Production deployment (cloud, scaling)
- Mobile app published to store
- Large-scale dataset (100+ documents)
- Hybrid retrieval (dense + sparse fusion) — optional for MVP
- A/B testing framework
- Monitoring dashboards

---

**Status:** Skeleton — Cần điền chi tiết tasks và done criteria  
**Priority:** P0 (Critical for MVP)
