# Documentation Update — 2026-06-10

## Change Summary

**Topic:** Production RAG retrieval filter rule clarification

**Issue:** Previous documentation incorrectly treated `is_latest = true` as a mandatory hard filter for all production RAG retrieval.

**Resolution:** Updated all affected documentation to clarify that `is_latest` is a **ranking preference**, not a hard filter.

---

## Rationale

Older document versions may still be:
- Valid and useful as supplementary context
- Referenced by newer procedures
- Required to fully understand current procedures
- Publicly accessible and approved

Excluding all older versions would remove valuable contextual information that helps students understand the full administrative landscape.

---

## Updated Files

### 1. `AGENTS.md`

**Section:** Publish rule  
**Change:** Removed `is_latest = true` from mandatory indexing conditions. Added note explaining it's a ranking preference.

**Section:** Retrieval rule  
**Change:** Removed `is_latest = true` from hard filter. Added ranking preference note.

### 2. `.docs/RAG_RETRIEVAL.md`

**Section:** Metadata filter  
**Change:** Renamed to "Production RAG hard filter". Removed `is_latest = true` from filter conditions. Added explicit "Ranking and version preference" subsection.

**Section:** Child chunk metadata  
**Change:** Added note clarifying `is_latest` is metadata for ranking, not a hard filter.

### 3. `.docs/CODING_RULES.md`

**Section:** Publish rule  
**Change:** Removed `is_latest = true` from mandatory conditions. Added note about using it as ranking preference.

### 4. `.docs/INGESTION_PIPELINE.md`

**Section:** Indexing and publish rule  
**Change:** Removed `is_latest = true` from indexing eligibility. Added note about ranking preference.

---

## Final Production RAG Filter Rules

### Hard Filter (ALL required)

Documents/chunks can be used for student-facing RAG ONLY when:

```
review_status = "approved"
AND validity_status = "valid"
AND rag_status = "published"
AND confidentiality = "public"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

### Ranking Preference

- **Prefer** `is_latest = true` when multiple versions of the same document exist and may conflict
- **Allow** older documents (`is_latest = false`) if they remain valid, published, public, and serve as supplementary, referenced, or required context
- **Exclude** older documents only when explicitly:
  - Expired (via `expiry_date`)
  - Replaced (via `validity_status = "replaced"`)
  - Unpublished (via `rag_status != "published"`)
  - Invalid (via `validity_status != "valid"`)
  - Not approved (via `review_status != "approved"`)

---

## Validation

✅ All documentation files updated consistently  
✅ No remaining instances of `is_latest = true` as hard filter  
✅ Clear distinction between hard filter and ranking preference  
✅ Rationale documented for future reference  

---

## Next Steps

When implementing the retrieval service (`app/retrieval/`):

1. Apply the 6 hard filter conditions to all Qdrant and PostgreSQL queries
2. Store `is_latest` in Qdrant payload for ranking
3. Use `is_latest` as a tie-breaker or boosting factor in reranking
4. Do NOT exclude chunks solely based on `is_latest = false`
5. Document any conflict resolution logic that uses `is_latest` as preference

---

**Updated by:** Kiro (Assistant)  
**Date:** 2026-06-10  
**Approved by:** [Pending user confirmation]
