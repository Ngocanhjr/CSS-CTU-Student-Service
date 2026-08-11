# 03. Schema Request/Response cho RAG Answer

**Last Updated:** 2026-07-13

```text
Tao app/schemas/rag.py (CHUA TON TAI)
Dinh nghia RagAnswerRequest, Citation, RagAnswerResponse
Dung cho POST /api/v1/rag/answer theo 06_API_SPEC.md
Khong them field ngoai spec, khong them auth/JWT
```

File này chỉ làm schema Pydantic cho request/response của endpoint `POST /api/v1/rag/answer`. Router thật (`app/api/rag.py`), retrieval (`app/retrieval/retriever.py`) và answer chain (`app/llm/rag_chain.py`) là phần việc của các guide khác (16, 18) và guide router riêng, **không** làm trong file này.

---

## 1. Trạng Thái Hiện Tại (đã đọc code, không suy đoán)

Đã xác nhận bằng cách đọc trực tiếp:

```text
app/schemas/rag.py         -> CHUA TON TAI, phai tao moi.
app/schemas/base.py        -> co StrictSchema(BaseModel), model_config = ConfigDict(extra="forbid").
app/schemas/assets.py      -> AssetMetadata/DocumentAssetRelation ke thua StrictSchema, dung Field(min_length=1)
                               cho cac khoa string, dung default an toan (vi du title: str = "").
app/schemas/documents.py   -> DocumentBaseMetadata/DocumentVersionMetadata ke thua StrictSchema tuong tu.
app/api/rag.py             -> CHUA TON TAI.
app/api/health.py          -> RONG, chua co route nao.
app/api/__init__.py        -> ton tai nhung rong.
```

Mọi schema khác trong project đều kế thừa `StrictSchema` (không phải `BaseModel` trần), nên `app/schemas/rag.py` phải theo đúng convention này: `extra="forbid"`, dùng `Field(...)` khi cần ràng buộc, comment tiếng Việt giải thích mục đích field giống style `documents.py`/`assets.py`.

Spec gốc (`.docs/spec/ctu-service/06_API_SPEC.md`) chỉ định nghĩa 4 field ở response cấp cao (`answer`, `citations`, `related_assets`, `trace_id`) và 3 field ở request (`query`, `user_role`, `prefer_current`). Cấu trúc chi tiết của từng `Citation` không có trong spec gốc — nhiệm vụ này định nghĩa `Citation` theo yêu cầu cụ thể được giao (xem mục 4), dựa trên các field đã tồn tại thật trong DB/`RetrievalResult` để không bịa field mới.

---

## 2. File Cần Tạo/Sửa

```text
chatbot/backend/app/schemas/rag.py         (tao moi)
chatbot/backend/test/schemas/rag_test.py   (tao moi)
```

Thư mục `chatbot/backend/test/schemas/` đã tồn tại (có `documents_test.py`, `assets_test.py`, `chunks_test.py`), chỉ cần thêm file test mới, không cần tạo thư mục.

Không sửa `app/schemas/base.py`, không sửa `app/schemas/documents.py`, không sửa `app/schemas/enums.py`.

---

## 3. RagAnswerRequest

Theo đúng `06_API_SPEC.md`:

```json
{
  "query": "Em muốn xin bảng điểm thì cần gì?",
  "user_role": "student",
  "prefer_current": true
}
```

`user_role` trong spec là string tự do (`"student"`), **không** phải enum đã có trong `app/schemas/enums.py` (enum `Audience` dùng giá trị tiếng Việt `sinh_vien/can_bo/giang_vien/cong_khai`, khác domain với `user_role` của request RAG answer). Không ép `user_role` vào `Audience` vì hai khái niệm khác nhau: `Audience` mô tả đối tượng tài liệu hướng tới, còn `user_role` mô tả người đang hỏi. Giữ `user_role: str` tự do, có validate không rỗng khi được truyền, mặc định `"student"` theo spec.

```python
class RagAnswerRequest(StrictSchema):
    """
    Request cho POST /api/v1/rag/answer.

    - query: cau hoi tho cua nguoi dung, bat buoc, khong duoc rong.
    - user_role: vai tro nguoi hoi, mac dinh "student" theo spec.
      Khong dung enum Audience vi day la field khac muc dich.
    - prefer_current: True neu muon uu tien tai lieu dang hieu luc/is_latest
      khi retrieval co nhieu phien ban trung document_key.
    """

    query: str = Field(min_length=1)
    user_role: str = Field(default="student", min_length=1)
    prefer_current: bool = True

    @field_validator("query", "user_role")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field khong duoc chi chua khoang trang")
        return stripped
```

Lưu ý:

```text
Field(min_length=1) chi chan chuoi rong "", khong chan chuoi toan khoang trang "   ".
Vi vay them field_validator strip_and_validate de dam bao query/user_role
khong bi rong sau khi strip, giong pattern DocumentBaseMetadata.clean_string_list
trong app/schemas/documents.py.
```

---

## 4. Citation

`Citation` mô tả một trích dẫn nguồn trong câu trả lời. Yêu cầu cụ thể cho guide này: `document_id`, `version_id`, `title`, `page_start`, `page_end`, `section_title`, `source_file`, `quote_snippet`.

Đối chiếu với DB thật (`app/databases/models/documents.py`, `app/databases/models/chunks.py`) và `RetrievalResult` (Guide 16, `app/retrieval/retriever.py` — hiện vẫn RỖNG, chỉ có thiết kế trong guide):

```text
document_id     -> Document.id (int, PK thuc trong bang documents).
                    KHONG dung document_key o day vi spec dung "_id" (khac
                    convention "_key" dang dung cho document_key/version_key
                    o cac schema khac). Ham hydrate/repository phia router
                    phai resolve document_key -> Document.id truoc khi dung.
version_id       -> DocumentVersion.id (int, PK thuc trong bang document_versions).
                    Cung tu resolve tu version_key luc hydrate, khong lay
                    truc tiep tu Qdrant payload (Qdrant khong co id numeric nay).
title            -> DocumentVersion.title hoac Document.title (da co field
                    title kieu String trong ca hai bang).
page_start       -> DocumentChunk.page_start (Integer, nullable).
page_end         -> DocumentChunk.page_end (Integer, nullable).
section_title    -> DocumentChunk.section_title (String(500), default "").
                    Day la field co thuc trong bang document_chunks, khong
                    phai bia moi.
source_file      -> Khong co cot rieng ten "source_file" trong DB. Gia tri
                    nay lay tu RetrievalResult.source_file (Guide 16 thiet
                    ke), thuong duoc build tu DocumentVersion.canonical_markdown_path
                    hoac source_path luc hydrate. O muc schema nay chi khai
                    bao field str, khong tu bia them cot DB moi.
quote_snippet    -> Khong co cot DB rieng. La doan trich ngan tu
                    DocumentChunk.content, duoc cat/format luc build citation
                    trong answer chain (Guide 18), khong luu lai trong DB.
```

```python
class Citation(StrictSchema):
    """
    Citation mo ta mot trich dan nguon dung de tra loi cau hoi RAG.

    - document_id: Document.id (PK int trong bang documents).
    - version_id: DocumentVersion.id (PK int trong bang document_versions).
    - title: tieu de tai lieu/phien ban dung hien thi cho nguoi dung.
    - page_start/page_end: khoang trang nguon, lay tu DocumentChunk.
      Co the None neu chunk khong co thong tin trang (vi du tai lieu it trang).
    - section_title: DocumentChunk.section_title, co the rong "".
    - source_file: ten/duong dan file nguon hien thi cho nguoi dung, build tu
      DocumentVersion.canonical_markdown_path/source_path luc hydrate.
    - quote_snippet: doan trich ngan lay tu DocumentChunk.content, khong luu DB.
    """

    document_id: int = Field(gt=0)
    version_id: int = Field(gt=0)
    title: str = ""
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str = ""
    source_file: str = ""
    quote_snippet: str = ""

    @model_validator(mode="after")
    def validate_page_range(self) -> "Citation":
        if self.page_start is not None and self.page_end is not None:
            if self.page_start > self.page_end:
                raise ValueError("page_start phai <= page_end")
        return self
```

Rule `page_start <= page_end` giống hệt rule đã có ở `Chunk.validate_chunk_contract()` trong `app/schemas/chunks.py` — dùng lại cách viết cho nhất quán, không phát minh rule mới.

---

## 5. RagAnswerResponse

Theo `06_API_SPEC.md`:

```json
{
  "answer": "...",
  "citations": [],
  "related_assets": [],
  "trace_id": "..."
}
```

`related_assets` trong spec gốc chỉ là `[]`, chưa có contract chi tiết field bên trong ở spec hiện tại. Bảng liên quan đã có thật trong DB là `document_assets` + `assets` (`app/databases/models/assets.py`, đã có `AssetMetadata`/`DocumentAssetRelation` trong `app/schemas/assets.py`). Vì guide này chỉ được giao đúng 4 field cấp cao theo spec, và không được bịa field mới ngoài spec, `related_assets` khai báo là `list[AssetMetadata]` — tái dùng schema `AssetMetadata` đã có sẵn (không tạo schema con mới), thay vì `list[Any]` mơ hồ. Nếu sau này BE quyết định trả về ít field hơn `AssetMetadata` đầy đủ, sẽ cần một guide riêng chỉnh lại, không phải phạm vi file này.

```python
class RagAnswerResponse(StrictSchema):
    """
    Response cho POST /api/v1/rag/answer.

    - answer: cau tra loi cuoi cung tra ve cho nguoi dung.
    - citations: danh sach Citation dung de sinh answer, co the rong khi
      khong tim thay nguon phu hop (xem Guide 18, RagAnswer.answer khi
      "chua tim thay thong tin trong tai lieu hien co").
    - related_assets: tai lieu/asset lien quan (form, template, ...), tai
      dung AssetMetadata da co trong app/schemas/assets.py.
    - trace_id: dinh danh duy nhat cho 1 lan goi, dung de tra cuu log/debug.
    """

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    related_assets: list[AssetMetadata] = Field(default_factory=list)
    trace_id: str = Field(min_length=1)
```

---

## 6. File Hoàn Chỉnh `app/schemas/rag.py`

```python
"""
Schema request/response cho endpoint POST /api/v1/rag/answer.
Theo .docs/spec/ctu-service/06_API_SPEC.md.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from app.schemas.assets import AssetMetadata
from app.schemas.base import StrictSchema


class RagAnswerRequest(StrictSchema):
    """
    Request cho POST /api/v1/rag/answer.

    - query: cau hoi tho cua nguoi dung, bat buoc, khong duoc rong.
    - user_role: vai tro nguoi hoi, mac dinh "student" theo spec.
      Khong dung enum Audience vi day la field khac muc dich.
    - prefer_current: True neu muon uu tien tai lieu dang hieu luc/is_latest
      khi retrieval co nhieu phien ban trung document_key.
    """

    query: str = Field(min_length=1)
    user_role: str = Field(default="student", min_length=1)
    prefer_current: bool = True

    @field_validator("query", "user_role")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field khong duoc chi chua khoang trang")
        return stripped


class Citation(StrictSchema):
    """
    Citation mo ta mot trich dan nguon dung de tra loi cau hoi RAG.

    - document_id: Document.id (PK int trong bang documents).
    - version_id: DocumentVersion.id (PK int trong bang document_versions).
    - title: tieu de tai lieu/phien ban dung hien thi cho nguoi dung.
    - page_start/page_end: khoang trang nguon, lay tu DocumentChunk.
    - section_title: DocumentChunk.section_title, co the rong "".
    - source_file: ten/duong dan file nguon hien thi cho nguoi dung.
    - quote_snippet: doan trich ngan lay tu DocumentChunk.content.
    """

    document_id: int = Field(gt=0)
    version_id: int = Field(gt=0)
    title: str = ""
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str = ""
    source_file: str = ""
    quote_snippet: str = ""

    @model_validator(mode="after")
    def validate_page_range(self) -> "Citation":
        if self.page_start is not None and self.page_end is not None:
            if self.page_start > self.page_end:
                raise ValueError("page_start phai <= page_end")
        return self


class RagAnswerResponse(StrictSchema):
    """
    Response cho POST /api/v1/rag/answer.

    - answer: cau tra loi cuoi cung tra ve cho nguoi dung.
    - citations: danh sach Citation dung de sinh answer, co the rong.
    - related_assets: tai lieu/asset lien quan, tai dung AssetMetadata.
    - trace_id: dinh danh duy nhat cho 1 lan goi.
    """

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    related_assets: list[AssetMetadata] = Field(default_factory=list)
    trace_id: str = Field(min_length=1)
```

---

## 7. Test/Kiểm Thử

File: `chatbot/backend/test/schemas/rag_test.py`

```python
import pytest
from pydantic import ValidationError

from app.schemas.rag import Citation, RagAnswerRequest, RagAnswerResponse


def test_rag_answer_request_uses_default_role_and_prefer_current():
    request = RagAnswerRequest(query="Em muon xin bang diem thi can gi?")

    assert request.user_role == "student"
    assert request.prefer_current is True


def test_rag_answer_request_rejects_blank_query():
    with pytest.raises(ValidationError):
        RagAnswerRequest(query="   ")


def test_rag_answer_request_rejects_unknown_field():
    with pytest.raises(ValidationError):
        RagAnswerRequest(query="cau hoi", unknown_field=True)


def test_citation_accepts_valid_page_range():
    citation = Citation(
        document_id=1,
        version_id=1,
        title="Quy dinh cong tac hoc vu",
        page_start=2,
        page_end=3,
        section_title="Dieu 5",
        source_file="qd-3266.md",
        quote_snippet="Sinh vien can nop don theo mau...",
    )

    assert citation.page_start == 2
    assert citation.page_end == 3


def test_citation_rejects_page_start_greater_than_page_end():
    with pytest.raises(ValidationError):
        Citation(document_id=1, version_id=1, page_start=5, page_end=2)


def test_citation_rejects_non_positive_ids():
    with pytest.raises(ValidationError):
        Citation(document_id=0, version_id=1)


def test_rag_answer_response_allows_empty_citations_and_assets():
    response = RagAnswerResponse(
        answer="Toi chua tim thay thong tin trong tai lieu hien co.",
        trace_id="trace-001",
    )

    assert response.citations == []
    assert response.related_assets == []


def test_rag_answer_response_requires_trace_id():
    with pytest.raises(ValidationError):
        RagAnswerResponse(answer="noi dung")
```

Lệnh chạy test:

```powershell
cd E:\RHNA\1Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/schemas/rag_test.py
```

### Kiểm thử thủ công qua curl (sau khi có router thật `app/api/rag.py`)

Guide này chỉ định nghĩa schema, chưa có router, nên curl dưới đây chỉ hợp lệ sau khi router `POST /api/v1/rag/answer` được implement (guide router riêng, không thuộc phạm vi file này):

```bash
curl -X POST http://localhost:8000/api/v1/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Em muon xin bang diem thi can gi?",
    "user_role": "student",
    "prefer_current": true
  }'
```

Response mong đợi có dạng đúng `RagAnswerResponse`:

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

---

## 8. Không Làm Trong File Này

```text
Khong tao app/api/rag.py (router thuc te goi answer_question()).
Khong sua app/retrieval/retriever.py hay app/llm/rag_chain.py (dang rong,
thuoc guide 16/18).
Khong them auth/JWT.
Khong them field ngoai 4 field cap cao cua RagAnswerResponse trong spec goc.
Khong tao bang moi hay sua 9 bang DB hien co.
```

---

## 9. Done Khi

- [ ] `app/schemas/rag.py` tồn tại, export `RagAnswerRequest`, `Citation`, `RagAnswerResponse`.
- [ ] Cả 3 class đều kế thừa `StrictSchema` (`extra="forbid"`), không dùng `BaseModel` trần.
- [ ] `RagAnswerRequest.query` bắt buộc, không rỗng sau khi strip.
- [ ] `RagAnswerRequest.user_role` mặc định `"student"`, không ép vào enum `Audience`.
- [ ] `RagAnswerRequest.prefer_current` mặc định `True`.
- [ ] `Citation` có đủ 8 field theo yêu cầu: `document_id`, `version_id`, `title`, `page_start`, `page_end`, `section_title`, `source_file`, `quote_snippet`.
- [ ] `Citation` validate `page_start <= page_end` khi cả hai có giá trị, giống rule ở `Chunk`.
- [ ] `RagAnswerResponse` có đủ 4 field: `answer`, `citations`, `related_assets`, `trace_id`; `related_assets` tái dùng `AssetMetadata`.
- [ ] `citations`/`related_assets` có default là list rỗng, không bắt buộc phải truyền khi không có kết quả.
- [ ] `test/schemas/rag_test.py` chạy pass với `pytest`.
- [ ] Không có field nào trong 3 class vượt ra ngoài spec `06_API_SPEC.md` + yêu cầu `Citation` được giao.

---

## 10. Phụ Thuộc / Thứ Tự Làm Trước

```text
Khong phu thuoc code moi nao khac de viet duoc file schema nay, vi
app/schemas/base.py va app/schemas/assets.py da co san va da doc truoc
khi viet guide nay.

Nhung de RagAnswerResponse duoc dung thuc te (khong chi ton tai schema
suong), can lam sau:
- Guide 16 (16_PART_I_RETRIEVAL_GUIDE.md): can RetrievalResult that de
  co page_start/page_end/section_title/source_file dua vao Citation.
- Guide 18 (18_PART_K_RAG_ANSWER_CHAIN_GUIDE.md): can answer_question()
  that de tao answer/citations/trace_id truoc khi router goi
  RagAnswerResponse(...).
- Mot guide router rieng (chua co trong bo 20 file, can bo sung sau) de
  tao app/api/rag.py, include vao app/main.py (hien dang rong).
```
