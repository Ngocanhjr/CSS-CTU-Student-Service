# 10. Bảo Mật và Document Governance

## Authentication

### Student Authentication
_[Username/password hoặc CTU SSO (future)]_

### Admin Authentication
_[Username/password với role check]_

### Session Management
_[JWT tokens, refresh tokens, expiry]_

---

## Authorization (RBAC)

### Roles
- **student:** _[Access chat, view public documents, download public assets]_
- **admin:** _[Access admin dashboard, upload, review, approve, publish]_
- **reviewer:** _[Review OCR output, approve/reject]_ (future)

### Permission Matrix

| Operation | Student | Admin | Reviewer |
|-----------|---------|-------|----------|
| Ask questions | ✅ | ✅ | ✅ |
| View citations | ✅ | ✅ | ✅ |
| Download public assets | ✅ | ✅ | ✅ |
| Upload documents | ❌ | ✅ | ❌ |
| Review OCR | ❌ | ✅ | ✅ |
| Approve documents | ❌ | ✅ | ✅ |
| Publish to RAG | ❌ | ✅ | ❌ |
| View internal docs | ❌ | ✅ | ✅ |

---

## Document Governance

### Confidentiality Levels
- **public:** _[Hiển thị cho students]_
- **internal:** _[Chỉ admin/staff xem được]_
- **confidential:** _[Restricted access]_

### Production RAG Hard Filter
```
review_status = "approved"
AND validity_status = "valid"
AND rag_status = "published"
AND confidentiality = "public"
AND effective_date <= today
AND (expiry_date IS NULL OR expiry_date >= today)
```

**Note:** `is_latest` không phải hard filter, chỉ dùng cho ranking preference.

---

## Version Governance

### Version Management Rules
- Mỗi document có thể có nhiều versions
- `is_latest = true` chỉ mark version mới nhất
- Old versions vẫn có thể valid và retrieve được (nếu pass hard filter)
- Admin phải explicit mark old version `validity_status = "replaced"` hoặc set `expiry_date` để deactivate

### Replacement Flow
1. Upload new version
2. Set `replaces_version_id` → old version ID
3. Set new version `is_latest = true`
4. Old version `is_latest = false`
5. Optional: set old version `validity_status = "replaced"` hoặc `expiry_date`

---

## Review và Publish Workflow

### Review States
- `not_reviewed` → Document mới upload, chưa review
- `reviewing` → Đang review
- `need_fix` → Cần sửa lỗi
- `approved` → Đã approve, ready to publish
- `rejected` → Rejected, không publish

### Publish States
- `not_indexed` → Chưa chunk/embed
- `chunked` → Đã chunk
- `embedded` → Đã embed
- `indexed` → Đã index vào Qdrant
- `published` → Active trong production RAG
- `deactivated` → Removed from production RAG
- `failed` → Indexing failed

### Approval Rules
- Chỉ `review_status = "approved"` mới được index
- Admin không thể bypass validation rules
- Backend enforce tất cả rules, frontend chỉ UI check

---

## Audit Logging

### Logged Actions
- Upload document
- Approve/reject document
- Publish/unpublish to RAG
- Delete document
- Metadata changes
- User login/logout

### Log Format
```json
{
  "timestamp": "2026-06-10T10:00:00Z",
  "user_id": "admin01",
  "action": "approve_document",
  "resource_type": "document_version",
  "resource_id": "doc-v-001",
  "details": {"previous_status": "reviewing", "new_status": "approved"},
  "ip_address": "10.0.0.1"
}
```

---

## Secrets Management

### Environment Variables (.env)
```
DATABASE_URL=postgresql://...
QDRANT_HOST=localhost
QDRANT_API_KEY=***
LLM_API_KEY=***
JWT_SECRET=***
```

### Security Rules
- Never commit secrets to git
- Use `.env` files locally
- Use secret managers in production (e.g., AWS Secrets Manager)

---

## Input Validation

### User Query Validation
_[Max length, sanitize special characters, no SQL injection]_

### File Upload Validation
_[File type whitelist, max size, virus scan]_

### Metadata Validation
_[Required fields, date logic, enum values]_

---

## Citation Integrity

### Citation Rules
- Citations cannot be modified by frontend
- Backend validate citations match retrieved chunks
- Citations must be traceable to source documents

---

## Data Backup

### PostgreSQL Backup
_[Daily automated backups, retention policy]_

### Qdrant Backup
_[Snapshots, disaster recovery plan]_

### Document Storage Backup
_[File storage backups]_

---

## Production Safety Rules

### Pre-Production Checklist
- [ ] All documents reviewed and approved
- [ ] Hard filter applied in retrieval code
- [ ] No confidential documents in student RAG
- [ ] Citations validated
- [ ] Secrets in .env not committed

---

**Status:** Skeleton — Cần điền chi tiết RBAC implementation và audit specs  
**Priority:** P2
