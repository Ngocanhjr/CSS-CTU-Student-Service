# 04. Đặc Tả Module

**Version:** 1.0  
**Last Updated:** 2026-06-10  
**Status:** Final

---

## Mục Lục

1. [Frontend Modules (Flutter)](#frontend-modules-flutter)
2. [Backend API Modules](#backend-api-modules-fastapi)
3. [OCR & Ingestion Modules](#ocr--ingestion-modules)
4. [Embedding & Vector Modules](#embedding--vector-modules)
5. [Retrieval & RAG Modules](#retrieval--rag-modules)
6. [Database Modules](#database-modules)
7. [Module Dependency Graph](#module-dependency-graph)

---

## Frontend Modules (Flutter)

### F1. Student Chat Module

**Location:** `frontend/lib/features/chat/`

**Trách nhiệm:**
- Hiển thị chat interface cho sinh viên
- Input query text với validation
- Gọi Backend `/rag/answer` API
- Display answer với formatted text
- Hiển thị loading states và error messages
- Hiển thị citation drawer khi user click vào citations
- Hiển thị related assets (forms, documents)

**Inputs:**
- User query text (String)
- Session context (optional, future)

**Outputs:**
- Formatted answer text
- Citation list với source links
- Related asset list
- Error message (nếu có)

**Dependencies:**
- Backend API: `POST /rag/answer`
- Citation Display Module
- State management (Riverpod/BLoC)

**UI Components:**
- Chat input field với voice input button (future)
- Message list (user messages + bot responses)
- Loading indicator
- Error banner
- Citation chips/badges trong answer text
- "Show citations" button

**Failure Cases:**
- Network error → Display "Không thể kết nối. Vui lòng thử lại."
- No results → Display "Không tìm thấy thông tin. Vui lòng thử câu hỏi khác."
- Timeout → Display "Request timeout. Vui lòng thử lại."
- Invalid query → Display validation error message

**State:**
```dart
class ChatState {
  List<Message> messages;
  bool isLoading;
  String? errorMessage;
  List<Citation>? currentCitations;
  List<Asset>? currentAssets;
}
```

---

### F2. Admin Document Management Module

**Location:** `frontend/lib/features/admin/document_management/`

**Trách nhiệm:**
- Upload documents (PDF, DOCX, images)
- List documents với filter/search
- View document details và metadata
- Approve/reject documents sau review
- Publish documents để make searchable
- Track ingestion job progress

**Inputs:**
- File upload (File object)
- Document metadata (title, type, department, dates)
- Filters (department, type, status, date range)

**Outputs:**
- Document list với pagination
- Document detail view
- Job status updates
- Success/error notifications

**Dependencies:**
- Backend API: `POST /ingestion/jobs`, `GET /documents`, `PATCH /documents/{id}`
- File picker (Flutter package)
- State management

**UI Screens:**
1. **Document List Screen:**
   - Table view: title, type, department, status, dates
   - Filters: department dropdown, type dropdown, status dropdown
   - Search bar
   - "Upload Document" button

2. **Document Upload Screen:**
   - File picker
   - Metadata form (title, type, department, effective_date, expiry_date, confidentiality)
   - "Upload" button
   - Progress indicator

3. **Document Detail Screen:**
   - Metadata display
   - OCR status, review status, validity status, RAG status
   - Markdown preview (sau OCR)
   - "Approve" / "Reject" buttons (nếu chưa approved)
   - "Publish" button (nếu approved nhưng chưa published)

**Failure Cases:**
- File too large → "File vượt quá 50MB"
- Invalid metadata → Display field-specific errors
- Upload failed → "Upload thất bại. Vui lòng thử lại."
- Permission denied → "Bạn không có quyền thực hiện thao tác này."

---

### F3. Citation Display Module

**Location:** `frontend/lib/features/chat/widgets/citation_drawer.dart`

**Trách nhiệm:**
- Display citation details trong drawer/modal
- Show source document title, version
- Show page number(s)
- Show chunk text snippet
- Provide link to full document

**Inputs:**
- Citation object: `{ document_title, version, page_number, snippet, source_url }`

**Outputs:**
- Citation card với formatted info
- "View full document" link

**UI Design:**
```
┌─────────────────────────────────┐
│ Nguồn trích dẫn                 │
├─────────────────────────────────┤
│ 📄 Quy chế đào tạo 2024         │
│ Phiên bản: 1.0                  │
│ Trang: 12                       │
│                                 │
│ "...sinh viên cần nộp đơn xin   │
│ học bổng trước ngày 30/9..."    │
│                                 │
│ [Xem tài liệu đầy đủ →]         │
└─────────────────────────────────┘
```

---

### F4. State Management

**Strategy:** Riverpod (recommended) hoặc BLoC

**Providers/BLoCs:**
- `chatProvider` — Quản lý chat state
- `documentProvider` — Quản lý document list state
- `authProvider` — Quản lý authentication state
- `uploadProvider` — Quản lý upload progress

**Example (Riverpod):**
```dart
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  return ChatNotifier(ref.read(apiClientProvider));
});
```

---

## Backend API Modules (FastAPI)

### B1. Auth & RBAC Module

**Location:** `app/core/security.py`, `app/api/auth.py`

**Trách nhiệm:**
- User authentication (login, logout)
- JWT token generation và validation
- Role-based access control (student, admin, reviewer)
- Permission checking middleware

**Inputs:**
- Login credentials (username, password)
- JWT token (Bearer header)

**Outputs:**
- Access token (JWT)
- User info với roles
- Permission check result (boolean)

**Dependencies:**
- PostgreSQL (users table, future)
- JWT library (PyJWT)

**Implementation:**
```python
# app/core/security.py
def create_access_token(user_id: str, roles: List[str]) -> str:
    payload = {"sub": user_id, "roles": roles, "exp": ...}
    return jwt.encode(payload, SECRET_KEY)

def verify_token(token: str) -> Dict:
    return jwt.decode(token, SECRET_KEY)

def require_role(required_role: str):
    """Decorator for route permission check"""
```

**Failure Cases:**
- Invalid credentials → 401 Unauthorized
- Expired token → 401 Token Expired
- Insufficient permissions → 403 Forbidden

---

### B2. Document Management Module

**Location:** `app/api/documents.py`, `app/databases/repositories/document_repo.py`

**Trách nhiệm:**
- CRUD operations cho documents, versions, assets
- Filter và search documents
- Update document status fields
- Manage document-asset relationships

**Endpoints:**
- `GET /documents` — List documents với filters
- `GET /documents/{id}` — Get document detail
- `POST /documents` — Create document (metadata only)
- `PATCH /documents/{id}` — Update document metadata/status
- `DELETE /documents/{id}` — Soft delete document
- `GET /documents/{id}/versions` — List versions của document
- `GET /documents/{id}/assets` — List assets của document

**Inputs:**
- Document metadata (title, type, department, dates, status fields)
- Filters (department, type, status, date range)
- Pagination params (page, limit)

**Outputs:**
- Document list với pagination
- Document detail với versions và assets
- Success/error messages

**Dependencies:**
- PostgreSQL (documents, document_versions, assets, document_assets tables)
- Auth module (permission check)

---

### B3. Metadata Validation Module

**Location:** `app/ingestion/metadata_validator.py`

**Trách nhiệm:**
- Validate required YAML frontmatter fields
- Check field formats (dates, enums)
- Apply business rules (effective_date < expiry_date)
- Return validation errors với field-specific messages

**Inputs:**
- Document metadata dict

**Outputs:**
- Validation result (boolean)
- Error list: `[{field: "effective_date", message: "Invalid date format"}]`

**Validation Rules:**
```python
REQUIRED_FIELDS = [
    "title", "document_type", "department", 
    "effective_date", "confidentiality", "version"
]

ENUM_FIELDS = {
    "document_type": ["regulation", "procedure", "form", "faq"],
    "confidentiality": ["public", "internal", "restricted"],
    "review_status": ["pending", "approved", "rejected"],
    "validity_status": ["draft", "valid", "superseded", "archived"],
    "rag_status": ["not_indexed", "indexing", "published", "unpublished"]
}

DATE_FIELDS = ["effective_date", "expiry_date", "issued_date"]
```

**Failure Cases:**
- Missing required field → Return error với field name
- Invalid enum value → Return valid options
- Invalid date format → Suggest correct format (YYYY-MM-DD)
- Business rule violation → Return specific error

---

## OCR & Ingestion Modules

### I1. OCR Service Module

**Location:** `app/ingestion/ocr_pvl.py`

**Trách nhiệm:** Orchestrate ocr-pvl, handle OCR output, update job progress

**Inputs:** File path, Job ID

**Outputs:** Markdown file path, OCR status, Error message

**Tools:** PaddleOCR, VietOCR, LlamaParse (via ocr-pvl)

**Failure Cases:** File not found, OCR crash (retry 2x), Invalid output

---

### I2. Markdown Normalization Module

**Location:** `app/ingestion/markdown_normalizer.py`

**Trách nhiệm:** Clean OCR output, validate page markers, normalize formatting

**Inputs:** Raw OCR Markdown

**Outputs:** Cleaned Markdown, Validation warnings

---

### I3. Chunking Service Module

**Location:** `app/ingestion/langchain_chunker.py`

**Trách nhiệm:** LangChain heading-aware parent-child chunking

**Framework:** LangChain MarkdownHeaderTextSplitter

**Inputs:** Canonical Markdown, Document metadata

**Outputs:** Parent chunks, Child chunks, Chunk count

---

## Embedding & Vector Modules

### E1. Embedding Service Module

**Location:** `app/embedding/bge_m3.py`

**Trách nhiệm:** Load BGE-M3, embed text, normalize vectors, batch processing

**Model:** `BAAI/bge-m3` (1024 dims)

**Inputs:** Text string hoặc list of texts

**Outputs:** Normalized embedding vector(s)

**Dependencies:** sentence-transformers, PyTorch

---

### E2. Qdrant Indexing Module

**Location:** `app/vectorstore/qdrant_client.py`

**Trách nhiệm:** Collection management, upsert vectors, search, deactivate points

**Inputs:** Chunk data (id, vector, metadata)

**Outputs:** Point ID, Search results

**Dependencies:** qdrant-client

---

## Retrieval & RAG Modules

### R1. Dense Retrieval Module

**Location:** `app/retrieval/dense.py`

**Trách nhiệm:** Query embedding, Qdrant vector search, metadata filtering

**Inputs:** Query text, Filters, Top-k

**Outputs:** Ranked chunk IDs với scores

---

### R2. Sparse Retrieval Module

**Location:** `app/retrieval/sparse.py`

**Trách nhiệm:** PostgreSQL FTS/BM25 search

**Inputs:** Query text, Filters, Top-k

**Outputs:** Ranked chunk IDs với scores

---

### R3. Hybrid Fusion Module

**Location:** `app/retrieval/fusion.py`

**Trách nhiệm:** RRF fusion của dense + sparse results

**Inputs:** Dense results, Sparse results

**Outputs:** Fused ranked list

---

### R4. Parent Context Expansion Module

**Location:** `app/retrieval/context.py`

**Trách nhiệm:** Expand child chunks to parent chunks

**Inputs:** Child chunk IDs

**Outputs:** Parent chunk texts

---

### R5. LLM Answer Generator Module

**Location:** `app/llm/answer_generator.py`

**Trách nhiệm:** Build prompt, call LLM, parse response, format answer

**Inputs:** Query, Retrieved context, Citations

**Outputs:** Generated answer với citations

**Dependencies:** OpenAI/Anthropic API, app/llm/prompts.py

---

### R6. Citation Service Module

**Location:** `app/llm/citation_validator.py`

**Trách nhiệm:** Extract citations từ LLM response, validate, format citation objects

**Inputs:** LLM response, Retrieved chunks

**Outputs:** Citation list: `[{document_title, version, page_number, snippet, source_url}]`

---

## Database Modules

### D1. PostgreSQL Persistence Module

**Location:** `app/databases/`

**Trách nhiệm:** SQLAlchemy models, sessions, repositories, migrations

**Files:**
- `session.py` — Database session management
- `models.py` — SQLAlchemy models (departments, documents, chunks, assets, jobs)
- `repositories.py` — Repository pattern cho CRUD operations

---

### D2. Qdrant Vector Storage Module

**Location:** `app/vectorstore/`

**Trách nhiệm:** Qdrant client, collection setup, point management

**Files:**
- `qdrant_client.py` — Qdrant connection
- `collections.py` — Collection creation/management
- `payloads.py` — Payload construction

---

## Module Dependency Graph

```
Flutter Frontend
    ↓
Backend API (app/api)
    ↓
    ├─→ Auth & RBAC (app/core)
    ├─→ Document Management (app/databases)
    ├─→ Ingestion Orchestration (app/ingestion)
    │       ↓
    │       ├─→ OCR Service (ocr-pvl)
    │       ├─→ Markdown Normalizer
    │       ├─→ Metadata Validator
    │       ├─→ Chunking Service (LangChain)
    │       ├─→ Embedding Service (BGE-M3)
    │       └─→ Qdrant Indexing
    │
    └─→ RAG Service (app/retrieval, app/llm)
            ↓
            ├─→ Dense Retrieval (Qdrant)
            ├─→ Sparse Retrieval (PostgreSQL FTS)
            ├─→ Hybrid Fusion (RRF)
            ├─→ Parent Context Expansion
            ├─→ LLM Answer Generator
            └─→ Citation Validator
```

---

## References

- **Architecture:** `03_SYSTEM_ARCHITECTURE.md`
- **Database:** `05_DATABASE_SPEC.md`
- **API:** `06_API_SPEC.md`
- **RAG Pipeline:** `07_RAG_SPEC.md`
- **Ingestion:** `08_OCR_INGESTION_SPEC.md`

---

**Next:** [05. Đặc Tả Database →](05_DATABASE_SPEC.md)

---

## OCR & Ingestion Modules

### I1. OCR Service Module

**Location:** `app/ingestion/ocr_pvl.py`

**Trách nhiệm:**
- Orchestrate ocr-pvl process
- Call ocr-pvl với correct parameters
- Handle OCR output (Markdown file)
- Update ingestion_job current_stage
- Preserve page markers (`<!-- page: N -->`)

**Inputs:**
- Original file path (PDF, DOCX, image)
- Job ID

**Outputs:**
- Markdown file path
- OCR status (success/failed)
- Error message (nếu failed)

**Tools:**
- **PaddleOCR:** Layout detection, text regions (via ocr-pvl)
- **VietOCR:** Vietnamese text recognition (via ocr-pvl)
- **LlamaParse:** Table-heavy pages, complex layouts (via ocr-pvl)

**Implementation:**
```python
def run_ocr_pvl(file_path: str, job_id: str) -> OCRResult:
    """
    Run ocr-pvl and return Markdown output path
    """
    cmd = ["python", "ocr-pvl/main.py", "--input", file_path, "--output", output_dir]
    result = subprocess.run(cmd, capture_output=True)
    
    if result.returncode == 0:
        return OCRResult(success=True, markdown_path=...)
    else:
        return OCRResult(success=False, error=result.stderr)
```

**Failure Cases:**
- File not found → Return error
- OCR process crash → Retry 2 lần, log error
- Invalid output → Flag for manual review

---

### I2. Markdown Normalization Module

**Location:** `app/ingestion/markdown_normalizer.py`

**Trách nhiệm:**
- Clean OCR output (remove extra whitespace, fix formatting)
- Validate page markers exist và correct
- Normalize heading levels
- Preserve table structure
- Add YAML frontmatter template (nếu chưa có)

**Inputs:**
- Raw OCR Markdown file

**Outputs:**
- Cleaned Markdown file
- Validation warnings (missing page markers, malformed tables)

**Normalization Rules:**
- Trim whitespace lines (max 1 blank line)
- Fix heading hierarchy (# → ## → ### no skip)
- Validate page markers: `<!-- page: \d+ -->`
- Normalize list formatting (consistent `-` hoặc `*`)
- Preserve table delimiters (`|`, `-`)

**Example:**
```python
def normalize_markdown(raw_md: str) -> str:
    # Remove extra blank lines
    md = re.sub(r'\n\n\n+', '\n\n', raw_md)
    
    # Validate page markers
    markers = re.findall(r'<!-- page: (\d+) -->', md)
    if not markers:
        logging.warning("No page markers found")
    
    # Add YAML frontmatter template if missing
    if not md.startswith('---'):
        md = YAML_TEMPLATE + '\n\n' + md
    
    return md
```

---

### I3. Chunking Service Module

**Location:** `app/ingestion/langchain_chunker.py`

**Trách nhiệm:**
- Implement LangChain heading-aware parent-child chunking
- Preserve document structure (headings → sections)
- Create parent chunks (sections) và child chunks (paragraphs)
- Persist chunks trong PostgreSQL với parent-child relationships
- Preserve page markers trong chunk text

**Framework:** LangChain

**Inputs:**
- Canonical Markdown file (sau review)
- Document metadata (document_id, version_id)

**Outputs:**
- Parent chunks (PostgreSQL)
- Child chunks (PostgreSQL)
- Chunk count

**Chunking Rules:**
```
Document
  ├─ Parent Chunk 1 (Section: "Điều kiện học bổng")
  │   ├─ Child Chunk 1.1 (Paragraph 1)
  │   ├─ Child Chunk 1.2 (Paragraph 2)
  │   └─ Child Chunk 1.3 (Table)
  ├─ Parent Chunk 2 (Section: "Thủ tục nộp hồ sơ")
  │   ├─ Child Chunk 2.1 (Paragraph 1)
  │   └─ Child Chunk 2.2 (List)
```

**Implementation:**
```python
from langchain.text_splitter import MarkdownHeaderTextSplitter

def chunk_document(markdown_text: str, doc_id: str, version_id: str):
    # LangChain heading-aware splitter
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
        ]
    )
    
    parent_chunks = splitter.split_text(markdown_text)
    
    for parent_chunk in parent_chunks:
        # Create parent in PostgreSQL
        parent_id = create_parent_chunk(parent_chunk, doc_id, version_id)
        
        # Split parent into child chunks (by paragraph)
        child_chunks = split_into_paragraphs(parent_chunk.page_content)
        
        for child_chunk in child_chunks:
            # Create child in PostgreSQL with parent_id
            create_child_chunk(child_chunk, parent_id, doc_id, version_id)
```

**Failure Cases:**
- Malformed Markdown → Log error, skip document
- No headings detected → Treat entire doc as 1 parent
- Child chunk too long (>1000 chars) → Further split

---

## Embedding & Vector Modules

### Embedding Service Module (`app/embedding`)
- **Trách nhiệm:** _[Load BGE-M3, embed chunks, normalize vectors]_
- **Model:** _[BAAI/bge-m3]_

### Qdrant Indexing Module (`app/vectorstore`)
- **Trách nhiệm:** _[Create collections, upsert points, search, deactivate]_

---

## Retrieval & RAG Modules

### Retrieval Service Module (`app/retrieval`)
- **Trách nhiệm:** _[Metadata filter, dense search, sparse search, fusion]_

### Reranking Module (`app/retrieval`)
- **Trách nhiệm:** _[Rerank top-k chunks]_

### Parent Context Expansion Module (`app/retrieval`)
- **Trách nhiệm:** _[Expand child chunks to parent chunks]_

### LLM Prompt Builder Module (`app/llm`)
- **Trách nhiệm:** _[Build grounded prompt from retrieved context]_

### Answer Generator Module (`app/llm`)
- **Trách nhiệm:** _[Call LLM, parse response, format answer]_

### Citation Service Module (`app/llm`)
- **Trách nhiệm:** _[Extract citations, validate citations, format citation objects]_

---

## Database Modules

### PostgreSQL Persistence Module (`app/databases`)
- **Trách nhiệm:** _[SQLAlchemy models, sessions, repositories]_

### Qdrant Vector Storage Module (`app/vectorstore`)
- **Trách nhiệm:** _[Qdrant client, collection management]_

---

## Module Dependency Graph
_[Mô tả dependencies giữa các modules]_

---

**Status:** Skeleton — Cần điền chi tiết inputs/outputs/dependencies  
**Priority:** P1
