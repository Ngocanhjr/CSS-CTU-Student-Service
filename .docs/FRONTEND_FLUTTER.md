# Flutter Frontend Guide

## Frontend decision

The CTU Student Service UI uses **Flutter**.

Backend pipeline decisions visible to Flutter admin screens:

| Pipeline stage | Current decision |
|---|---|
| OCR | `ocr-pvl` |
| RAG/chunking workflow | LangChain |
| Embedding model | `BAAI/bge-m3` |
| Runnable-code target | `2026-06-19` |
| HNSW | Future backend optimization; frontend should not expose it in MVP |

Use Flutter for:

- student chat interface;
- citation/source drawer;
- procedure detail and checklist screen;
- related forms/assets screen;
- admin dashboard;
- document upload and ingestion job tracking;
- metadata review and publish workflow;
- evaluation/feedback screens when needed.

Do not use React, Next.js, Tailwind, plain HTML, or another frontend stack unless the project owner explicitly changes this decision later.

## Recommended Flutter architecture

```text
frontend/
├── lib/
│   ├── main.dart
│   ├── app.dart
│   ├── core/
│   │   ├── config/
│   │   ├── network/
│   │   ├── theme/
│   │   ├── routing/
│   │   └── widgets/
│   ├── features/
│   │   ├── auth/
│   │   ├── chat/
│   │   ├── citations/
│   │   ├── procedures/
│   │   ├── assets/
│   │   ├── documents/
│   │   ├── ingestion/
│   │   ├── admin_dashboard/
│   │   └── evaluation/
│   └── shared/
│       ├── models/
│       ├── dto/
│       └── utils/
└── test/
```

## State management

Pick one pattern and use it consistently.

Recommended options:

| Option | When to use |
|---|---|
| Riverpod | Recommended default for MVP; clean dependency injection and async state. |
| BLoC | Use if the team prefers strict event/state separation. |

Do not mix Riverpod, BLoC, Provider, and GetX without a clear reason.

## API integration rule

Flutter talks only to Backend API/RAG Service through HTTP APIs.

Important endpoints expected by Flutter:

```text
POST /rag/answer
GET  /documents
GET  /document-versions
POST /ingestion/jobs
GET  /ingestion/jobs/{id}
POST /documents/upload
POST /document-versions/{id}/validate
POST /document-versions/{id}/approve
POST /index/rebuild
```

Flutter should use typed DTOs for:

- answer response;
- citation;
- related asset/form;
- document;
- document version;
- ingestion job;
- validation error.

## Student screens

### Chat screen

Required UI parts:

- query input;
- answer area;
- loading/streaming state;
- answer source status;
- citation list/drawer;
- related forms/assets;
- feedback buttons.

If the answer lacks enough source, show the backend fallback message clearly. Do not hide missing-source warnings.

### Citation drawer

Show:

- document title;
- version/code if available;
- page or section;
- source file;
- quoted snippet if API returns it;
- related downloadable asset if allowed.

### Procedure detail/checklist screen

Show only backend-returned data:

- 대상/đối tượng áp dụng;
- hồ sơ cần chuẩn bị;
- các bước thực hiện;
- nơi nộp;
- thời gian xử lý;
- biểu mẫu liên quan;
- nguồn/citation.

Do not hard-code procedure steps in Flutter.

## Admin screens

### Admin dashboard

Show overview cards:

- total documents;
- waiting OCR;
- waiting review;
- approved/published;
- failed ingestion jobs;
- expired/replaced documents.

### Document upload screen

Flow:

```text
Upload file
→ create document/version draft
→ create ingestion job
→ show `ocr-pvl` OCR status
→ show extracted Markdown/metadata preview
→ admin completes metadata
→ validate metadata
→ approve
→ LangChain chunk / BGE-M3 embed / Qdrant index
→ published
```

### Metadata review screen

Admin must be able to edit and confirm:

- title;
- document_type;
- domain;
- department;
- audience;
- code;
- effective_date;
- expiry_date;
- is_latest;
- validity_status;
- review_status;
- rag_status;
- source_file/path/url;
- citation_type;
- ocr_engine;
- embedding_model.

## UX rules

- Use CTU-friendly clean blue theme.
- Prioritize readability over dense UI.
- Show status badges for OCR/review/validity/RAG status.
- Surface validation errors clearly before allowing publish/index.
- Show source/citation access near every answer.
- Keep admin destructive actions explicit: deactivate, reindex, replace version.
- Design responsive layouts for desktop web and mobile screens if Flutter Web is enabled.

## Security boundary

Flutter may hide or disable UI controls based on user role, but Backend must enforce all permissions.

Flutter must never be the only place that checks:

- admin/reviewer role;
- document confidentiality;
- publish permission;
- download permission;
- latest/valid status.
