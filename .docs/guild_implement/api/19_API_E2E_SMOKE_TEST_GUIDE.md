# 19. E2E Smoke Test toan bo API + 2 Frontend

**Last Updated:** 2026-07-14

```text
Muc tieu file nay:
- Kiem thu tay (Swagger + curl) toan bo endpoint /api/v1/... sau khi guide
  00-18 trong bo chatbot/.docs/guild_implement/api/ da lam xong.
- Chay thuc Flutter (chatbot-ctu-app/frontend) noi backend thuc, theo
  checklist B6 cua chatbot-ctu-app/PLAN_CONNECT_BACKEND.md.
- Chay thuc admin-frontend (chatbot/admin-frontend) noi backend thuc, test
  ca 2 luong: ingest 1 file moi (upload->ocr->metadata->ingest) va
  quan ly tai lieu da co (list/edit).
- Tong ket bang pass/fail. KHONG viet code moi, KHONG sua file code nao.
```

Guide này là bước cuối, gom lại toàn bộ 18 guide trước trong bộ `api/` thành 1 kịch bản
kiểm thử tay. Không lặp lại nội dung thiết kế/code của guide 01-18, chỉ dẫn cách xác nhận
chúng chạy đúng khi ráp vào nhau.

---

## 0. Trạng Thái Thực Tế Trước Khi Test (đã đọc code, không suy đoán)

```text
Da xac nhan ton tai trong chatbot/.docs/guild_implement/api/ tai thoi diem viet guide nay:
  00_API_OVERVIEW_AND_CONVENTIONS.md, 01_APP_MAIN_AND_HEALTH_GUIDE.md,
  02_SETTINGS_ENV_CORS_GUIDE.md, 03_RAG_ANSWER_SCHEMA_GUIDE.md,
  04_RETRIEVER_IMPLEMENTATION_GUIDE.md, 06_REFERENCE_DATA_ENDPOINT_GUIDE.md.
CHUA co file cho guide 05, 07-18 (rag_chain wiring, router rag/answer, router
documents, router versions, router ingestion, Flutter/Admin integration) -
theo bang o 00_API_OVERVIEW_AND_CONVENTIONS.md muc 2, cac guide nay se duoc
viet sau, chua ton tai luc viet guide 19 nay.

Vi vay, cac buoc/curl trong file nay mo ta TRANG THAI KY VONG sau khi toan bo
00-18 hoan thanh, khong phai trang thai co the chay ngay bay gio. Truoc khi
chay guide nay, phai xac nhan lai (doc code) rang tung router/endpoint duoi
day da thuc su ton tai - neu chua, dung lai va hoan thien guide tuong ung
truoc, khong bo qua buoc do trong bang tong ket muc 5.
```

Endpoint public đã CHỐT trong `.docs/spec/ctu-service/06_API_SPEC.md` (nhóm A - có spec gốc):

```text
POST /api/v1/rag/answer
GET  /api/v1/documents
GET  /api/v1/documents/{id}
GET  /api/v1/document-versions/{id}
POST /api/v1/ingestion/jobs
GET  /api/v1/ingestion/jobs/{id}
```

Endpoint bổ sung, suy ra từ hợp đồng mock đã có sẵn trong `admin-frontend/src/api/mockClient.js`,
`admin-frontend/src/api/documentsMockApi.js`, và `chatbot-ctu-app/PLAN_CONNECT_BACKEND.md`
(nhóm B - CHƯA có trong `06_API_SPEC.md`, cần một guide riêng chốt route trước khi test được):

```text
GET  /api/v1/document-categories        (PLAN_CONNECT_BACKEND.md A7, chua co router thuc)
GET  /api/v1/documents/{id}/download    (PLAN_CONNECT_BACKEND.md A8, chua co router thuc)
GET  /api/v1/versions                   (documentsMockApi.js listDocuments, chua co router thuc)
PUT  /api/v1/versions/{id}              (documentsMockApi.js updateDocument, chua co router thuc)
POST /api/v1/documents/upload           (mockClient.js uploadDocument, chua co router thuc)
POST /api/v1/versions/{id}/ocr          (mockClient.js runOcr, chua co router thuc)
PUT  /api/v1/versions/{id}/metadata     (mockClient.js saveMetadata, chua co router thuc)
POST /api/v1/versions/{id}/ingest       (mockClient.js runIngest, chua co router thuc)
```

Chú ý: `GET /api/v1/versions` (nhóm B) và `GET /api/v1/document-versions/{id}` (nhóm A) là
**hai route khác nhau**, không được nhầm lẫn khi test — route đầu do admin-frontend mock đặt tên
số nhiều rút gọn cho danh sách phiên bản đang quản lý, route sau là chi tiết 1 version theo đúng
spec gốc.

---

## 1. Điều Kiện Trước Khi Test

```bash
# 1. Docker services (Postgres + Qdrant) dang chay
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot
docker compose ps

# 2. Alembic da upgrade head, DB co it nhat vai dong departments/document_types
cd backend
..\..\.venv\Scripts\alembic.exe current

# 3. .env co du bien: DATABASE_URL, QDRANT_URL, QDRANT_API_KEY, NVIDIA_API_KEY,
#    NVIDIA_EMBEDDING_MODEL, CORS_ORIGINS, LLM_PROVIDER, LLM_API_KEY, LLM_CHAT_MODEL
#    (xem 02_SETTINGS_ENV_CORS_GUIDE.md muc 8)
```

Nếu bất kỳ điều kiện trên chưa đủ, dừng lại và xử lý trước — chạy smoke test khi thiếu env sẽ
cho kết quả fail sai (do thiếu config, không phải do code lỗi).

---

## 2. Bước 1: Backend Qua Swagger + Curl

Chạy server:

```bash
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Mở `http://localhost:8000/docs` (Swagger tự sinh từ FastAPI), thử từng route bằng UI hoặc bằng
`curl` bên dưới. Đánh dấu vào checklist muc 5 khi mỗi route trả đúng status/shape mong đợi.

### 2.1. `GET /health`

```bash
curl -i http://localhost:8000/health
```

Kỳ vọng: `200`, `{"status":"ok"}`.

### 2.2. `POST /api/v1/rag/answer`

```bash
curl -X POST http://localhost:8000/api/v1/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Em muon xin bang diem thi can gi?",
    "user_role": "student",
    "prefer_current": true
  }'
```

Kỳ vọng: `200`, đúng shape `RagAnswerResponse` (guide 03):

```json
{
  "answer": "...",
  "citations": [
    {
      "document_id": 12,
      "version_id": 34,
      "title": "Quy dinh cong tac hoc vu",
      "page_start": 2,
      "page_end": 3,
      "section_title": "Dieu 5",
      "source_file": "qd-3266.md",
      "quote_snippet": "..."
    }
  ],
  "related_assets": [],
  "trace_id": "..."
}
```

Nếu chưa có dữ liệu published trong Qdrant, kỳ vọng `citations: []` và `answer` là câu "chưa có
đủ thông tin" (theo thiết kế `app/llm/rag_chain.py`, guide 18/06), không phải lỗi 500.

### 2.3. `GET /api/v1/document-categories` (nhóm B)

```bash
curl http://localhost:8000/api/v1/document-categories
```

Kỳ vọng (theo `PLAN_CONNECT_BACKEND.md` A7, ví dụ):

```json
[{ "key": "quyet-dinh", "name": "Quyết định", "count": 4, "latest_date": "2023-09-01" }]
```

### 2.4. `GET /api/v1/documents`

```bash
curl "http://localhost:8000/api/v1/documents?document_type=quyet_dinh"
```

Kỳ vọng: `200`, danh sách item tối thiểu `{document_id, title, document_type, updated_date,
department}` (theo `06_API_SPEC.md` + `DocumentBaseMetadata`, guide 08 khi được viết sẽ chốt
chính xác field). `[]` nếu không có tài liệu khớp filter, không phải lỗi.

### 2.5. `GET /api/v1/documents/{id}`

```bash
curl http://localhost:8000/api/v1/documents/12
```

Kỳ vọng: `200` với đủ metadata (`DocumentBaseMetadata` + tóm tắt version), hoặc `404` nếu `id`
không tồn tại — không phải `500`.

### 2.6. `GET /api/v1/documents/{id}/download` (nhóm B)

```bash
curl -i -OJ http://localhost:8000/api/v1/documents/12/download
```

Kỳ vọng: `200`, header `Content-Disposition: attachment; filename=...`, file PDF tải được. `404`
nếu file gốc không tồn tại trên server (không phải `500`).

### 2.7. `GET /api/v1/versions` (nhóm B)

```bash
curl "http://localhost:8000/api/v1/versions?rag_status=published"
```

Kỳ vọng: `200`, danh sách version khớp field trong `documentsMockApi.js` (`version_key`, `title`,
`ocr_status`, `review_status`, `rag_status`, `updated_at`, ...), đã bỏ `validity_status` và
`version_label` (không nằm trong 9 bảng đã chốt — nếu response còn field này, đó là bug cần sửa
ở guide router, không phải hành vi đúng).

### 2.8. `PUT /api/v1/versions/{id}` (nhóm B)

```bash
curl -X PUT http://localhost:8000/api/v1/versions/34 \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"title": "Tieu de moi"}}'
```

Kỳ vọng: `200`, trả `document_version` đã cập nhật; nếu `canonical_markdown` thay đổi, `rag_status`
phải được đưa về pipeline chunk/embed lại theo đúng thiết kế `updateDocument` trong
`documentsMockApi.js`, không giữ nguyên `rag_status=published` với nội dung cũ.

### 2.9. `POST /api/v1/documents/upload` (nhóm B)

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@E:\path\to\vi-du.pdf" \
  -F "title=Vi du tai lieu moi"
```

Kỳ vọng: `200`, trả `{document_id, document_version_id, version_key, source_path, checksum,
ocr_status: "not_started", review_status: "not_reviewed", rag_status: "not_indexed"}` (theo
`mockClient.js::uploadDocument`).

### 2.10. `POST /api/v1/versions/{id}/ocr` (nhóm B)

```bash
curl -X POST http://localhost:8000/api/v1/versions/57/ocr
```

Kỳ vọng: `200`, trả `{ocr_status, canonical_markdown_path, page_count, char_count, markdown}`.
Nếu backend giữ nguyên hợp đồng `onStep` streaming của `mockClient.js` (step progress UI), route
này cần trả dạng streaming (SSE/chunked) — guide router riêng (18 trong bảng 00) phải ghi rõ chốt
sync hay streaming trước khi test bước này; nếu chưa chốt, test tạm ở dạng sync (đợi xong rồi trả
1 lần) và ghi chú lại trong bảng tổng kết.

### 2.11. `PUT /api/v1/versions/{id}/metadata` (nhóm B)

```bash
curl -X PUT http://localhost:8000/api/v1/versions/57/metadata \
  -H "Content-Type: application/json" \
  -d '{"document_type": "quyet_dinh", "domain": "hoc_vu", "responsible_department": ["PDT"]}'
```

Kỳ vọng: `200`, `{document_version_id, saved: true, metadata, review_status: "reviewing"}`.

### 2.12. `POST /api/v1/versions/{id}/ingest` (nhóm B)

```bash
curl -X POST http://localhost:8000/api/v1/versions/57/ingest
```

Kỳ vọng: `200`, `{rag_status: "published", parent_chunks, child_chunks, total_chunks,
qdrant_points, sample_chunk_keys}`. Sau khi route này chạy thành công, `POST /api/v1/rag/answer`
với câu hỏi liên quan tới tài liệu vừa ingest phải trả `citations` không rỗng — đây là điểm nối
quan trọng giữa luồng admin (ingest) và luồng student (rag/answer), phải test cả hai theo thứ tự
này, không test rời rạc.

### 2.13. `GET /api/v1/document-versions/{id}`

```bash
curl http://localhost:8000/api/v1/document-versions/34
```

Kỳ vọng: `200`, trả field trạng thái từ `DocumentVersionStatusFields`
(`ocr_status`, `review_status`, `rag_status`, `status_note`) nằm trực tiếp trong
`document_versions`, không có bảng `document_version_status` riêng (đúng `06_API_SPEC.md`).

### 2.14. `POST /api/v1/ingestion/jobs` + `GET /api/v1/ingestion/jobs/{id}`

```bash
curl -X POST http://localhost:8000/api/v1/ingestion/jobs \
  -H "Content-Type: application/json" \
  -d '{"document_version_id": 34}'

curl http://localhost:8000/api/v1/ingestion/jobs/1
```

Kỳ vọng: job status dùng field `current_step` (đúng `06_API_SPEC.md`), không dùng tên field khác
(`step`, `stage`, ...).

---

## 3. Bước 2: Flutter App Thật Nối Backend

Theo checklist B6 của `chatbot-ctu-app/PLAN_CONNECT_BACKEND.md`. Trước khi chạy, xác nhận guide
14/15/16 (Flutter integration, bảng 00 mục 2) đã thay `chat_controller.dart` và thêm
`lib/core/api/api_client.dart` như thiết kế — nếu chưa, `chat_controller.dart` vẫn còn gọi
`buildMockAnswer()` (đã xác nhận là code thật hiện tại trong `lib/features/chat/chat_controller.dart`)
và bước này sẽ luôn "pass giả" vì không thật sự gọi network.

```bash
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot-ctu-app\frontend
flutter analyze
flutter run
```

Checklist thủ công trên thiết bị/emulator:

```text
[ ] Go 1 cau hoi trong tab Chat -> thay bubble user hien ngay, sau do typing
    indicator, roi cau tra loi THAT (khong con la kMockAnswer co dinh).
[ ] Khoi "Nguon tham khao" duoi cau tra loi hien dung so luong Citation
    tra ve tu POST /api/v1/rag/answer, khong con la kMockSources co dinh.
[ ] Bam vao 1 the nguon -> mo man chi tiet tai lieu, hien dung
    title/section/page tu Citation (hoac tu GET /api/v1/documents/{id}
    neu guide 16 da noi API nay).
[ ] Tat backend (Ctrl+C uvicorn) -> gui lai 1 cau hoi -> app hien bubble
    loi than thien ("Xin loi, he thong dang gap su co...", theo thiet ke
    B4 cua PLAN_CONNECT_BACKEND.md), KHONG crash app, KHONG treo o trang
    thai typing vo thoi han.
[ ] Mo lai backend, vao tab Tai lieu -> danh sach category load duoc tu
    GET /api/v1/document-categories (khong con la kDocumentCategories
    co dinh trong mock_data.dart).
[ ] Bam vao 1 category -> danh sach file trong category load tu
    GET /api/v1/documents?document_type=...
[ ] Bam vao 1 file -> man chi tiet load tu GET /api/v1/documents/{id},
    co nut mo/tai file goi GET /api/v1/documents/{id}/download.
```

Nếu chạy trên Android emulator, xác nhận base URL đang là `http://10.0.2.2:8000` (không phải
`localhost`) và `AndroidManifest.xml` đã có `android:usesCleartextTraffic="true"` — nếu quên bước
này, mọi request sẽ timeout/refuse ngay cả khi backend đang chạy đúng.

---

## 4. Bước 3: Admin-Frontend Thật Nối Backend

Trước khi chạy, xác nhận guide 17/18/19 (Admin React integration, bảng 00 mục 2) đã thay
`src/api/mockClient.js` và `src/api/documentsMockApi.js` bằng `fetch()` thật gọi các endpoint
nhóm B ở mục 0 — nếu chưa, `App.jsx`/`PipelineContext.jsx` vẫn đang chạy hoàn toàn trên mock nội
bộ (không có network call nào), và bước này cũng sẽ "pass giả".

```bash
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\admin-frontend
npm run dev
```

`vite.config.js` đã có `proxy: { '/api': 'http://localhost:8000' }` sẵn, nên không cần đổi base
URL khi dev — mở `http://localhost:5174` (port khai báo trong `vite.config.js`).

### 4.1. Luồng ingest 1 file mới

```text
[ ] Tab Upload: chon 1 file PDF, dat title -> bam Upload -> goi thuc
    POST /api/v1/documents/upload, nhan document_id/version_id thuc
    (khong con la seq++ tang dan trong mockClient.js).
[ ] Tab OCR: bam Run OCR -> step progress hien dung tien trinh thuc (hoac
    it nhat ket qua cuoi dung, tuy backend sync/streaming da chot) ->
    xem duoc canonical markdown tra ve.
[ ] Tab Metadata: dien document_type/domain/responsible_department/audience
    -> Save -> goi thuc PUT /api/v1/versions/{id}/metadata, review_status
    chuyen thanh "reviewing".
[ ] Tab Ingest: bam Run Ingest -> goi thuc POST /api/v1/versions/{id}/ingest
    -> nhan parent_chunks/child_chunks/qdrant_points thuc (khac 0).
[ ] Tab Output: xem tong ket dung du lieu vua ingest, khong con la so lieu
    gia lap tu countHeadings() trong mockClient.js.
[ ] Sang app Flutter (hoac curl truc tiep), hoi 1 cau lien quan noi dung
    file vua ingest -> POST /api/v1/rag/answer phai tra citation tro ve
    dung version_key vua tao.
```

### 4.2. Luồng quản lý tài liệu đã có

```text
[ ] Trang DocumentsListPage: danh sach load tu GET /api/v1/versions, filter
    theo department_id/document_type_id/rag_status/review_status hoat dong
    dung (goi lai API voi query param, khong loc client-side tren data tinh
    cu cua documentsMockApi.js).
[ ] Bam vao 1 dong -> DocumentEditPage load chi tiet tu
    GET /api/v1/versions/{id} (hoac GET /api/v1/document-versions/{id} neu
    guide router quyet dinh dung chung route nay - ghi ro lua chon thuc te
    vao bang tong ket muc 5).
[ ] Sua metadata hoac noi dung -> Save -> goi thuc PUT /api/v1/versions/{id},
    step progress hien dung nhanh (chi cap nhat metadata, giu vector) hay
    cham (content doi, chunk/embed lai) tuy truong hop, giong logic
    updateDocument trong documentsMockApi.js.
[ ] Sau khi sua content 1 tai lieu dang published, hoi lai cau hoi lien quan
    qua Flutter/curl -> cau tra loi phai phan anh noi dung MOI, khong con
    tra ve noi dung cu (xac nhan qdrant_delete + qdrant_upsert da chay dung).
```

### 4.3. Dữ liệu tham chiếu (department/document_type dropdown)

```text
[ ] Dropdown department/document_type trong form Metadata/DocumentEditPage
    load tu GET /api/v1/departments va GET /api/v1/document-types (guide 06),
    khong con la array tinh trong referenceData.js.
[ ] audienceOptions/domainOptions/assetTypes/ocrStatuses/reviewStatuses/
    ragStatuses van la enum tinh trong referenceData.js (theo quyet dinh
    o guide 06 muc 5) - xac nhan cac gia tri nay KHOP voi Literal thuc trong
    app/schemas/enums.py, khong con gia tri cu sai lech (vi du assetTypes
    cu la ['FORM_LINK','VIDEO_LINK','WEB_LINK'], phai doi thanh
    ['form','template','guide','attachment']).
```

---

## 5. Bảng Tổng Kết Pass/Fail

Điền lại bảng này mỗi lần chạy smoke test, kèm ngày chạy và commit hash để đối chiếu sau:

| # | Route/Luồng | Nhóm | Kỳ vọng | Pass/Fail | Ghi chú |
|---|---|---|---|---|---|
| 1 | `GET /health` | A | `200 {"status":"ok"}` | | |
| 2 | `POST /api/v1/rag/answer` | A | citations khớp Qdrant | | |
| 3 | `GET /api/v1/document-categories` | B | count đúng theo DB | | |
| 4 | `GET /api/v1/documents` | A | list/filter đúng | | |
| 5 | `GET /api/v1/documents/{id}` | A | 200/404 đúng | | |
| 6 | `GET /api/v1/documents/{id}/download` | B | file tải được | | |
| 7 | `GET /api/v1/versions` | B | list version | | |
| 8 | `PUT /api/v1/versions/{id}` | B | update + re-index đúng | | |
| 9 | `POST /api/v1/documents/upload` | B | tạo version mới | | |
| 10 | `POST /api/v1/versions/{id}/ocr` | B | trả markdown | | |
| 11 | `PUT /api/v1/versions/{id}/metadata` | B | review_status đổi | | |
| 12 | `POST /api/v1/versions/{id}/ingest` | B | chunk/embed/index | | |
| 13 | `GET /api/v1/document-versions/{id}` | A | status field đúng | | |
| 14 | `POST/GET /api/v1/ingestion/jobs` | A | `current_step` đúng | | |
| 15 | Flutter — chat hỏi/đáp thật | - | UX giữ nguyên, data thật | | |
| 16 | Flutter — tắt backend không crash | - | bubble lỗi thân thiện | | |
| 17 | Flutter — tab Tài liệu | - | category/list/detail/download | | |
| 18 | Admin — luồng ingest 1 file | - | upload→ocr→metadata→ingest | | |
| 19 | Admin — luồng list/edit tài liệu | - | filter + update + re-index | | |
| 20 | Admin — dropdown reference data | - | không còn array tĩnh lệch enum | | |

Nếu bất kỳ dòng nào Fail, không tiếp tục các dòng phụ thuộc phía dưới (ví dụ dòng 15-17 phụ thuộc
dòng 2/4/5/6 đã Pass) — quay lại guide tương ứng để sửa trước khi test tiếp.

---

## 6. Không Làm Trong File Này

```text
Khong viet code moi (router/schema/model).
Khong sua chatbot-ctu-app/frontend hay chatbot/admin-frontend.
Khong tu chot route nhom B (document-categories, documents/{id}/download,
versions/*, documents/upload) thanh chinh thuc trong 06_API_SPEC.md - do
la viec cua mot guide rieng bo sung spec, khong phai guide smoke test nay.
```

---

## Done Khi

- [ ] Toàn bộ 20 dòng ở bảng mục 5 đã chạy và ghi kết quả Pass/Fail thật, không để trống.
- [ ] Mọi Fail đều có ghi chú nguyên nhân và đã trỏ về guide cần sửa (01-18).
- [ ] Flutter app chạy được với backend thật, không còn phụ thuộc `buildMockAnswer()`/
      `kMockSources`/`kMockDocuments`/`kDocumentCategories`/`kDocumentsByCategory` trong
      `lib/shared/mock/mock_data.dart` cho luồng đã test Pass.
- [ ] Admin-frontend chạy được với backend thật, không còn phụ thuộc `mockClient.js`/
      `documentsMockApi.js` cho luồng đã test Pass.
- [ ] Luồng nối giữa admin (ingest) và student (rag/answer) đã được test theo đúng thứ tự
      (ingest trước, hỏi sau) và trả kết quả nhất quán.
- [ ] Danh sách route nhóm B (mục 0) đã được đối chiếu với `06_API_SPEC.md` — nếu quyết định giữ
      lại các route này, cần một guide bổ sung chính thức hoá vào spec; nếu quyết định đổi tên
      cho khớp spec gốc (ví dụ dùng `document-versions` thay `versions`), phải sửa lại cả backend
      và 2 mock layer đồng bộ, không sửa một phía.

---

## Phụ Thuộc / Thứ Tự Làm Trước

```text
Guide nay lam CUOI CUNG trong bo 20 guide o api/, sau khi:
  - 01-06 (backend core) xong: FastAPI app, settings/CORS, schema rag,
    retriever, reference-data.
  - 07-13 (backend endpoints + ingestion) xong: router rag/answer,
    documents, document-versions, ingestion/jobs, va (neu giu nhom B)
    router cho document-categories/download/versions-CRUD/upload/ocr/
    metadata/ingest.
  - 14-16 (Flutter integration) xong: api_client.dart, chat_controller.dart
    goi API thuc, man Tai lieu noi API thuc.
  - 17-19 (Admin React integration) xong: httpClient.js, mockClient.js va
    documentsMockApi.js duoc thay bang fetch thuc.
Neu bat ky guide nao trong danh sach tren chua xong, chi chay duoc phan
tuong ung trong bang muc 5, khong danh gia toan bo la Pass.
```
