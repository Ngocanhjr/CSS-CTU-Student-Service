# 00. API Overview & Conventions

**Last Updated:** 2026-07-13

File này là index cho toàn bộ thư mục `chatbot/.docs/guild_implement/api/`, gồm 20 guide con
(01-20) nối tiếp guide này. Mục tiêu: đưa backend FastAPI từ trạng thái rỗng (`app/main.py`,
`app/api/health.py`, `app/retrieval/retriever.py`, `app/llm/rag_chain.py`, `app/llm/generator.py`
đều 0 dòng) lên đủ endpoint theo `.docs/spec/ctu-service/06_API_SPEC.md`, rồi nối 2 frontend
(Flutter sinh viên, React admin) từ mock sang gọi API thật.

```text
Backend core (bootstrap FastAPI, CORS, dependency)
  -> Backend endpoints (rag/answer, documents, document-versions)
  -> Ingestion endpoints (ingestion/jobs)
  -> Flutter integration (thay mock bằng http client thật)
  -> Admin React integration (thay mockClient/documentsMockApi bằng fetch thật)
  -> E2E smoke (curl toàn bộ endpoint, chạy thật với 2 frontend)
```

Guide này không viết code, chỉ chốt convention và thứ tự làm. Chi tiết code nằm ở từng guide
01-20.

---

## 1. Trạng Thái Hiện Tại (đã xác nhận bằng đọc code, không suy đoán)

```text
app/main.py                     RỖNG - chưa có FastAPI() instance, chưa include router, chưa CORS.
app/api/health.py               RỖNG - chưa có route.
app/api/__init__.py             tồn tại nhưng rỗng.
app/api/routes/                 RỖNG - chưa có file router nào.
app/retrieval/retriever.py      RỖNG - chưa có class Retriever.
app/llm/rag_chain.py            RỖNG - answer_question()/build_context_block() ở guide 18 CHƯA implement.
app/llm/generator.py            RỖNG.
app/llm/prompts.py              ĐÃ CÓ - RAG_ANSWER_PROMPT dùng ChatPromptTemplate.from_template(),
                                 biến {context}/{question} (khác with guide 18 mô tả from_messages;
                                 ưu tiên code thật này).
app/embedding/embedder.py       ĐÃ CÓ - NVIDIAEmbeddings, embed_query(), embed_texts(),
                                 embed_chunks_with_cache().
app/vectorstore/qdrant_client.py ĐÃ CÓ - get_qdrant_client(), đọc QDRANT_URL/QDRANT_API_KEY qua os.getenv().
app/vectorstore/repository.py   ĐÃ CÓ đầy đủ - COLLECTION_NAME, VECTOR_NAME, search_points(),
                                 upsert_chunks(), build_context_filter(), build_payload().
app/vectorstore/models.py       ĐÃ CÓ - RetrievalFilter, QdrantChunkPayload, QdrantSearchResult.
app/core/settings_loader.py     CHỈ CÓ ChunkingSettings + RetrievalSettings qua get_rag_settings().
                                 KHÔNG có settings cho CORS_ORIGINS/LLM API key/API port - phần API
                                 cần bổ sung MỚI, không sửa 2 dataclass hiện có.
app/schemas/documents.py        ĐÃ CÓ DocumentBaseMetadata, DocumentVersionStatusFields
                                 (status field nằm trực tiếp trong document_versions).
app/databases/session.py        ĐÃ CÓ AsyncSessionLocal, get_session() (async generator).
requirements.txt                CHƯA có fastapi/uvicorn - phải bổ sung khi làm guide 01.
```

9 bảng DB dùng: `departments`, `document_types`, `documents`, `document_versions`,
`document_chunks`, `ingestion_jobs`, `document_recipients`, `document_assets`, `assets`. Không có
`document_version_status`, không có `version_status_history`, không dùng `validity_status`.

---

## 2. Danh Sách 20 Guide Con

| # | File | Nội dung | Nhóm |
|---|------|----------|------|
| 01 | `01_FASTAPI_APP_BOOTSTRAP_GUIDE.md` | Viết `app/main.py`: tạo `FastAPI()`, đăng ký CORS middleware, include router, thêm `fastapi`/`uvicorn` vào `requirements.txt`. | Backend core |
| 02 | `02_API_SETTINGS_AND_ENV_GUIDE.md` | Bổ sung settings MỚI cho API (CORS origins, app port, LLM provider key) tách riêng khỏi `ChunkingSettings`/`RetrievalSettings` hiện có; không sửa 2 dataclass đó. | Backend core |
| 03 | `03_HEALTH_ENDPOINT_GUIDE.md` | Viết `app/api/health.py` (`GET /api/v1/health` hoặc `GET /health` tuỳ chốt ở guide) trả trạng thái DB/Qdrant. | Backend core |
| 04 | `04_API_DEPENDENCIES_GUIDE.md` | `app/api/deps.py`: dependency cho `AsyncSession` (từ `get_session()`), `QdrantClient` (từ `get_qdrant_client()`), embedder, LLM instance. | Backend core |
| 05 | `05_RETRIEVER_IMPLEMENTATION_GUIDE.md` | Implement `app/retrieval/retriever.py` (class `Retriever`, `search_resolved_query()`) nối `search_points()` (đã có ở `repository.py`) + hydrate PostgreSQL. | Backend core |
| 06 | `06_RAG_CHAIN_WIRING_GUIDE.md` | Implement `app/llm/rag_chain.py` (`answer_question()`, `build_context_block()`) và `app/llm/generator.py` theo khung guide 18, dùng `RAG_ANSWER_PROMPT` thật ở `app/llm/prompts.py`. | Backend core |
| 07 | `07_RAG_ANSWER_ENDPOINT_GUIDE.md` | `app/api/routes/rag.py`: `POST /api/v1/rag/answer`, request/response đúng `06_API_SPEC.md` (`query`, `user_role`, `prefer_current` -> `answer`, `citations`, `related_assets`, `trace_id`). | Backend endpoints |
| 08 | `08_DOCUMENTS_LIST_ENDPOINT_GUIDE.md` | `app/api/routes/documents.py`: `GET /api/v1/documents` (filter theo `department`/`document_type`/`domain`, phân trang). | Backend endpoints |
| 09 | `09_DOCUMENT_DETAIL_ENDPOINT_GUIDE.md` | `GET /api/v1/documents/{id}` trong cùng `documents.py`, trả `DocumentBaseMetadata` + danh sách version tóm tắt. | Backend endpoints |
| 10 | `10_DOCUMENT_VERSION_DETAIL_ENDPOINT_GUIDE.md` | `app/api/routes/versions.py`: `GET /api/v1/document-versions/{id}`, trả field trạng thái từ `DocumentVersionStatusFields` (nằm trong `document_versions`, không có bảng status riêng). | Backend endpoints |
| 11 | `11_INGESTION_JOB_CREATE_ENDPOINT_GUIDE.md` | `app/api/routes/ingestion.py`: `POST /api/v1/ingestion/jobs`, nhận file/metadata, tạo record `ingestion_jobs`, chạy `app/ingestion/pipeline.py` (đã có) nền hoặc đồng bộ tuỳ chốt guide. | Ingestion endpoints |
| 12 | `12_INGESTION_JOB_STATUS_ENDPOINT_GUIDE.md` | `GET /api/v1/ingestion/jobs/{id}`, trả `current_step` đúng field đã chốt trong `06_API_SPEC.md`. | Ingestion endpoints |
| 13 | `13_INGESTION_PIPELINE_SERVICE_WIRING_GUIDE.md` | Nối `app/api/routes/ingestion.py` với `app/ingestion/pipeline.py`, `app/ingestion/index_document.py`, `app/embedding/embedder.py`, `app/vectorstore/repository.py` đã có sẵn thành 1 service layer duy nhất. | Ingestion endpoints |
| 14 | `14_FLUTTER_API_CLIENT_BOOTSTRAP_GUIDE.md` | Tạo `lib/core/api/api_client.dart` (mới), thêm `http: ^1.2.0` vào `pubspec.yaml`, cấu hình base URL theo platform (`10.0.2.2` cho Android emulator, `localhost` cho các nền tảng khác), `usesCleartextTraffic` cho dev HTTP. | Flutter integration |
| 15 | `15_FLUTTER_CHAT_INTEGRATION_GUIDE.md` | Sửa `lib/features/chat/chat_controller.dart`: thay `Future.delayed` + `buildMockAnswer()` bằng gọi `POST /api/v1/rag/answer` qua `api_client.dart`, giữ nguyên UX (bubble user, typing indicator). | Flutter integration |
| 16 | `16_FLUTTER_DOCUMENTS_INTEGRATION_GUIDE.md` | Map response `GET /api/v1/documents`/`GET /api/v1/documents/{id}` sang `SourceRef`/`DocumentDetail`; `icon`/`color`/`bg` của `DocumentCategory` vẫn map phía Flutter theo `document_type`, không lấy từ API. | Flutter integration |
| 17 | `17_ADMIN_API_CLIENT_BOOTSTRAP_GUIDE.md` | Tạo `src/api/httpClient.js` (mới, dùng `fetch` thuần, không thêm axios), thêm `.env`/`import.meta.env.VITE_API_BASE_URL` (mới, chưa có), CORS cho `http://localhost:5173`. | Admin React integration |
| 18 | `18_ADMIN_INGESTION_INTEGRATION_GUIDE.md` | Thay `src/api/mockClient.js` (`uploadDocument`/`runOcr`/`saveMetadata`/`runIngest`) bằng gọi endpoint thật ở guide 11-13; giữ contract `onStep` callback hoặc chốt lại nếu backend chưa hỗ trợ streaming step. | Admin React integration |
| 19 | `19_ADMIN_DOCUMENTS_INTEGRATION_GUIDE.md` | Thay `src/api/documentsMockApi.js` (`listDocuments`/`getDocument`/`updateDocument`) bằng endpoint guide 08-10; chốt rõ `src/api/referenceData.js` (documentTypes, departments...) giữ tĩnh hay chuyển sang endpoint riêng. | Admin React integration |
| 20 | `20_E2E_API_SMOKE_GUIDE.md` | Kịch bản curl/pytest chạy hết endpoint theo thứ tự ingestion -> documents -> rag/answer, cộng smoke tay với Flutter debug build và Admin `npm run dev`. | E2E smoke |

Thứ tự làm đề xuất bám theo cột "Nhóm": 01-06 (backend core) -> 07-10 (backend endpoints) ->
11-13 (ingestion endpoints) -> 14-16 (Flutter) -> 17-19 (Admin React) -> 20 (e2e smoke). Có thể
làm 07-10 song song với 11-13 vì không phụ thuộc nhau, nhưng cả hai đều cần 01-06 xong trước.

---

## 3. Convention Chung Cho Toàn Bộ 20 Guide

### 3.1 Prefix và versioning

```text
Mọi route public đều có prefix /api/v1, đúng 06_API_SPEC.md.
Không đổi field request/response đã chốt trong 06_API_SPEC.md
(query/user_role/prefer_current, answer/citations/related_assets/trace_id,
current_step, document-versions).
Nếu 1 guide con phát hiện cần field mới ngoài spec, phải ghi rõ "MỞ RỘNG so với
06_API_SPEC.md" trong guide đó, không tự đổi field cũ.
Không tạo /api/v2 trong phạm vi 20 guide này.
```

### 3.2 JSON response - không bọc envelope thừa

```text
Response trả đúng field đã định nghĩa trong 06_API_SPEC.md, không bọc thêm
{"data": ..., "success": true} hoặc {"code": 0, "result": ...}.
```

Ví dụ đúng (theo spec RAG answer):

```json
{
  "answer": "...",
  "citations": [],
  "related_assets": [],
  "trace_id": "..."
}
```

Ví dụ sai (không dùng):

```json
{
  "success": true,
  "data": {
    "answer": "...",
    "citations": []
  }
}
```

Lỗi vẫn dùng cơ chế `HTTPException` chuẩn của FastAPI (`{"detail": "..."}`), không tự định nghĩa
error envelope khác trừ khi guide 01-20 nói rõ.

### 3.3 Quy tắc đặt tên router trong `app/api/`

```text
app/api/routes/<domain>.py  - 1 file router theo domain, không dồn hết vào 1 file.
app/api/routes/rag.py       - router cho /api/v1/rag/answer.
app/api/routes/documents.py - router cho /api/v1/documents, /api/v1/documents/{id}.
app/api/routes/versions.py  - router cho /api/v1/document-versions/{id}.
app/api/routes/ingestion.py - router cho /api/v1/ingestion/jobs, /api/v1/ingestion/jobs/{id}.
app/api/health.py           - giữ riêng ở app/api/ (đã có file rỗng sẵn), không đưa
                               vào app/api/routes/.
```

Mỗi router file dùng `APIRouter(prefix="/api/v1/<domain>", tags=["<domain>"])`, sau đó
`app/main.py` chỉ làm việc duy nhất là `app.include_router(...)` cho từng router, không định
nghĩa route trực tiếp trong `main.py`.

### 3.4 CORS cho 2 frontend

```text
Flutter dev:
  - Android emulator gọi backend qua http://10.0.2.2:<port>.
  - Web/desktop debug gọi qua http://localhost:<port>.
  - Flutter không chạy trong browser với origin cố định như web app, nên CORS chủ yếu
    ảnh hưởng khi test bằng Flutter web; vẫn nên cho phép localhost.

React admin dev:
  - Vite default dev server: http://localhost:5173.
  - CORS_ORIGINS (setting MỚI ở guide 02) phải gồm tối thiểu:
    ["http://localhost:5173", "http://localhost", "http://10.0.2.2"]
```

Mẫu cấu hình CORS trong `app/main.py` (chi tiết đầy đủ nằm ở guide 01, đây chỉ minh hoạ
convention):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # list[str] từ settings MỚI, không hardcode rải rác
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Không hardcode origin list trực tiếp trong `main.py`; đọc từ settings MỚI (guide 02) để dev có
thể override qua env (`.env`, `CORS_ORIGINS=http://localhost:5173,http://10.0.2.2`).

### 3.5 Không phá hợp đồng đã chốt

```text
Không thêm bảng document_version_status/version_status_history.
Không thêm lại validity_status.
Không đổi RagStatus/OcrStatus/ReviewStatus trong app/schemas/enums.py.
Không tự định nghĩa lại review_status/rag_status/is_latest eligibility trong route -
phải dùng app/retrieval/eligibility.py (guide 15 §8.1, guide 22 §12.2) khi route nào
cần filter theo trạng thái publish.
```

---

## 4. Kiểm Thử Tổng Quát Cho Nhóm Guide

Mỗi guide 01-20 tự có phần kiểm thử riêng, nhưng quy ước chung:

```bash
# Chạy server dev sau khi guide 01 xong
cd chatbot/backend
uvicorn app.main:app --reload --port 8000

# Smoke health
curl http://localhost:8000/api/v1/health

# Smoke RAG answer (sau guide 07)
curl -X POST http://localhost:8000/api/v1/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "Em muốn xin bảng điểm thì cần gì?", "user_role": "student", "prefer_current": true}'
```

Guide 20 gom toàn bộ các lệnh curl này thành 1 kịch bản chạy tuần tự, cộng thêm chạy thật
Flutter (`flutter run`) và Admin (`npm run dev`) để xác nhận không còn phụ thuộc mock.

---

## Done Khi

- [ ] Bảng 20 guide con ở mục 2 khớp với danh sách file thực tế trong `api/` (khi các guide con
      được viết, tên file phải đúng như liệt kê, không đổi số thứ tự tuỳ ý).
- [ ] Convention prefix `/api/v1` và response không envelope được áp dụng nhất quán ở guide
      07-13, 20.
- [ ] Convention đặt tên router (`app/api/routes/<domain>.py`) được dùng đúng ở guide 07-13.
- [ ] CORS origins cho Flutter (`10.0.2.2`/`localhost`) và React admin (`localhost:5173`) được
      định nghĩa qua settings mới, không hardcode.
- [ ] Guide 02 chốt rõ settings API mới tách khỏi `ChunkingSettings`/`RetrievalSettings` hiện có
      trong `app/core/settings_loader.py`.
- [ ] Guide 01 xác nhận `fastapi`/`uvicorn` đã thêm vào `requirements.txt`.
- [ ] Không guide con nào thêm field/table ngoài 9 bảng và `06_API_SPEC.md` mà không ghi rõ là
      mở rộng.

## Phụ Thuộc / Thứ Tự Làm Trước

```text
Guide 00 (file này) không phụ thuộc guide nào, chỉ tổng hợp trạng thái đã có.
Guide 01-06 (backend core) cần đọc trước:
  - 21_RUNTIME_SETTINGS_GUIDE.md (quy tắc không dùng `or` fallback cho settings mới).
  - 16_PART_I_RETRIEVAL_GUIDE.md, 18_PART_K_RAG_ANSWER_CHAIN_GUIDE.md (khung Retriever/rag_chain).
  - 15_PART_H_QDRANT_VECTORSTORE_GUIDE.md (eligibility, search_points() đã có).
Guide 07-13 (endpoints) cần 01-06 xong trước vì đều import qua app/api/deps.py.
Guide 14-16 (Flutter) cần 07/08/09/10 xong trước (endpoint rag/answer + documents phải chạy được).
Guide 17-19 (Admin React) cần 08/09/10/11/12/13 xong trước (documents + ingestion jobs).
Guide 20 (e2e smoke) làm cuối cùng, sau khi cả 2 frontend đã hết mock.
```
