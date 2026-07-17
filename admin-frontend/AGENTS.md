# Admin frontend rules

## Project boundary

- This directory is the React/Vite admin interface for document upload, review, ingestion, and management.
- `chatbot-ctu-app` is the separate Flutter student-facing question-answering interface.
- Do not apply the root-level "Flutter only" rule to this admin directory.
- Keep the admin UI light-themed. Use the existing CSS variables instead of component-level color values or inline styles.

## Semantic HTML5

- Use semantic elements when the element describes content meaning: `header`, `nav`, `main`, `aside`, `section`, `article`, `form`, `label`, `button`, `table`, `dl`, and `footer`.
- Use `div` for layout-only groups such as `.row`, `.col`, `.grid`, `.stack`, `.app`, and scroll wrappers when no semantic element describes that group. Do not create anonymous wrapper chains.
- Do not replace every `div` mechanically. Semantic structure and layout `div`s should coexist.
- Keep one visible `h1` per page; descend headings in order without skipping levels.
- Every input has a connected `label`; every action uses `button`; use native form controls before custom widgets.
- Use `dl` for key/value metadata, `table` only for tabular data, and real lists for repeated items.
- Add meaningful text labels, `aria-*` only when native semantics cannot express needed behavior, and avoid clickable non-button elements.
- The React mount element `#root` remains a `div`; application content beneath it must choose semantic elements for meaning and `div` for layout.

### Fieldset rule

- Use `fieldset` only for a real group of related form controls and give it a meaningful `legend`.
- Do not use `fieldset` as a generic card, grid, spacing wrapper, or replacement for every layout `div`.
- A read-only information card should normally be `section.card` with a heading; its internal layout may use `div.row` and `div.col`.

## Structured content

- Keep document metadata as named fields matching backend schemas; never derive identifiers or duplicate YAML fields in the UI.
- Render canonical Markdown and parsed metadata as distinct sections with explicit headings.
- Prefer stable, descriptive text and headings so assistive technology and AI/search indexing tools can identify page purpose and data relationships.
- Keep admin pages `noindex, nofollow, noarchive`; improve machine readability through semantic structure, not public indexing or speculative JSON-LD.

## Validation

Run before handing off UI changes:

```powershell
rtk rg -n '<div|<fieldset|style=\{' src -g '*.jsx'
rtk npm run build
rtk git diff --check
```

The first command is a review list, not a zero-match requirement. Confirm each `div` is layout-only, each `fieldset` groups related controls, and inline styles are justified. Do not add a dependency solely to enforce these rules.
