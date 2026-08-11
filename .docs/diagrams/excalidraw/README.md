# Excalidraw Diagrams

Thư mục này chứa các file source `.excalidraw` cho presentation diagrams.

---

## Mục Đích

Excalidraw diagrams dùng cho:
- **Presentations:** Slides cho stakeholders, demos
- **High-level overview:** Conceptual architecture, không quá technical
- **Polished visuals:** Clean, professional-looking diagrams cho reports
- **Manual refinement:** Hand-drawn style với precise control

---

## Cách Sử Dụng

### Tạo Diagram Mới

1. Mở [Excalidraw](https://excalidraw.com/)
2. Vẽ diagram
3. File → Save as → `<diagram_name>.excalidraw`
4. Lưu vào thư mục này
5. Commit source file vào git

### Edit Diagram Existing

1. Mở file `.excalidraw` trong [Excalidraw](https://excalidraw.com/)
   - Drag & drop file vào browser
   - Hoặc File → Open
2. Edit diagram
3. Save lại với tên cũ
4. Commit changes

### Export for Presentation

1. File → Export image
2. Chọn PNG (high resolution) hoặc SVG
3. Lưu exported file ra ngoài git (trong `exports/` hoặc presentation folder)
4. **Không commit PNG/SVG files** (chỉ commit `.excalidraw` sources)

---

## Suggested Diagrams (Not Yet Created)

Các diagrams sau có thể được vẽ bằng Excalidraw khi cần present:

1. **`system_context.excalidraw`**
   - High-level: Users ↔ CTU-Service ↔ External systems
   - Reference: `../mermaid/system_context.mmd`

2. **`system_container.excalidraw`**
   - Components: Flutter, Backend, PostgreSQL, Qdrant
   - Reference: `../mermaid/system_container.mmd`

3. **`rag_pipeline.excalidraw`**
   - Visual flow: Query → Retrieval → LLM → Answer
   - Reference: `../mermaid/rag_pipeline.mmd`

4. **`ingestion_pipeline.excalidraw`**
   - Visual flow: Upload → OCR → Review → Index
   - Reference: `../mermaid/ingestion_pipeline.mmd`

5. **`erd.excalidraw`**
   - Simplified ERD cho presentation (không cần all fields)
   - Reference: `../mermaid/erd.mmd`

6. **`chat_flow.excalidraw`**
   - User journey: Student asks → receives answer với citations
   - Reference: `../mermaid/sequence_chat_flow.mmd`

---

## Diagram Skill Reference

Khi vẽ diagrams, tham khảo:

```
CTU-SERVICE/.claude/skills/diagram/SKILL.md
```

Diagram skill provides:
- Methodology: ARGUE visually (shape = meaning)
- Color palette: Brand colors và semantic colors
- Playbooks: Architecture, flowchart, sequence, hierarchy
- Quality checklist

---

## Tips for Good Excalidraw Diagrams

### Visual Hierarchy
- Use size và color để show importance
- Main components lớn hơn, bold hơn
- Supporting components nhỏ hơn, subtle hơn

### Layout
- Left-to-right hoặc top-to-bottom flow
- Group related components
- Align components neatly

### Color Coding
- Consistent color scheme (e.g., blue = backend, green = database, orange = external)
- Use color palette từ diagram skill

### Labels
- Clear, concise labels
- Vietnamese cho internal docs
- English cho external presentations (nếu cần)

### Arrows
- Show data flow direction clearly
- Label arrows với action/data type

---

## Mermaid vs Excalidraw

| Aspect | Mermaid | Excalidraw |
|--------|---------|------------|
| **Purpose** | Technical docs | Presentations |
| **Style** | Text-based, structured | Hand-drawn, flexible |
| **Maintainability** | Easy (code) | Medium (visual) |
| **Detail level** | High | Medium-low |
| **Version control** | Excellent (text diff) | OK (JSON diff) |
| **Best for** | Specs, GitHub docs | Slides, stakeholder meetings |

**Recommendation:** Maintain both.
- Update Mermaid first (sync với specs)
- Update Excalidraw khi cần present

---

## Export Folder (Not in Git)

Suggested local structure (không commit vào git):

```
.docs/diagrams/excalidraw/
├── README.md               # This file (committed)
├── *.excalidraw            # Source files (committed)
└── exports/                # Exported PNG/SVG (gitignored)
    ├── system_context.png
    ├── rag_pipeline.png
    └── ...
```

Add to `.gitignore`:
```
.docs/diagrams/excalidraw/exports/
```

---

## Tools

- **Excalidraw Web:** https://excalidraw.com/
- **Excalidraw VS Code Extension:** https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor
- **Excalidraw Desktop:** https://github.com/excalidraw/excalidraw-desktop

---

**Created:** 2026-06-10  
**Status:** Empty — Diagrams will be created manually khi cần present
