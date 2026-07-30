# Task 01: Reference Data APIs

## Mục tiêu
Tạo API lấy dữ liệu tham chiếu (document types, departments) từ database thay vì hardcode ở frontend.

## Endpoints cần implement

### 1. GET /api/v1/reference/document-types
```json
Response 200:
[
  { "id": 1, "code": "noi_quy", "name": "Nội quy", "is_active": true },
  { "id": 2, "code": "quy_trinh", "name": "Quy trình", "is_active": true }
]
```

### 2. GET /api/v1/reference/departments
```json
Response 200:
[
  { "id": 1, "code": "PDT", "name": "Phòng Đào tạo", "is_active": true },
  { "id": 2, "code": "PCTSV", "name": "Phòng Công tác Sinh viên", "is_active": true }
]
```

---

## Checklist

### Backend

- [ ] **Tạo schema** `backend/app/schemas/reference.py`
```python
from app.schemas.base import StrictSchema

class DocumentTypeResponse(StrictSchema):
    id: int
    code: str
    name: str
    is_active: bool

class DepartmentResponse(StrictSchema):
    id: int
    code: str
    name: str
    is_active: bool
```

- [ ] **Tạo router** `backend/app/api/reference.py`
```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.databases.models.documents import DocumentType, Department
from app.schemas.reference import DocumentTypeResponse, DepartmentResponse

router = APIRouter(prefix="/reference", tags=["reference"])

@router.get("/document-types", response_model=list[DocumentTypeResponse])
async def list_document_types(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(DocumentType).where(DocumentType.is_active == True)
    )
    return result.scalars().all()

@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Department).where(Department.is_active == True)
    )
    return result.scalars().all()
```

- [ ] **Đăng ký router** trong `backend/app/main.py`
```python
from app.api.reference import router as reference_router

app.include_router(reference_router, prefix="/api/v1")
```

### Frontend

- [ ] **Thêm API functions** trong `admin-frontend/src/api/client.js`
```javascript
export const api = {
  // ... existing functions
  
  getDocumentTypes() {
    return request('/api/v1/reference/document-types')
  },

  getDepartments() {
    return request('/api/v1/reference/departments')
  },
}
```

- [ ] **Tạo hook/context** để cache reference data (optional)
```javascript
// admin-frontend/src/hooks/useReferenceData.js
import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export function useReferenceData() {
  const [documentTypes, setDocumentTypes] = useState([])
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getDocumentTypes(),
      api.getDepartments(),
    ]).then(([types, depts]) => {
      setDocumentTypes(types)
      setDepartments(depts)
      setLoading(false)
    })
  }, [])

  return { documentTypes, departments, loading }
}
```

- [ ] **Update components** sử dụng reference data:
  - `DocumentsListPage.jsx` - filters
  - `DocumentEditPage.jsx` - dropdowns

---

## Database Tables (đã có sẵn)

Kiểm tra models trong `backend/app/databases/models/documents.py`:
- `DocumentType` - id, code, name, is_active
- `Department` - id, code, name, is_active

Data đã được seed trong migration `7b0c2fd5a1e4_seed_reference_data.py`.

---

## Test

```bash
# Test backend
curl http://localhost:8000/api/v1/reference/document-types
curl http://localhost:8000/api/v1/reference/departments

# Verify response format
curl -s http://localhost:8000/api/v1/reference/document-types | jq '.[0] | keys'
# Expected: ["code", "id", "is_active", "name"]
```

---

## Definition of Done

- [ ] 2 endpoints trả về đúng format JSON
- [ ] Frontend gọi API thay vì dùng hardcoded data
- [ ] Filters trong DocumentsListPage hoạt động với data từ API
- [ ] Dropdowns trong DocumentEditPage hiển thị đúng options
