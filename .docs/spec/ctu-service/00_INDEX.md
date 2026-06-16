# CTU Student Service — Đặc Tả Dự Án

## Mục đích

Thư mục này chứa đặc tả kỹ thuật đầy đủ cho dự án **CTU Student Service**, một hệ thống RAG (Retrieval-Augmented Generation) hỗ trợ sinh viên tra cứu và hoàn thành các thủ tục hành chính tại Trường Đại học Cần Thơ.

Đặc tả này là **nguồn chân lý duy nhất** (single source of truth) cho:
- Kiro, Codex, Claude khi viết code
- Lập trình viên hiểu kiến trúc hệ thống
- Thành viên mới onboarding vào dự án
- Ghi nhận các quyết định kiến trúc quan trọng
- Lập kế hoạch triển khai

**Quy tắc quan trọng:** Mọi thay đổi source code chỉ được thực hiện **sau khi đọc đặc tả liên quan**.

---

## 📚 Danh Mục Đặc Tả

### 01. Tổng Quan Dự Án
📄 **[01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md)**
- Tên dự án và bối cảnh vấn đề
- Mục tiêu và phạm vi hệ thống
- Người dùng mục tiêu
- Công nghệ chính
- Tổng quan kiến trúc cấp cao

### 02. Yêu Cầu Hệ Thống
📄 **[02_REQUIREMENTS.md](02_REQUIREMENTS.md)**
- Yêu cầu chức năng (functional requirements)
- Yêu cầu phi chức năng (non-functional requirements)
- Yêu cầu chatbot sinh viên
- Yêu cầu admin và quản lý tài liệu
- Yêu cầu OCR và ingestion
- Yêu cầu RAG và citation
- Tiêu chí chấp nhận (acceptance criteria)

### 03. Kiến Trúc Hệ Thống
📄 **[03_SYSTEM_ARCHITECTURE.md](03_SYSTEM_ARCHITECTURE.md)**
- Kiến trúc tổng thể
- Trách nhiệm từng layer
- Data flow và deployment view
- Chiến lược logging và error handling
- Liên kết với sơ đồ Mermaid

### 04. Đặc Tả Module
📄 **[04_MODULE_SPEC.md](04_MODULE_SPEC.md)**
- Flutter frontend app
- Backend API (FastAPI)
- Auth/RBAC
- Admin document management
- OCR ingestion service
- Chunking và embedding service
- Qdrant indexing service
- Retrieval và reranking service
- LLM answer generation
- Citation service

### 05. Đặc Tả Database
📄 **[05_DATABASE_SPEC.md](05_DATABASE_SPEC.md)**
- Các bảng chính và mối quan hệ
- Schema chi tiết
- Chiến lược metadata và versioning
- Các trường status quan trọng
- Quy tắc document governance
- Liên kết với ERD Mermaid

### 06. Đặc Tả API
📄 **[06_API_SPEC.md](06_API_SPEC.md)**
- Auth APIs
- User/chat APIs
- Admin document APIs
- OCR/ingestion APIs
- Metadata validation APIs
- Search/retrieval APIs
- Health check APIs

### 07. Đặc Tả RAG Pipeline
📄 **[07_RAG_SPEC.md](07_RAG_SPEC.md)**
- Knowledge base lifecycle
- Markdown document format và YAML metadata
- Chunking strategy (LangChain parent-child)
- Embedding strategy (BAAI/bge-m3)
- Qdrant collection và indexing
- Dense và hybrid retrieval
- Reranking và parent context expansion
- Prompt construction
- Citation generation
- Evaluation strategy

### 08. Đặc Tả OCR và Ingestion
📄 **[08_OCR_INGESTION_SPEC.md](08_OCR_INGESTION_SPEC.md)**
- OCR pipeline overview (ocr-pvl)
- PaddleOCR, VietOCR, LlamaParse usage
- Markdown normalization
- Page marker preservation
- YAML metadata frontmatter
- Human review workflow
- Ingestion status lifecycle
- Error handling và retry

### 09. Đặc Tả Frontend (Flutter)
📄 **[09_FRONTEND_SPEC.md](09_FRONTEND_SPEC.md)**
- Flutter app scope
- Student screens (chat, citations, procedures)
- Admin screens (document management, review, indexing)
- UX consistency rules
- State management strategy
- API integration

### 10. Bảo Mật và Document Governance
📄 **[10_SECURITY_AND_GOVERNANCE.md](10_SECURITY_AND_GOVERNANCE.md)**
- Authentication và authorization
- RBAC cho admin và student
- Document governance rules
- Version và validity management
- Review và publish workflow
- Audit logging
- Production safety rules

### 11. Kế Hoạch Triển Khai
📄 **[11_IMPLEMENTATION_PLAN.md](11_IMPLEMENTATION_PLAN.md)**
- Phân chia phases từ 2026-06-08 đến 2026-06-19
- Vertical slice đầu tiên
- Thứ tự triển khai backend/frontend
- Testing và evaluation milestones
- Done criteria cho từng phase

### 12. Câu Hỏi Chưa Giải Quyết
📄 **[12_OPEN_QUESTIONS.md](12_OPEN_QUESTIONS.md)**
- Các quyết định chưa rõ ràng
- LLM provider cuối cùng
- Embedding model alternatives
- Reranker model selection
- Deployment target details
- Storage path conventions

---

## 📊 Danh Mục Sơ Đồ (Diagrams)

### Mermaid Diagrams (Technical, Maintainable)
📁 **[../../diagrams/mermaid/](../../diagrams/mermaid/)**

| Sơ đồ | Mô tả |
|-------|-------|
| `system_context.mmd` | C4 Level 1: System context view |
| `system_container.mmd` | C4 Level 2: Container và components |
| `rag_pipeline.mmd` | RAG query flow từ user question → answer |
| `ingestion_pipeline.mmd` | Document ingestion từ upload → indexed |
| `erd.mmd` | Entity-relationship diagram (database) |
| `sequence_chat_flow.mmd` | Sequence: Student question → answer với citations |
| `sequence_ingestion_flow.mmd` | Sequence: Admin upload → validated → indexed |

### Excalidraw Diagrams (Presentation, Polished)
📁 **[../../diagrams/excalidraw/](../../diagrams/excalidraw/)**

Thư mục này chứa các file `.excalidraw` nguồn để tạo sơ đồ presentation chất lượng cao.  
Xem [README](../../diagrams/excalidraw/README.md) để biết cách sử dụng.

---

## 📖 Thứ Tự Đọc Đề Xuất

### Cho Developer Mới
1. **01_PROJECT_OVERVIEW.md** — Hiểu tổng quan dự án
2. **03_SYSTEM_ARCHITECTURE.md** — Hiểu kiến trúc tổng thể
3. **05_DATABASE_SPEC.md** — Hiểu data model
4. **07_RAG_SPEC.md** — Hiểu RAG pipeline core
5. **11_IMPLEMENTATION_PLAN.md** — Biết thứ tự làm việc

### Cho Backend Developer
1. **03_SYSTEM_ARCHITECTURE.md** — Hiểu folder structure
2. **04_MODULE_SPEC.md** — Hiểu module responsibilities
3. **05_DATABASE_SPEC.md** — Hiểu database schema
4. **06_API_SPEC.md** — Hiểu API contracts
5. **07_RAG_SPEC.md** — Triển khai RAG logic
6. **08_OCR_INGESTION_SPEC.md** — Triển khai ingestion

### Cho Frontend Developer (Flutter)
1. **03_SYSTEM_ARCHITECTURE.md** — Hiểu tổng thể
2. **06_API_SPEC.md** — Hiểu APIs cần gọi
3. **09_FRONTEND_SPEC.md** — Triển khai screens
4. **07_RAG_SPEC.md** — Hiểu RAG response format

### Cho RAG/ML Engineer
1. **07_RAG_SPEC.md** — Hiểu RAG pipeline
2. **08_OCR_INGESTION_SPEC.md** — Hiểu OCR và chunking
3. **05_DATABASE_SPEC.md** — Hiểu metadata structure
4. **04_MODULE_SPEC.md** — Hiểu embedding/vectorstore modules

### Cho DevOps/Architect
1. **03_SYSTEM_ARCHITECTURE.md** — Hiểu deployment view
2. **10_SECURITY_AND_GOVERNANCE.md** — Hiểu security requirements
3. **11_IMPLEMENTATION_PLAN.md** — Hiểu milestones
4. **12_OPEN_QUESTIONS.md** — Biết những gì cần quyết định

---

## 🔄 Quy Trình Cập Nhật Đặc Tả

### Khi Nào Cần Cập Nhật
- Thay đổi quyết định kiến trúc quan trọng
- Thêm bảng database mới
- Thay đổi API contract
- Thêm module hoặc service mới
- Thay đổi RAG pipeline logic
- Phát hiện conflict giữa spec và code

### Cách Cập Nhật
1. **Đọc spec hiện tại trước** khi thay đổi
2. **Cập nhật file spec liên quan**
3. **Cập nhật sơ đồ Mermaid nếu cần**
4. **Ghi lại lý do thay đổi** trong commit message
5. **Thông báo team** nếu thay đổi ảnh hưởng nhiều modules

### Version Control
- Mỗi thay đổi quan trọng tạo entry trong `.docs/CHANGELOG_YYYY-MM-DD.md`
- Commit spec changes riêng với code changes
- Tag các milestone spec quan trọng

---

## 🚨 Nguyên Tắc Quan Trọng

### ❌ KHÔNG BAO GIỜ
- Thay đổi source code mà không đọc spec trước
- Tạo module/folder mới mà không cập nhật spec
- Hard-code business logic mà nên ở database
- Bỏ qua citation requirements
- Deploy code mà chưa match với spec

### ✅ LUÔN LUÔN
- Đọc spec liên quan trước khi code
- Cập nhật spec khi kiến trúc thay đổi
- Validate metadata theo spec rules
- Apply production RAG filters đầy đủ
- Include citations trong student-facing answers
- Test với real Vietnamese documents

---

## 📞 Liên Hệ và Hỗ Trợ

- **Spec issues**: Tạo GitHub issue với tag `spec`
- **Architecture questions**: Hỏi trong architecture channel
- **Spec conflicts**: Báo ngay cho team lead

---

**Phiên bản:** 1.0  
**Ngày tạo:** 2026-06-10  
**Cập nhật cuối:** 2026-06-10  
**Trạng thái:** Draft — Đang hoàn thiện spec đầy đủ
