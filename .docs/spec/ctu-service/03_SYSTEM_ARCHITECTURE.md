# 03. Kiến Trúc Hệ Thống

**Version:** 1.0  
**Last Updated:** 2026-06-10  
**Status:** Final

---

## Mục Lục

1. [Tổng Quan Kiến Trúc](#tổng-quan-kiến-trúc)
2. [Pinned Technology Decisions](#pinned-technology-decisions)
3. [Layer Responsibilities](#layer-responsibilities)
4. [Backend Folder Structure](#backend-folder-structure-authoritative)
5. [Data Flow](#data-flow)
6. [Deployment View](#deployment-view)
7. [Logging và Error Handling](#logging-và-error-handling)

---

## Tổng Quan Kiến Trúc

### High-Level Architecture

```text
Student/Admin Users
        ↓
Flutter Frontend (Mobile/Web)
        ↓
Backend API (FastAPI)
        ↓
  ┌─────┴─────┐
  ↓           ↓
RAG Service   Ingestion Service
  ↓           ↓
PostgreSQL + Qdrant + File Storage
```

### Architecture Diagram Reference
📊 **[Xem sơ đồ chi tiết: ../../diagrams/mermaid/system_container.mmd](../../diagrams/mermaid/system_container.mmd)**

---

## Pinned Technology Decisions

**Implementation Period:** `2026-06-08` đến `2026-06-19`

Các quyết định công nghệ sau đây **đã được fix** và không thay đổi trong giai đoạn MVP:

| Lĩnh vực | Quyết định | Lý do |
|----------|------------|-------|
| **Frontend** | Flutter | Cross-platform (mobile + web), Material Design 3 |
| **Backend API** | FastAPI | Performance cao, async support, automatic OpenAPI docs |
| **OCR Tool** | `ocr-pvl` | Tích hợp sẵn PaddleOCR + VietOCR + LlamaParse |
| **RAG Framework** | LangChain | Ecosystem rộng, chunking utilities, retrieval composition |
| **Chunking** | LangChain heading-aware parent-child | Preserve structure, enable context expansion |
| **Embedding Model** | `BAAI/bge-m3` | State-of-art multilingual, 1024 dims, Vietnamese support |
| **Vector DB** | Qdrant | Rust-based, fast, easy metadata filter, Docker-friendly |
| **Relational DB** | PostgreSQL | Source of truth cho metadata, versioning, governance |
| **Retrieval Strategy** | Hybrid (Dense + Sparse) | Dense vector search + BM25/FTS → RRF fusion |
| **Storage** | Local filesystem (MVP) | Sau này migrate sang MinIO/S3-compatible |
| **Queue** | Sync/Background tasks (MVP) | Sau này thêm Celery/RQ nếu cần scale |
| **Distance Metric** | Cosine similarity | Standard cho normalized embeddings |

### Công Nghệ KHÔNG Sử Dụng (MVP)

- ❌ React, Next.js, Tailwind (Frontend chỉ dùng Flutter)
- ❌ Django, Express.js (Backend chỉ dùng FastAPI)
- ❌ Pinecone, Weaviate, Milvus (Vector DB chỉ dùng Qdrant)
- ❌ HNSW tuning (Tối ưu hóa sau MVP)
- ❌ Elasticsearch (Dùng PostgreSQL FTS + Qdrant dense search)

---

## Layer Responsibilities

### 1. Frontend Layer (Flutter)

**Vai trò:** Presentation và user interaction

**Trách nhiệm:**
- Chat UI cho sinh viên (query input, answer display, citation drawer)
- Admin dashboard (document upload, review, publish)
- Citation display với link đến source pages
- Asset/form download links
- State management (Riverpod/BLoC)
- API client integration (Dio hoặc generated client)

**Nguyên tắc quan trọng:**
- Flutter là **presentation client only**
- Không connect trực tiếp đến PostgreSQL hoặc Qdrant
- Không quyết định document validity/publish status
- Không hard-code procedure content, deadlines, fees, forms
- Không bỏ qua citation validation
- Luôn gọi Backend API và render returned data

### 2. Backend API Layer (FastAPI)

**Vai trò:** API gateway và business orchestration

**Trách nhiệm:**
- Authentication và authorization (JWT, RBAC)
- CRUD endpoints cho departments, document_types, documents, versions, assets
- Ingestion job creation và status tracking
- Chat history management (future)
- Request validation và response formatting
- Error handling và exception translation

**Nguyên tắc:**
- Route handlers phải **thin** (gọi service layer)
- Không chứa business logic trong route handlers
- Validate input với Pydantic schemas
- Return typed response schemas
- Log requests và errors

### 3. RAG Service Layer

**Vai trò:** Retrieval-augmented generation pipeline

**Trách nhiệm:**
- Query normalization (Vietnamese text processing)
- Intent và entity extraction (optional, future)
- Metadata filter construction
- **Dense retrieval** từ Qdrant (vector search)
- **Sparse retrieval** từ PostgreSQL (FTS/BM25)
- **Hybrid fusion** (RRF - Reciprocal Rank Fusion)
- **Reranking** (optional, future)
- **Parent context expansion** (child chunk → parent document section)
- Context compression và assembly
- LLM prompt construction
- Grounded answer generation với LLM
- Citation validation và formatting

**LangChain Integration:**
- Dùng LangChain cho retrieval composition
- Dùng LangChain query transformation
- Dùng LangChain context assembly
- Giữ metadata filters và business rules trong project code

### 4. Data Layer

**PostgreSQL (Source of Truth):**
- Metadata: departments, document_types, documents, document_versions
- Document chunks với parent-child relationships
- Assets và document_assets relationships
- Ingestion jobs và status tracking
- Governance fields: review_status, validity_status, rag_status, confidentiality
- Full-text search (FTS) cho sparse retrieval

**Qdrant (Vector Search Index):**
- Vector embeddings của child chunks (1024-dim BGE-M3)
- Minimal payload: chunk_id, document_id, version_id, page_number, is_published
- Metadata filters: review_status, validity_status, rag_status, confidentiality, dates
- Không lưu rich data (join từ PostgreSQL khi cần)

**File Storage:**
- Original uploaded files (PDF, DOCX, images)
- OCR outputs (Markdown)
- Canonical Markdown trong `01_Dataset` (sau human review)
- Downloadable assets (forms, templates)

### 5. OCR/Ingestion Layer

**Vai trò:** Document processing pipeline

**Trách nhiệm:**
- File upload và validation
- **OCR orchestration** (gọi `ocr-pvl`)
  - PaddleOCR: layout detection, text regions
  - VietOCR: Vietnamese text recognition
  - LlamaParse: table-heavy pages, complex layouts
- Markdown normalization
- Page marker preservation (`<!-- page: 4 -->`)
- YAML metadata validation (frontmatter)
- Human review coordination
- **Chunking với LangChain** (heading-aware parent-child)
- **Embedding với BGE-M3** (batch processing)
- **Qdrant indexing** (upsert vectors)
- Job status tracking

**Output:**
- Cleaned Markdown với structure preserved
- Parent-child chunks trong PostgreSQL
- Vector embeddings trong Qdrant
- Indexing status updates

---

## Backend Folder Structure (Authoritative)

### Current Structure

```text
backend/
├── app/
│   ├── api/              # FastAPI routers
│   ├── config/           # Settings, environment variables
│   ├── core/             # Shared utilities (exceptions, logging, security)
│   ├── databases/        # PostgreSQL models, sessions
│   ├── embedding/        # BGE-M3 embedding service
│   ├── ingestion/        # OCR, chunking, validation, indexing
│   ├── llm/              # LLM client, prompts, answer generation
│   ├── retrieval/        # Dense/sparse retrieval, fusion, reranking
│   ├── schemas/          # Pydantic request/response DTOs
│   ├── vectorstore/      # Qdrant client, collections
│   ├── __init__.py
│   └── main.py           # FastAPI app entrypoint
├── logs/
├── requirements.txt
├── .dockerignore
└── README.md
```

### Folder-to-Responsibility Mapping

| Folder | Trách nhiệm chi tiết |
|--------|---------------------|
| **`app/api`** | FastAPI route definitions, router registration. Handlers phải thin. |
| **`app/config`** | Environment variables, service URLs, model names, database/Qdrant config. |
| **`app/core`** | Exceptions, dependency injection, security helpers, logging, constants. |
| **`app/databases`** | PostgreSQL engine/session, SQLAlchemy models, repositories, migrations. |
| **`app/embedding`** | BGE-M3 model loading, text embedding, batch embedding, normalization. |
| **`app/ingestion`** | Upload → `ocr-pvl` → Markdown normalization → metadata validation → LangChain chunking → embedding → Qdrant indexing. |
| **`app/llm`** | LLM client (OpenAI/Anthropic/local), prompt templates, grounded answer generation. |
| **`app/retrieval`** | Metadata filters, dense retrieval (Qdrant), sparse retrieval (PostgreSQL FTS), hybrid fusion (RRF), reranking, parent context expansion. |
| **`app/schemas`** | Pydantic schemas cho requests/responses. |
| **`app/vectorstore`** | Qdrant client, collection setup, upsert/search/deactivate. |
| **`app/main.py`** | FastAPI application initialization, router registration. |

### Feature-to-Folder Mapping

Khi implement feature, chọn folder đúng:

| Feature / Task | Primary Folder(s) |
|----------------|-------------------|
| Auth endpoints | `app/api`, `app/core`, `app/schemas` |
| Department/document type APIs | `app/api`, `app/databases`, `app/schemas` |
| Document/version/asset CRUD | `app/api`, `app/databases`, `app/schemas` |
| Ingestion job creation/status | `app/api`, `app/ingestion`, `app/databases`, `app/schemas` |
| OCR text extraction | `app/ingestion` (gọi `ocr-pvl`) |
| Metadata validation | `app/ingestion`, `app/databases` |
| Chunk preview/persist | `app/ingestion`, `app/databases` (dùng LangChain chunking) |
| Embedding | `app/embedding` (BGE-M3) |
| Qdrant upsert/search/deactivate | `app/vectorstore` |
| Dense retrieval | `app/retrieval`, `app/vectorstore` |
| Sparse retrieval | `app/retrieval`, `app/databases` (PostgreSQL FTS) |
| Hybrid fusion | `app/retrieval` |
| Reranking | `app/retrieval` |
| Context expansion | `app/retrieval`, `app/databases` |
| LLM answer generation | `app/llm`, `app/retrieval` |
| `/rag/answer` endpoint | `app/api`, `app/retrieval`, `app/llm`, `app/schemas` |

### Quy Tắc Implementation

❌ **Không được tạo các folder duplicate:**
- `app/db`, `app/database`
- `app/embeddings`
- `app/vector_index`
- `app/rag_service`
- `app/modules`
- `app/services`

✅ **Luôn dùng folder structure hiện tại** trừ khi project owner yêu cầu refactor.

---

## Data Flow

### Student Query Flow

```text
1. Student types question → Flutter UI
2. Flutter calls POST /rag/answer → Backend API
3. Backend validates request → app/api/rag.py
4. Query normalization → app/retrieval/service.py (LangChain)
5. Metadata filter construction → app/retrieval/filters.py
   - Filter: review_status=approved, validity_status=valid, rag_status=published, confidentiality=public
   - Filter: effective_date <= today, expiry_date IS NULL OR >= today
6. Dense retrieval (Qdrant vector search) → app/vectorstore/qdrant_client.py
7. Sparse retrieval (PostgreSQL FTS) → app/databases/repositories.py
8. Hybrid fusion (RRF) → app/retrieval/fusion.py
9. Parent context expansion → app/retrieval/context.py
10. Prompt construction → app/llm/prompts.py
11. LLM call → app/llm/client.py
12. Citation validation → app/llm/citation_validator.py
13. Response formatting → app/schemas/rag.py
14. Return answer + citations + assets → Flutter UI
15. Flutter displays answer + citation drawer
```

**Sơ đồ chi tiết:** 📊 [diagrams/mermaid/sequence_chat_flow.mmd](../../diagrams/mermaid/sequence_chat_flow.mmd)

### Admin Ingestion Flow

```text
1. Admin uploads file → Flutter Admin UI
2. Flutter calls POST /ingestion/jobs → Backend API
3. Backend creates ingestion_job → app/databases/models.py
4. Job current_stage: uploaded → app/ingestion/job_runner.py
5. OCR processing → app/ingestion/ocr_pvl.py (gọi ocr-pvl)
   - PaddleOCR: layout detection
   - VietOCR: Vietnamese OCR
   - LlamaParse: table-heavy pages
6. Markdown output → processing/01_OCR_Output/
7. Job current_stage: ocr_done → PostgreSQL
8. Human review Markdown → Obsidian/text editor
9. Approved Markdown → 01_Dataset/ (với YAML metadata)
10. Metadata validation → app/ingestion/metadata_validator.py
11. LangChain chunking (parent-child) → app/ingestion/langchain_chunker.py
12. Chunks persist → PostgreSQL document_chunks
13. BGE-M3 embedding (batch) → app/embedding/bge_m3.py
14. Qdrant upsert vectors → app/vectorstore/qdrant_client.py
15. Job status: indexed → PostgreSQL
16. Document rag_status: published → searchable
```

**Sơ đồ chi tiết:** 📊 [diagrams/mermaid/sequence_ingestion_flow.mmd](../../diagrams/mermaid/sequence_ingestion_flow.mmd)

### Citation Tracing Flow

```text
1. LLM answer references chunks → chunk_ids
2. Backend queries document_chunks → parent document info
3. Backend extracts page markers from chunk text → page numbers
4. Backend returns citations with:
   - Document title, version
   - Page number(s)
   - Chunk text snippet
   - Document source URL/path
5. Flutter displays citation drawer:
   - "Nguồn: [Quy chế đào tạo 2024] - Trang 12"
   - Snippet preview
   - Link to full document
```

---

## Deployment View

### Development Environment (Docker Compose)

```yaml
services:
  postgres:
    image: postgres:17
    ports:
      - "${POSTGRES_PORT}:5432"
    volumes:
      - ./db/postgres:/var/lib/postgresql/data
      - ./database/postgres/init:/docker-entrypoint-initdb.d:ro
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: ${TZ:-Asia/Ho_Chi_Minh}

  qdrant:
    image: qdrant/qdrant:v1.18.2
    ports:
      - "${QDRANT_HTTP_PORT}:6333"
      - "${QDRANT_GRPC_PORT}:6334"
    volumes:
      - ./db/qdrant:/qdrant/storage
      - ./db/qdrant_snapshots:/qdrant/snapshots

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - qdrant
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      QDRANT_HOST: qdrant
      QDRANT_HTTP_PORT: ${QDRANT_HTTP_PORT}
      QDRANT_GRPC_PORT: ${QDRANT_GRPC_PORT}
      EMBEDDING_MODEL: BAAI/bge-m3
      LLM_PROVIDER: openai  # hoặc anthropic
      LLM_API_KEY: ${LLM_API_KEY}

  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      - backend
    environment:
      API_BASE_URL: http://backend:8000
```

**Env vars:** Xem `.env.example` để biết tất cả biến bắt buộc (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `QDRANT_HTTP_PORT`, `QDRANT_GRPC_PORT`, v.v.).  
**Chạy:** `docker compose up -d`

**Chạy:** `docker-compose up -d`

### Production Deployment (Future)

- Backend: Deploy lên cloud (AWS ECS, Google Cloud Run, hoặc VPS)
- PostgreSQL: Managed service (AWS RDS, Google Cloud SQL)
- Qdrant: Docker hoặc Qdrant Cloud
- Storage: MinIO hoặc S3-compatible
- Frontend: Flutter web build deploy lên CDN (Cloudflare, Netlify)

---

## Logging và Error Handling

### Logging Strategy

**Log Levels:**
- `DEBUG`: Chi tiết query, embedding vectors, chunk counts
- `INFO`: API requests, current_stage changes, ingestion milestones
- `WARNING`: Validation errors, missing metadata, slow queries
- `ERROR`: OCR failures, LLM errors, database connection errors
- `CRITICAL`: Service crashes, data corruption

**Log Format:**
```json
{
  "timestamp": "2026-06-10T11:45:00Z",
  "level": "INFO",
  "service": "backend-api",
  "module": "app.retrieval.service",
  "message": "Dense retrieval returned 12 chunks",
  "metadata": {
    "query": "thủ tục xin học bổng",
    "user_id": "student_123",
    "duration_ms": 45
  }
}
```

**Log Storage:**
- Development: `backend/logs/` (local files)
- Production: Centralized logging (CloudWatch, Datadog, hoặc ELK stack)

### Error Handling

**Exception Hierarchy:**
```python
# app/core/exceptions.py
class CTUServiceException(Exception):
    """Base exception"""

class DocumentNotFoundException(CTUServiceException):
    """Document not found"""

class MetadataValidationException(CTUServiceException):
    """Invalid metadata"""

class OCRFailedException(CTUServiceException):
    """OCR processing failed"""

class RetrievalException(CTUServiceException):
    """Retrieval failed"""

class LLMException(CTUServiceException):
    """LLM call failed"""
```

**API Error Responses:**
```json
{
  "error": {
    "code": "METADATA_VALIDATION_ERROR",
    "message": "Required field 'effective_date' is missing",
    "details": {
      "field": "effective_date",
      "document_id": "doc_123"
    }
  }
}
```

### Retry Strategy

- OCR failures: Retry 2 lần với exponential backoff
- LLM calls: Retry 3 lần với fallback prompt
- Qdrant indexing: Retry 2 lần, log error nếu fail
- PostgreSQL connection: Retry với backoff, circuit breaker

---

## Security Considerations

- **Authentication:** JWT tokens (Bearer)
- **Authorization:** RBAC (student, admin, reviewer roles)
- **HTTPS:** Required cho production
- **SQL Injection:** Dùng SQLAlchemy ORM (parameterized queries)
- **XSS:** Flutter auto-escapes, backend validates input
- **Secrets Management:** Environment variables, không commit trong code
- **Rate Limiting:** Future (implement khi có abuse)

---

## Performance Guidelines

### Target Latency (MVP)
- `/rag/answer`: < 3 seconds (p95)
- Dense retrieval: < 100ms
- Sparse retrieval: < 50ms
- LLM call: < 2 seconds
- Embedding single query: < 50ms

### Optimization (Post-MVP)
- HNSW index tuning (Qdrant)
- PostgreSQL query optimization (indexes, query plans)
- Caching frequent queries (Redis)
- Batch embedding for ingestion
- Async processing với Celery

---

## References

- **Architecture Overview:** `.docs/ARCHITECTURE.md`
- **Backend Structure:** `.docs/BACKEND_STRUCTURE.md`
- **Database Schema:** `05_DATABASE_SPEC.md`, `.docs/DATABASE_SCHEMA.md`
- **RAG Pipeline:** `07_RAG_SPEC.md`, `.docs/RAG_RETRIEVAL.md`
- **Ingestion Pipeline:** `08_OCR_INGESTION_SPEC.md`, `.docs/INGESTION_PIPELINE.md`
- **Diagrams:** `../../diagrams/mermaid/`

---

**Next:** [04. Đặc Tả Module →](04_MODULE_SPEC.md)
_[Mô tả: Answer → Retrieved chunks → Source documents → Page/section]_

---

## Deployment View

### Docker Compose Architecture (MVP)
_[Mô tả: Services: backend, frontend, postgres, qdrant, nginx]_

### Network Topology
_[Mô tả: Container communication, ports, volumes]_

### Configuration Management
_[Mô tả: .env files, secrets management]_

---

## Logging Strategy

### Log Levels
_[DEBUG, INFO, WARNING, ERROR]_

### Structured Logging Format
_[JSON format với trace_id]_

### Log Aggregation
_[File-based cho MVP, future: ELK stack]_

---

## Error Handling Strategy

### Error Categories
_[Validation errors, retrieval errors, LLM errors, infrastructure errors]_

### Error Response Format
_[Structured JSON response]_

### Retry Logic
_[Transient failures: Qdrant connection, LLM API]_

---

## Mermaid Diagrams Reference

- **System Context:** [diagrams/mermaid/system_context.mmd](../../diagrams/mermaid/system_context.mmd)
- **System Container:** [diagrams/mermaid/system_container.mmd](../../diagrams/mermaid/system_container.mmd)

---

**Status:** Skeleton — Cần điền nội dung chi tiết  
**Priority:** P0 (Critical for MVP)
