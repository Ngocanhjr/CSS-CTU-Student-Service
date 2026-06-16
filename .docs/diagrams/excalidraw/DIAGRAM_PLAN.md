# CTU-Service Excalidraw Diagrams Plan

**Purpose:** High-level presentation diagrams cho stakeholders

---

## Recommended Diagrams

### 1. System Architecture Overview
**Type:** Architecture diagram  
**Playbook:** `playbooks/architecture.md`  
**Purpose:** Show high-level system components and data flow

**Components:**
- Student/Admin (users)
- Flutter Frontend (mobile + web)
- Backend API (FastAPI)
- RAG Service (retrieval + generation)
- Data layer (PostgreSQL, Qdrant, Storage)
- OCR Service (ocr-pvl)

**Visual Pattern:** Layered architecture with arrows showing data flow

---

### 2. RAG Pipeline Flow
**Type:** Process flowchart  
**Playbook:** `playbooks/flowchart.md`  
**Purpose:** Show step-by-step RAG query processing

**Steps:**
1. User query input
2. Query normalization
3. Metadata filter
4. Dense retrieval (Qdrant)
5. Sparse retrieval (PostgreSQL)
6. Hybrid fusion (RRF)
7. Parent context expansion
8. LLM prompt construction
9. Answer generation
10. Citation validation
11. Response to user

**Visual Pattern:** Linear flow with branch for dense/sparse retrieval, converging at fusion

---

### 3. Document Ingestion Lifecycle
**Type:** Sequence/timeline diagram  
**Playbook:** `playbooks/sequence-timeline.md`  
**Purpose:** Show document journey from upload to searchable

**Stages:**
1. Upload → Storage
2. OCR (ocr-pvl) → Markdown
3. Human Review → Approved
4. Chunking (LangChain) → Parent-Child chunks
5. Embedding (BGE-M3) → Vectors
6. Indexing (Qdrant) → Searchable
7. Published → RAG retrieval

**Visual Pattern:** Timeline with stage badges, showing stage transitions

---

## Implementation Note

**Excalidraw JSON files require:**
- Manual element placement (x, y coordinates)
- Element IDs, grouping, binding
- Render-verify loop (PNG export → visual QA)
- Typically 500-2000+ lines JSON per diagram

**Recommendation:**
1. Use Mermaid diagrams (already created) for technical documentation
2. Create Excalidraw diagrams manually via https://excalidraw.com/ for presentations
3. Export to PNG/SVG for reports
4. Store .excalidraw source files in git for future edits

**Mermaid vs Excalidraw:**
- **Mermaid:** Text-based, version-control friendly, auto-layout, quick updates
- **Excalidraw:** Hand-drawn style, polished visuals, manual layout, presentation-ready

---

## Quick Start Guide

### Create Excalidraw Diagram Manually

1. Go to https://excalidraw.com/
2. Draw diagram using tools:
   - Rectangle: System components
   - Diamond: Decision points
   - Arrow: Data flow
   - Text: Labels
3. Export:
   - File → Save as... → `.excalidraw` (source)
   - File → Export image → PNG (for docs)
4. Store files:
   - Source: `chatbot/.docs/diagrams/excalidraw/system-architecture.excalidraw`
   - Export: `chatbot/.docs/diagrams/excalidraw/system-architecture.png`

### Tips

- Use consistent colors (refer to `.claude/skills/diagram/references/color-palette.md`)
- Keep text minimal and readable
- Use visual patterns (layers, flows, hierarchies)
- Test with stakeholders before finalizing

---

## Status

✅ **Mermaid diagrams:** 7 diagrams created (text-based, ready to use)  
⚠️ **Excalidraw diagrams:** Plan created, manual creation recommended

**Rationale:** Excalidraw requires manual visual design and render-verify loops. Mermaid diagrams already provide technical documentation. Excalidraw is best created manually for presentation polish.

---

**Created:** 2026-06-10  
**References:** `.claude/skills/diagram/SKILL.md`
