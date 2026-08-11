# 09. Đặc Tả Frontend (Flutter)

## Flutter App Scope

### Platform Support
- Mobile (Android/iOS)
- Web (future)

### Tech Stack
- **Framework:** Flutter
- **State Management:** _[Riverpod/BLoC — chọn 1 và dùng consistent]_
- **API Client:** _[Dio hoặc generated OpenAPI client]_
- **Routing:** _[go_router hoặc auto_route]_

---

## Student Screens

### 1. Chat Screen
**Purpose:** _[Main screen cho student query]_

**UI Components:**
- Query input field
- Answer display area
- Loading/streaming state
- Citation list/chips
- Related external links section
- Feedback buttons

**Behavior:**
- _[Input validation]_
- _[Call RAG answer API defined in `06_API_SPEC.md`]_
- _[Display answer + citations]_
- _[Handle errors: no results, timeout]_

---

### 2. Citation Drawer/Modal
**Purpose:** _[Show citation detail]_

**UI Components:**
- Document title
- Version/code
- Page/section
- Source file name
- Quote snippet
- Download link (if public)

**Trigger:** _[Click on citation chip]_

---

### 3. Procedure Detail Screen
**Purpose:** _[Show full procedure checklist]_

**UI Components:**
- Đối tượng áp dụng
- Hồ sơ cần chuẩn bị
- Các bước thực hiện
- Nơi nộp
- Thời gian xử lý
- Biểu mẫu liên quan
- Nguồn/citations

**Note:** _[Không hard-code procedure content, lấy từ backend]_

---

### 4. Chat History Screen
**Purpose:** _[Xem lại chat history]_

**UI Components:**
- List of sessions
- Click to view messages
- Delete session button

---

## Admin Screens

### 1. Admin Dashboard
**Purpose:** _[Overview cards]_

**Widgets:**
- Total documents
- Waiting OCR
- Waiting review
- approved/published
- Failed jobs
- Unpublished/deactivated documents

---

### 2. Document List Screen
**Purpose:** _[List all documents với filters]_

**Filters:**
- Department
- Document type
- Status (ocr_status, review_status, rag_status)
- Date range

**Actions:**
- View detail
- Edit metadata
- Upload new version

---

### 3. Document Upload Screen
**Purpose:** _[Upload new document]_

**Flow:**
```
Select file → Upload → Show OCR status → Preview Markdown
→ Complete metadata → Validate → Approve → Publish
```

**UI Components:**
- File picker
- Progress bar
- Metadata form
- Validation error display
- OCR output preview

---

### 4. Metadata Validation Screen
**Purpose:** _[Admin complete và validate metadata]_

**Editable Fields:**
- `title`, `document_type`, `domain`, `audience`
- `code`, `issued_date`, `is_latest`
- `review_status`

**Recipient Departments (nhiều-nhiều qua `document_recipients`):**
- Multi-select picker — chọn một hoặc nhiều phòng ban
- Date picker — nhập một `effective_date` áp dụng chung cho tất cả phòng ban vừa chọn
- Khi submit: tạo N rows trong `document_recipients(document_version_id, department_id, effective_date)`
- Hiển thị danh sách phòng ban đã được gán kèm `effective_date` tương ứng

> `department` không phải field đơn trên `documents`. Quan hệ được lưu ở bảng trung gian
> `document_recipients`. Một version có thể gửi đến nhiều phòng ban trong cùng một lần
> với cùng một `effective_date`.

**Actions:**
- Save draft
- Validate
- Submit for review

---

### 5. OCR Review Screen
**Purpose:** _[Review OCR Markdown output]_

**UI Components:**
- Markdown preview
- Raw Markdown editor
- Page marker validation
- Table structure check
- Approve/reject buttons

---

### 6. Ingestion Job Progress Screen
**Purpose:** _[Track ingestion job progress]_

**UI Components:**
- Job list với `current_step` badges
- Click to view detail: stages, progress, errors
- Retry button cho failed jobs

---

### 7. Document Version Detail Screen
**Purpose:** _[View full document version info]_

**Sections:**
- Metadata
- Status timeline
- Chunks preview
- Related external links
- Ingestion jobs
- Version history (replaces/replaced_by)

---

## UX Consistency Rules

### Theme
_[CTU-friendly clean blue theme, Material Design 3]_

### Status Badges
- `ocr_status`: _[not_started=grey, processing=blue, need_review=orange, done=green, failed=red]_
- `review_status`: _[not_reviewed=grey, reviewing=blue, need_fix=orange, approved=green, rejected=red]_
- `rag_status`: _[not_indexed=grey, chunked=blue, embedded=blue, indexed=yellow, published=green, deactivated=grey, failed=red]_

### Loading States
_[Spinner, skeleton loaders, progress bars]_

### Empty States
_[Friendly empty state messages với illustrations]_

### Error States
_[User-friendly error messages, retry buttons]_

---

## State Management Strategy

### State Management Choice
_[Riverpod (recommended) hoặc BLoC]_

### State Objects
```dart
// Example with Riverpod
class ChatState {
  final String query;
  final String? answer;
  final List<Citation> citations;
  final List<Asset> relatedAssets;
  final bool isLoading;
  final String? error;
}
```

---

## API Integration

### HTTP Client Setup
_[Dio with interceptors: auth token, error handling, logging]_

### DTOs (Data Transfer Objects)
_[Match backend Pydantic schemas]_

### Error Handling
```dart
try {
  final response = await apiClient.post('/api/v1/rag/answer', data: request);
  return AnswerResponse.fromJson(response.data);
} on DioException catch (e) {
  if (e.response?.statusCode == 404) {
    throw NotFoundException();
  }
  throw ApiException(e.message);
}
```

---

## Security Boundary

### UI Role Check
_[Hide/disable controls dựa trên role, nhưng backend enforce permissions]_

### Never Trust Client
- Document confidentiality check → backend
- Publish permission → backend
- Download permission → backend

---

## Responsive Layout

### Mobile-First
_[Design cho mobile trước]_

### Tablet/Desktop
_[Responsive layout với breakpoints]_

---

**Status:** Skeleton — Cần điền chi tiết UI mockups và component specs  
**Priority:** P1


