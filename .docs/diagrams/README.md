# CTU-Service Diagrams

Thư mục này chứa sơ đồ kỹ thuật cho dự án CTU Student Service.

---

## Cấu Trúc Thư Mục

```
diagrams/
├── README.md                    # File này
├── mermaid/                     # Sơ đồ Mermaid (technical, maintainable)
│   ├── system_context.mmd
│   ├── system_container.mmd
│   ├── rag_pipeline.mmd
│   ├── ingestion_pipeline.mmd
│   ├── erd.mmd
│   ├── sequence_chat_flow.mmd
│   └── sequence_ingestion_flow.mmd
│
└── excalidraw/                  # Sơ đồ Excalidraw (presentation, polished)
    ├── README.md
    └── *.excalidraw             # Source files
```

---

## Mermaid Diagrams (Technical)

### Mục Đích
Mermaid diagrams được dùng cho:
- Documentation kỹ thuật
- Version control friendly (text-based)
- Dễ update khi architecture thay đổi
- Render trực tiếp trong GitHub/GitLab

### Danh Sách Sơ Đồ

| File | Type | Mô Tả |
|------|------|-------|
| `system_context.mmd` | C4 Level 1 | System context: users, external systems |
| `system_container.mmd` | C4 Level 2 | Containers: frontend, backend, databases |
| `rag_pipeline.mmd` | Flowchart | RAG query flow từ user question → answer |
| `ingestion_pipeline.mmd` | Flowchart | Document ingestion từ upload → indexed |
| `erd.mmd` | ERD | Database entity-relationship diagram |
| `sequence_chat_flow.mmd` | Sequence | Student question → answer sequence |
| `sequence_ingestion_flow.mmd` | Sequence | Admin upload → publish sequence |
| `rag-ingestion-module.mmd` | Flowchart | RAG Ingestion Module chi tiết: canonical MD + YAML → validate → chunk → embed → index → publish |
| `rag-retrieval-module.mmd` | Flowchart | RAG Retrieval Module chi tiết: query → metadata filter → PostgreSQL FTS/BM25 + Qdrant dense → RRF → context pack |
| `rag-llm-generation-module.mmd` | Flowchart | RAG LLM Answer Generation Module chi tiết: context pack → prompt → LLM → citation → trace → response |

### Cách Xem Mermaid Diagrams

**Option 1: GitHub/GitLab**
- Mermaid code blocks render tự động

**Option 2: VS Code**
- Install extension: "Mermaid Preview"
- Right-click `.mmd` file → Preview

**Option 3: Online**
- [Mermaid Live Editor](https://mermaid.live/)
- Copy/paste `.mmd` content

**Option 4: CLI**
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i system_context.mmd -o system_context.png
```

---

## Excalidraw Diagrams (Presentation)

### Mục Đích
Excalidraw diagrams được dùng cho:
- Presentation slides
- High-level overview cho stakeholders
- Polished visuals cho reports/proposals
- Conceptual diagrams (less technical detail)

### Workflow
1. Draw diagrams manually trong [Excalidraw](https://excalidraw.com/)
2. Save source files (`.excalidraw`) trong `excalidraw/` folder
3. Export to PNG/SVG cho presentations
4. Keep `.excalidraw` sources trong git để có thể edit lại

**Note:** Excalidraw files không được generate bởi Kiro/AI. Chúng phải được vẽ manually để đảm bảo visual quality.

---

## Diagram Update Guidelines

### Khi Nào Cần Update Diagrams

- Architecture thay đổi (thêm/bớt components)
- Database schema thay đổi (thêm tables/relationships)
- Data flow thay đổi
- API endpoints thay đổi
- Deployment topology thay đổi

### Workflow Update

1. **Update specs first:** Thay đổi `.docs/spec/ctu-service/*.md` trước
2. **Update Mermaid diagrams:** Sync Mermaid diagrams với specs
3. **Commit together:** Commit spec changes + diagram changes cùng nhau
4. **Update Excalidraw (optional):** Update presentation diagrams nếu cần present

### Consistency Rules

- Mermaid diagrams phải match với specs
- Naming trong diagrams phải match với code (folder names, table names, API endpoints)
- Excalidraw diagrams có thể simplified (presentation-friendly)

---

## Diagram-to-Spec Mapping

| Diagram | Related Specs |
|---------|---------------|
| `system_context.mmd` | `01_PROJECT_OVERVIEW.md`, `03_SYSTEM_ARCHITECTURE.md` |
| `system_container.mmd` | `03_SYSTEM_ARCHITECTURE.md`, `04_MODULE_SPEC.md` |
| `rag_pipeline.mmd` | `07_RAG_SPEC.md` |
| `ingestion_pipeline.mmd` | `08_OCR_INGESTION_SPEC.md` |
| `erd.mmd` | `05_DATABASE_SPEC.md` |
| `sequence_chat_flow.mmd` | `02_REQUIREMENTS.md` (FR-1), `06_API_SPEC.md` |
| `sequence_ingestion_flow.mmd` | `02_REQUIREMENTS.md` (FR-2), `06_API_SPEC.md` |
| `rag-ingestion-module.html` / `.json` / `.mmd` | `07_RAG_SPEC.md`, `08_OCR_INGESTION_SPEC.md`, `05_DATABASE_SPEC.md` |
| `rag-retrieval-module.html` / `.json` / `.mmd` | `07_RAG_SPEC.md`, `05_DATABASE_SPEC.md`, `06_API_SPEC.md` |
| `rag-llm-generation-module.html` / `.json` / `.mmd` | `07_RAG_SPEC.md`, `06_API_SPEC.md`, `05_DATABASE_SPEC.md` |

---

## Export Guidelines

### For Documentation
- Keep `.mmd` source files in git
- Auto-render trong GitHub README

### For Presentations
- Export Excalidraw → PNG (high resolution)
- Export Mermaid → PNG/SVG nếu cần embed trong slides

### For Reports
- PDF-friendly: export to SVG → embed trong LaTeX/Word

---

## Tools Reference

- **Mermaid:** https://mermaid.js.org/
- **Mermaid Live Editor:** https://mermaid.live/
- **Excalidraw:** https://excalidraw.com/
- **Excalidraw VS Code Extension:** https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor
- **C4 Model:** https://c4model.com/

---

**Created:** 2026-06-10  
**Maintained by:** Development Team
