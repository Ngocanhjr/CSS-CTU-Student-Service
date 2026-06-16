# 01. Tổng Quan Dự Án

## Tên Dự Án

**CTU Student Service** — Hệ thống chatbot RAG hỗ trợ thủ tục hành chính sinh viên

---

## Bối Cảnh Vấn Đề

### Vấn Đề Hiện Tại

Thông tin về thủ tục hành chính sinh viên tại Trường Đại học Cần Thơ (CTU) hiện đang:

- **Phân tán** trên nhiều nguồn: PDF quy định, văn bản thủ tục, biểu mẫu Word/PDF, thông báo trên website, trang phòng ban
- **Khó tìm kiếm**: Sinh viên phải tìm qua nhiều trang web, nhiều file PDF dài
- **Thiếu ngữ cảnh**: Quy định chung không chỉ rõ điều kiện áp dụng cho từng đối tượng sinh viên
- **Dễ lỗi thời**: Thông tin trên các kênh không đồng bộ, sinh viên có thể nhận thông tin cũ
- **Thiếu guidance**: Sinh viên không biết cần chuẩn bị gì, nộp ở đâu, mất bao lâu

### Giải Pháp Hiện Tại Không Đủ

- **Tìm kiếm từ khóa thuần túy (keyword search)**: Bỏ sót các kết quả tương đồng về ngữ nghĩa
- **Chatbot LLM thuần (generic chatbot)**: Dễ hallucination, không có nguồn trích dẫn, trả lời sai thông tin quan trọng như deadline, học phí, biểu mẫu
- **FAQ tĩnh**: Không cover được tất cả các trường hợp, không cá nhân hóa theo đối tượng sinh viên

### Tại Sao RAG?

**RAG (Retrieval-Augmented Generation)** kết hợp:
1. **Retrieval**: Tìm kiếm semantic chính xác qua vector search
2. **Grounding**: LLM chỉ trả lời dựa trên tài liệu được retrieve
3. **Citation**: Mỗi câu trả lời kèm nguồn trích dẫn rõ ràng

→ Giảm hallucination, tăng độ tin cậy, dễ verify, dễ update knowledge base

---

## Mục Tiêu Dự Án

### Mục Tiêu Chính

Xây dựng **hệ thống RAG procedural** giúp sinh viên:
1. **Tra cứu nhanh** thông tin thủ tục hành chính bằng ngôn ngữ tự nhiên (tiếng Việt)
2. **Nhận câu trả lời có trích dẫn** từ tài liệu chính thống của CTU
3. **Hiểu rõ điều kiện áp dụng** cho từng đối tượng sinh viên
4. **Biết checklist cụ thể**: hồ sơ cần chuẩn bị, nơi nộp, thời gian xử lý, biểu mẫu liên quan
5. **Truy cập biểu mẫu và tài liệu liên quan** trực tiếp từ câu trả lời

### Mục Tiêu Phụ

- Admin có thể **quản lý knowledge base**: upload tài liệu, validate metadata, review OCR output, approve trước khi publish
- Hệ thống **tự động version documents**, đánh dấu tài liệu expired/replaced
- Hệ thống **track document lineage**, giữ lại tài liệu cũ khi vẫn cần reference
- Hệ thống **log và trace** để debug/evaluate RAG quality

---

## Người Dùng Mục Tiêu

### 1. Sinh Viên CTU (Primary User)

**Use cases:**
- "Em muốn xin cấp bảng điểm thì cần chuẩn bị gì?"
- "Thủ tục bảo lưu kết quả học tập có deadline không?"
- "Em có thể xin chuyển ngành nếu đang nợ môn không?"
- "Làm thẻ sinh viên mất bao lâu và làm ở đâu?"
- "Biểu mẫu xin nghỉ học tạm thời nộp cho ai?"

**Cần:**
- Câu trả lời nhanh, chính xác, có trích dẫn
- Hiển thị rõ điều kiện áp dụng cho em
- Link tải biểu mẫu và tài liệu liên quan
- Dễ sử dụng trên mobile

### 2. Admin/Quản Lý Tài Liệu (Secondary User)

**Use cases:**
- Upload tài liệu mới (PDF/Word/scanned image)
- Review và sửa OCR output
- Validate metadata (loại tài liệu, phòng ban, đối tượng áp dụng, ngày hiệu lực)
- Approve document trước khi publish vào RAG
- Quản lý version: đánh dấu tài liệu cũ expired/replaced
- Theo dõi ingestion job progress
- Reindex khi cần

**Cần:**
- Giao diện admin rõ ràng
- Workflow validation và approval
- Tracking ingestion progress
- Error handling và retry

### 3. Nhà Phát Triển/Đánh Giá (Tertiary User)

**Use cases:**
- Monitor RAG quality
- Debug retrieval issues
- Evaluate với golden questions
- Tune retrieval/reranking parameters
- Trace từ answer → retrieved chunks → source documents

**Cần:**
- Logging chi tiết
- Debug/trace endpoints
- Evaluation metrics
- Retrieval quality dashboard

---

## Phạm Vi Hệ Thống

### In Scope (Phase 1 MVP — 2026-06-08 to 2026-06-19)

✅ **Core RAG Pipeline:**
- OCR tài liệu (ocr-pvl: PaddleOCR + VietOCR + LlamaParse)
- Markdown normalization với page markers
- Metadata validation
- LangChain heading-aware parent-child chunking
- BGE-M3 embedding (1024-dim)
- Qdrant indexing (cosine distance)
- Dense + hybrid retrieval (Qdrant + PostgreSQL FTS)
- Reranking và parent context expansion
- LLM answer generation với citations

✅ **Admin Workflow:**
- Upload tài liệu
- Review OCR output
- Validate metadata
- Approve/reject documents
- Publish vào RAG

✅ **Student Interface (Flutter):**
- Chat screen với query input
- Answer display với citations
- Citation drawer (xem source chi tiết)
- Related forms/assets

✅ **Database:**
- PostgreSQL: metadata, versions, chunks, assets, jobs
- Qdrant: vector search

✅ **Vertical Slice:**
- 3–5 documents end-to-end từ OCR → RAG answer

### Out of Scope (Phase 1)

❌ **Chưa làm ở MVP:**
- Procedure graph/flowchart generation
- Eligibility auto-checking (yêu cầu business logic phức tạp)
- Multi-turn conversational memory
- Personalized checklist dựa trên student profile
- Full RBAC với nhiều roles
- Mobile app deployment (chỉ local dev)
- Production deployment (cloud, scaling, HA)
- HNSW tuning (để phase sau khi có data đủ lớn)
- Advanced reranker (cross-encoder, LLM-based reranker)
- LLM fine-tuning
- A/B testing framework

### Future Enhancements (Phase 2+)

🔮 **Có thể mở rộng sau:**
- Voice input (speech-to-text)
- Multi-language support (English)
- Procedure graph visualization
- Automated eligibility checker
- Student profile integration
- Notification khi có tài liệu mới
- Feedback loop và reinforcement learning
- Integration với CTU portal
- Mobile app published trên store

---

## Công Nghệ Chính

### Stack Overview

| Layer | Technology |
|-------|------------|
| **Frontend** | Flutter (mobile + web) |
| **Backend API** | FastAPI (Python) |
| **RAG Service** | FastAPI (Python) với LangChain |
| **OCR** | ocr-pvl (PaddleOCR + VietOCR + LlamaParse) |
| **Chunking** | LangChain heading-aware parent-child |
| **Embedding** | BAAI/bge-m3 (1024-dim, cosine) |
| **Vector DB** | Qdrant |
| **Metadata DB** | PostgreSQL |
| **Storage** | Local filesystem (future: MinIO/S3) |
| **Deployment** | Docker Compose (local MVP) |

### Tech Decisions (Fixed for MVP)

**Đã quyết định từ 2026-06-08:**
- ✅ OCR tool: `ocr-pvl` (không dùng Tesseract hay Textract riêng lẻ)
- ✅ RAG framework: LangChain (orchestration, retrieval composition)
- ✅ Embedding model: BAAI/bge-m3
- ✅ Vector DB: Qdrant với cosine distance
- ✅ Chunking: LangChain với parent-child strategy
- ✅ HNSW: **KHÔNG** tune trong MVP (future optimization only)

---

## Tổng Quan Kiến Trúc Cấp Cao

```
┌─────────────────────────────────────────────────────────────────┐
│                         Người Dùng                               │
│                   (Sinh viên + Admin)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Flutter Frontend App                            │
│            (Mobile/Web — Chat UI + Admin UI)                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                         │
│   ┌────────────┬────────────┬──────────────┬──────────────┐    │
│   │ Auth/RBAC  │  Document  │  Ingestion   │  RAG/Answer  │    │
│   │  Service   │  Management│   Service    │    Service   │    │
│   └────────────┴────────────┴──────────────┴──────────────┘    │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PostgreSQL  │  │    Qdrant    │  │    Storage   │
│   (Metadata) │  │  (Vectors)   │  │   (Files)    │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Data Flow Chính

**Student Query Flow:**
```
Sinh viên nhập câu hỏi
→ Frontend gửi đến Backend /rag/answer
→ Backend normalize query
→ Retrieval service: metadata filter + Qdrant vector search + PostgreSQL FTS
→ RRF fusion + reranking
→ Parent context expansion
→ LLM prompt construction
→ LLM answer generation
→ Citation validation
→ Response: answer + citations + related assets
→ Frontend hiển thị answer + citation drawer
```

**Admin Ingestion Flow:**
```
Admin upload tài liệu
→ Backend tạo ingestion job
→ OCR service (ocr-pvl) → Markdown output
→ Admin review và validate metadata
→ Admin approve
→ Chunking service (LangChain) → parent/child chunks
→ Embedding service (BGE-M3) → vectors
→ Qdrant indexing → upsert points
→ PostgreSQL update: rag_status = "published"
→ Document active trong RAG
```

---

## Đầu Ra Kỳ Vọng Của Hệ Thống

### Student-Facing Output

**Ví dụ câu hỏi:**
> "Em muốn xin cấp bảng điểm thì cần chuẩn bị gì?"

**Response mong đợi:**
```json
{
  "answer": "Để xin cấp bảng điểm, bạn cần chuẩn bị:\n\n1. Đơn xin cấp bảng điểm (theo mẫu)\n2. Bản sao chứng minh nhân dân hoặc căn cước công dân\n3. Học phí đã được thanh toán đầy đủ\n4. Lệ phí cấp bảng điểm: 50,000 VNĐ/bản\n\nNộp hồ sơ tại Phòng Đào tạo, tầng 2, nhà A. Thời gian xử lý: 5-7 ngày làm việc.",
  "citations": [
    {
      "document_id": "qd-bang-diem-2024",
      "version_id": "v1.0",
      "title": "Quy định cấp bảng điểm sinh viên",
      "page_start": 3,
      "page_end": 3,
      "section_title": "Hồ sơ yêu cầu",
      "source_file": "QD_CapBangDiem_2024.pdf"
    }
  ],
  "related_assets": [
    {
      "asset_id": "form-bang-diem",
      "title": "Mẫu đơn xin cấp bảng điểm",
      "file_path": "/assets/forms/don_xin_cap_bang_diem.docx",
      "download_url": "/api/assets/form-bang-diem/download"
    }
  ],
  "confidence": "high",
  "retrieval_count": 3
}
```

**Đặc điểm:**
- ✅ Câu trả lời cụ thể, có cấu trúc
- ✅ Có citations với page, section, source file
- ✅ Có related assets (biểu mẫu)
- ✅ Không hallucinate (không bịa deadline, học phí, yêu cầu không có trong nguồn)

### Admin-Facing Output

**Ingestion job progress:**
```json
{
  "job_id": "job-12345",
  "document_version_id": "doc-v-001",
  "current_stage": "indexed",
  "stages": [
    {"stage": "uploaded", "timestamp": "2026-06-10T08:00:00Z"},
    {"stage": "ocr_running", "timestamp": "2026-06-10T08:05:00Z"},
    {"stage": "ocr_done", "timestamp": "2026-06-10T08:10:00Z"},
    {"stage": "metadata_validated", "timestamp": "2026-06-10T09:00:00Z"},
    {"stage": "approved", "timestamp": "2026-06-10T09:30:00Z"},
    {"stage": "chunked", "timestamp": "2026-06-10T09:35:00Z"},
    {"stage": "embedded", "timestamp": "2026-06-10T09:40:00Z"},
    {"stage": "indexed", "timestamp": "2026-06-10T09:42:00Z"}
  ],
  "total_chunks": 45,
  "indexed_chunks": 45,
  "errors": []
}
```

---

## Tổng Quan Cấu Trúc Thư Mục Dự Án

```
CTU-SERVICE/
└── chatbot/                    # Main project folder
    ├── backend/                # FastAPI backend
    │   └── app/
    │       ├── api/            # API routes
    │       ├── config/         # Settings
    │       ├── core/           # Shared utilities
    │       ├── databases/      # PostgreSQL models
    │       ├── embedding/      # BGE-M3 embedding
    │       ├── ingestion/      # OCR + chunking
    │       ├── llm/            # LLM answer generation
    │       ├── retrieval/      # RAG retrieval
    │       ├── schemas/        # Pydantic DTOs
    │       ├── vectorstore/    # Qdrant client
    │       └── main.py         # App entrypoint
    │
    ├── frontend/               # Flutter app
    │   └── lib/
    │       ├── features/       # Screens: chat, admin, citations
    │       ├── core/           # Network, routing, theme
    │       └── shared/         # Models, DTOs
    │
    ├── .docs/                  # Documentation
    │   ├── spec/               # Project specifications ← YOU ARE HERE
    │   ├── diagrams/           # Mermaid + Excalidraw
    │   └── *.md                # Existing architecture docs
    │
    ├── db/                     # Database setup (migrations, seeds)
    ├── infrastructure/         # Docker Compose, env templates
    ├── ocr/                    # OCR service (ocr-pvl)
    └── nlcs/                   # Dataset and canonical Markdown
        └── 01_Dataset/         # Reviewed canonical documents
```

---

## Target Milestone: 2026-06-19

**Goal:** Chạy được vertical slice end-to-end với 3–5 documents

**Success criteria:**
1. ✅ OCR 3–5 documents với ocr-pvl → Markdown output
2. ✅ Admin review và approve documents
3. ✅ LangChain chunk documents → parent/child chunks
4. ✅ BGE-M3 embed child chunks → 1024-dim vectors
5. ✅ Qdrant indexing → collection `ctu_chunks_bge_m3`
6. ✅ `/rag/answer` endpoint returns grounded answer với citations
7. ✅ Flutter chat screen hiển thị answer + citations
8. ✅ Test với 10–20 real student questions

**Không yêu cầu:**
- ❌ HNSW tuning (future optimization)
- ❌ Production deployment
- ❌ Full RBAC
- ❌ Advanced reranker
- ❌ Large-scale data (chỉ 3–5 docs)

---

## Liên Kết Tài Liệu Liên Quan

- **Kiến trúc chi tiết:** [03_SYSTEM_ARCHITECTURE.md](03_SYSTEM_ARCHITECTURE.md)
- **Yêu cầu đầy đủ:** [02_REQUIREMENTS.md](02_REQUIREMENTS.md)
- **Database schema:** [05_DATABASE_SPEC.md](05_DATABASE_SPEC.md)
- **RAG pipeline:** [07_RAG_SPEC.md](07_RAG_SPEC.md)
- **Implementation plan:** [11_IMPLEMENTATION_PLAN.md](11_IMPLEMENTATION_PLAN.md)

---

**Phiên bản:** 1.0  
**Ngày tạo:** 2026-06-10  
**Trạng thái:** Draft
