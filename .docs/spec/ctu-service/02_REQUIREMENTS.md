# 02. Yêu Cầu Hệ Thống

## Tổng Quan

Tài liệu này mô tả các yêu cầu chức năng và phi chức năng cho hệ thống **CTU Student Service**. Các yêu cầu được chia thành nhóm rõ ràng theo vai trò người dùng và tính năng.

---

## Yêu Cầu Chức Năng (Functional Requirements)

### FR-1: Student Chatbot

#### FR-1.1: Natural Language Query
**Mô tả:** Sinh viên có thể đặt câu hỏi bằng tiếng Việt tự nhiên về thủ tục hành chính.

**Acceptance criteria:**
- Hỗ trợ câu hỏi tiếng Việt có dấu và không dấu
- Hiểu được các cách hỏi khác nhau cùng một ý nghĩa (e.g., "xin cấp bảng điểm", "làm thế nào để lấy bảng điểm", "cần gì để được cấp bảng điểm")
- Xử lý typos và Vietnamese-specific variations

**Priority:** P0 (Must-have)

#### FR-1.2: Grounded Answer với Citations
**Mô tả:** Mỗi câu trả lời phải dựa trên tài liệu đã được index và kèm theo citations.

**Acceptance criteria:**
- Câu trả lời chỉ được generate từ retrieved documents
- Mỗi claim quan trọng (deadline, học phí, yêu cầu hồ sơ) phải có citation
- Citation bao gồm: document title, page/section, source file
- Nếu không đủ thông tin, hệ thống trả lời "Hiện tại chưa có đủ thông tin" thay vì bịa
- Không hallucinate fees, deadlines, departments, forms

**Priority:** P0 (Must-have)

#### FR-1.3: Related Assets Display
**Mô tả:** Hiển thị các biểu mẫu, tài liệu liên quan kèm câu trả lời.

**Acceptance criteria:**
- Liệt kê forms/assets liên quan đến thủ tục được hỏi
- Mỗi asset có title, file type, download link
- Click vào asset có thể tải về hoặc xem online

**Priority:** P0 (Must-have)

#### FR-1.4: Citation Detail View
**Mô tả:** Sinh viên có thể xem chi tiết source document của từng citation.

**Acceptance criteria:**
- Click vào citation mở citation drawer/modal
- Hiển thị: document title, version, page, section, quote snippet
- Có link tải full document (nếu public)

**Priority:** P0 (Must-have)

#### FR-1.5: Chat History
**Mô tả:** Lưu lịch sử chat của sinh viên.

**Acceptance criteria:**
- Sinh viên xem lại các câu hỏi và câu trả lời trước đó
- History được lưu theo session hoặc user account
- Có thể clear history

**Priority:** P1 (Should-have)

---

### FR-2: Admin Document Management

#### FR-2.1: Document Upload
**Mô tả:** Admin upload tài liệu mới vào hệ thống.

**Acceptance criteria:**
- Hỗ trợ file types: PDF, Word, scanned images (PNG, JPG)
- Upload trả về document_id và tạo ingestion job
- Hiển thị upload progress

**Priority:** P0 (Must-have)

#### FR-2.2: Metadata Validation
**Mô tả:** Admin nhập và validate metadata cho document.

**Acceptance criteria:**
- Required fields: title, document_type, department, audience, effective_date
- Optional fields: expiry_date, code, issued_date, replaces_version_id
- Backend validate metadata rules trước khi save
- Hiển thị validation errors rõ ràng

**Priority:** P0 (Must-have)

#### FR-2.3: OCR Review
**Mô tả:** Admin review OCR output trước khi approve.

**Acceptance criteria:**
- Xem Markdown output từ ocr-pvl
- Kiểm tra page markers (`<!-- page: 1 -->`) có đủ không
- Kiểm tra tables có preserve structure không
- Sửa OCR errors trực tiếp trong UI hoặc re-upload

**Priority:** P0 (Must-have)

#### FR-2.4: Document Approval
**Mô tả:** Admin approve hoặc reject document trước khi publish vào RAG.

**Acceptance criteria:**
- Có button "Approve" và "Reject" rõ ràng
- Reject yêu cầu lý do
- Chỉ approved documents mới được index vào Qdrant
- Approved documents có `review_status = "approved"`

**Priority:** P0 (Must-have)

#### FR-2.5: Publish Control
**Mô tả:** Admin publish document vào production RAG sau khi approve.

**Acceptance criteria:**
- Sau approve, admin trigger "Publish to RAG"
- Backend: chunk → embed → index → set `rag_status = "published"`
- Published documents xuất hiện trong student search results

**Priority:** P0 (Must-have)

#### FR-2.6: Version Management
**Mô tả:** Admin quản lý versions của documents.

**Acceptance criteria:**
- Upload document mới có thể link với document cũ (replaces_version_id)
- Đánh dấu `is_latest` cho version mới nhất
- Version cũ có thể set `validity_status = "replaced"` hoặc `expiry_date`
- Old versions không tự động xóa khỏi RAG (vẫn có thể retrieve nếu còn valid)

**Priority:** P0 (Must-have)

#### FR-2.7: Ingestion Job Tracking
**Mô tả:** Admin theo dõi progress của ingestion jobs.

**Acceptance criteria:**
- Xem list ingestion jobs với current stage, progress, errors
- Click vào job xem detail: stage history, progress, errors
- Retry failed jobs

**Priority:** P0 (Must-have)

---

### FR-3: OCR và Text Extraction

#### FR-3.1: ocr-pvl Integration
**Mô tả:** Backend gọi ocr-pvl để OCR documents.

**Acceptance criteria:**
- ocr-pvl internally sử dụng PaddleOCR, VietOCR, LlamaParse
- Backend wrapper chỉ gọi ocr-pvl command/service
- Không gọi PaddleOCR/VietOCR/LlamaParse trực tiếp từ backend

**Priority:** P0 (Must-have)

#### FR-3.2: Page Marker Preservation
**Mô tả:** OCR output Markdown phải giữ page markers.

**Acceptance criteria:**
- Mỗi page có marker `<!-- page: N -->`
- Markers dùng cho citation tracing
- Backend validate Markdown có đủ page markers trước khi approve

**Priority:** P0 (Must-have)

#### FR-3.3: Table Structure Preservation
**Mô tả:** OCR giữ table structure cho tables quan trọng (học phí, deadline, requirements).

**Acceptance criteria:**
- Tables OCR output dùng Markdown table format hoặc HTML table
- Không convert tables thành plain text mất structure
- LlamaParse path được dùng cho table-heavy pages

**Priority:** P0 (Must-have)

---

### FR-4: RAG Pipeline

#### FR-4.1: Chunking với LangChain
**Mô tả:** Documents được chunk theo heading-aware parent-child strategy với LangChain.

**Acceptance criteria:**
- Parent chunks: 800–1500 tokens (full sections)
- Child chunks: 300–600 tokens (sub-sections)
- Overlap: 50–100 tokens
- Preserve headings, lists, tables, page markers

**Priority:** P0 (Must-have)

#### FR-4.2: Embedding với BGE-M3
**Mô tả:** Child chunks được embed với BAAI/bge-m3.

**Acceptance criteria:**
- Embedding dimension: 1024
- Normalize embeddings: true
- Chỉ dùng BGE-M3, không mix models

**Priority:** P0 (Must-have)

#### FR-4.3: Qdrant Indexing
**Mô tả:** Child chunks được index vào Qdrant collection.

**Acceptance criteria:**
- Collection name: `ctu_chunks_bge_m3`
- Distance metric: cosine
- Payload chứa: chunk_id, document_id, version_id, validity_status, rag_status, is_latest, page_start, page_end
- HNSW không tune trong MVP

**Priority:** P0 (Must-have)

#### FR-4.4: Metadata Filtering
**Mô tả:** Retrieval apply production RAG hard filter.

**Acceptance criteria:**
- Filter: `review_status = approved AND validity_status = valid AND rag_status = published AND confidentiality = public AND effective_date <= today AND (expiry_date IS NULL OR >= today)`
- Không yêu cầu `is_latest = true` (chỉ dùng cho ranking)

**Priority:** P0 (Must-have)

#### FR-4.5: Hybrid Retrieval
**Mô tả:** Kết hợp dense vector search (Qdrant) và sparse search (PostgreSQL FTS/BM25).

**Acceptance criteria:**
- Dense: Qdrant vector similarity search
- Sparse: PostgreSQL full-text search trên chunk content
- Fusion: RRF (Reciprocal Rank Fusion)

**Priority:** P1 (Should-have — MVP có thể chỉ dùng dense)

#### FR-4.6: Reranking
**Mô tả:** Rerank top-k retrieved chunks.

**Acceptance criteria:**
- Reranker model (e.g., cross-encoder hoặc simple heuristics)
- Rerank dựa trên query-chunk relevance
- Return top-k sau rerank

**Priority:** P1 (Should-have — MVP có thể skip)

#### FR-4.7: Parent Context Expansion
**Mô tả:** Expand child chunks thành parent chunks để có đủ context.

**Acceptance criteria:**
- Retrieve parent chunk từ PostgreSQL dựa trên parent_id
- Gửi parent context vào LLM thay vì chỉ child chunk

**Priority:** P0 (Must-have)

#### FR-4.8: Citation Validation
**Mô tả:** Validate citations trong answer có match với retrieved chunks không.

**Acceptance criteria:**
- Mỗi citation phải có document_id, page, section
- Backend verify citation refs có trong retrieved chunks
- Nếu không match, log warning

**Priority:** P0 (Must-have)

---

### FR-5: Security và Governance

#### FR-5.1: Authentication
**Mô tả:** Users phải authenticate để dùng hệ thống.

**Acceptance criteria:**
- Student: username/password hoặc CTU SSO (future)
- Admin: username/password với role check
- Session/JWT token management

**Priority:** P1 (Should-have — MVP có thể skip auth)

#### FR-5.2: Authorization (RBAC)
**Mô tả:** Role-based access control cho student và admin.

**Acceptance criteria:**
- Student role: chỉ access chat, xem citations, tải public assets
- Admin role: access admin dashboard, upload, review, approve, publish
- Backend enforce RBAC trên mọi endpoints

**Priority:** P1 (Should-have — MVP có thể skip hoặc simple role check)

#### FR-5.3: Document Governance
**Mô tả:** Chỉ approved, valid, published documents được dùng cho student RAG.

**Acceptance criteria:**
- Hard filter 6 conditions (xem FR-4.4)
- Admin không thể bypass validation rules
- Confidential documents không bao giờ xuất hiện trong student search

**Priority:** P0 (Must-have)

#### FR-5.4: Audit Logging
**Mô tả:** Log các admin actions quan trọng.

**Acceptance criteria:**
- Log: upload, approve, reject, publish, unpublish, delete
- Log include: user_id, timestamp, action, document_id
- Logs có thể query để audit trail

**Priority:** P2 (Nice-to-have)

---

## Yêu Cầu Phi Chức Năng (Non-Functional Requirements)

### NFR-1: Performance

#### NFR-1.1: Response Time
- **Student query:** `/rag/answer` response trong < 5s (P95)
- **Admin actions:** Upload, approve, publish response trong < 3s (P95)
- **Retrieval:** Qdrant search < 500ms (P95)

#### NFR-1.2: Throughput
- **MVP target:** Support 10 concurrent users
- **Future:** Support 100+ concurrent users

#### NFR-1.3: Scalability
- **MVP:** Single-instance deployment (Docker Compose local)
- **Future:** Horizontal scaling (Qdrant cluster, backend replicas)

---

### NFR-2: Reliability

#### NFR-2.1: Availability
- **MVP:** Best-effort (dev environment)
- **Future production:** 99% uptime

#### NFR-2.2: Data Integrity
- **PostgreSQL:** ACID transactions cho metadata
- **Qdrant:** Eventual consistency acceptable
- **Documents:** Checksum validation

#### NFR-2.3: Error Handling
- Backend trả về structured error responses với error codes
- Frontend hiển thị user-friendly error messages
- Retry logic cho transient failures (Qdrant connection, LLM API)

---

### NFR-3: Security

#### NFR-3.1: Data Confidentiality
- `confidentiality = "public"` documents only trong student RAG
- `confidentiality = "internal"` chỉ admin xem được
- Secrets (API keys, DB passwords) trong `.env`, không commit

#### NFR-3.2: Input Validation
- Validate mọi user input trước khi xử lý
- Sanitize query strings để tránh injection

#### NFR-3.3: Citation Integrity
- Không cho phép modify citations
- Citations phải traceable về source documents

---

### NFR-4: Usability

#### NFR-4.1: Student UI
- Chat interface đơn giản, dễ dùng trên mobile
- Response time feedback (loading spinner)
- Citation rõ ràng, dễ click xem detail

#### NFR-4.2: Admin UI
- Workflow rõ ràng: upload → review → approve → publish
- Status badges cho ingestion jobs
- Validation errors hiển thị inline

---

### NFR-5: Maintainability

#### NFR-5.1: Code Quality
- Follow backend structure quy định (xem BACKEND_STRUCTURE.md)
- Pydantic schemas cho tất cả API requests/responses
- Type hints cho Python code

#### NFR-5.2: Documentation
- API docs auto-generated (FastAPI Swagger)
- README trong mỗi module
- Specs luôn sync với code

#### NFR-5.3: Testability
- Unit tests cho core logic (chunking, embedding, retrieval)
- Integration tests cho APIs
- End-to-end test cho vertical slice

---

### NFR-6: Observability

#### NFR-6.1: Logging
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Trace IDs cho mỗi request

#### NFR-6.2: Monitoring
- **MVP:** File-based logs
- **Future:** Prometheus metrics, Grafana dashboards

#### NFR-6.3: Debugging
- Retrieval debug info: top-k chunks, scores, filters applied
- Citation traceability: answer → chunks → documents

---

## Acceptance Criteria Tổng Thể

### Vertical Slice Success (2026-06-19)

✅ **Đã hoàn thành khi:**
1. 3–5 documents đã được OCR → reviewed → indexed
2. Student có thể hỏi 10–20 test questions và nhận câu trả lời có citations
3. Admin có thể upload, review, approve, publish documents qua Flutter UI
4. Backend `/rag/answer` endpoint chạy ổn định
5. Qdrant collection `ctu_chunks_bge_m3` có vectors của 3–5 documents
6. PostgreSQL có đầy đủ metadata, chunks, assets
7. Flutter chat screen hiển thị answer + citation drawer

❌ **Không yêu cầu cho MVP:**
- HNSW tuning
- Production deployment
- Advanced reranker
- Full RBAC với nhiều roles
- A/B testing

---

## Liên Kết

- **Kiến trúc:** [03_SYSTEM_ARCHITECTURE.md](03_SYSTEM_ARCHITECTURE.md)
- **Database schema:** [05_DATABASE_SPEC.md](05_DATABASE_SPEC.md)
- **RAG pipeline:** [07_RAG_SPEC.md](07_RAG_SPEC.md)
- **Implementation plan:** [11_IMPLEMENTATION_PLAN.md](11_IMPLEMENTATION_PLAN.md)

---

**Phiên bản:** 1.0  
**Ngày tạo:** 2026-06-10  
**Trạng thái:** Draft
