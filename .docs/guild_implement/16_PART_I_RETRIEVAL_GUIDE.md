# 16. Part I - Hướng Dẫn Implement Retrieval Tối Thiểu

**Last Updated:** 2026-06-20

File này tách chi tiết từ guide 07, phần I.

Mục tiêu:

```text
Nhan query
retrieval qua LangChain Qdrant retriever
van ap dung filter student
lay full content/citation
tra ve retrieval results
```

Guide này chưa làm LLM answer generation.

---

## 1. File Cần Sửa/Tạo

```text
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/test/retrieval/test_retriever.py
```

Phụ thuộc:

```text
app.embedding.embedder
app.vectorstore.repository
app.databases.models
langchain-qdrant
langchain-core
```

Đã chốt RAG pipeline đi theo LangChain:

```text
Embedding: LangChain NVIDIAEmbeddings
Vector retrieval: LangChain QdrantVectorStore/retriever
Hydration/citation/status: project code rieng
```

Lý do vẫn cần project code:

```text
Khong tin Qdrant payload lam canonical content.
Content/citation cuoi cung lay tu PostgreSQL va payload trace fields.
```

---

## 2. Result Model

File:

```text
chatbot/backend/app/retrieval/retriever.py
```

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalResult:
    chunk_key: str
    score: float
    content: str
    title: str
    page_start: int | None
    page_end: int | None
    source_file: str
    source_url: str
    citation: str
```

---

## 3. Citation Helper

```python
def build_citation(
    *,
    source_file: str,
    page_start: int | None,
    page_end: int | None,
    heading_path: list[str] | None = None,
) -> str:
    if page_start and page_end:
        if page_start == page_end:
            return f"{source_file}, trang {page_start}"
        return f"{source_file}, trang {page_start}-{page_end}"

    if heading_path:
        return f"{source_file}, muc {heading_path[-1]}"

    return source_file
```

---

## 4. Build LangChain Retriever

File:

```text
chatbot/backend/app/retrieval/retriever.py
```

Suggested pattern:

```python
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore

from app.embedding.embedder import TextEmbedder
from app.vectorstore.repository import DEFAULT_COLLECTION, build_student_filter


DEFAULT_TOP_K = 5


def build_langchain_qdrant_retriever(
    *,
    qdrant_client: QdrantClient,
    embedder: TextEmbedder,
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = DEFAULT_TOP_K,
    audience: str = "student",
):
    vectorstore = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=embedder,
    )

    search_kwargs = {"k": top_k}
    if audience == "student":
        search_kwargs["filter"] = build_student_filter()

    return vectorstore.as_retriever(search_kwargs=search_kwargs)
```

`top_k` trong caller production lấy từ `get_settings().retrieval.top_k` (default `5` trong settings model). Không dùng fallback bằng `or`.

Lưu ý:

```text
TextEmbedder can tuong thich LangChain Embeddings interface.
Neu TextEmbedder wrapper rieng khong du interface, tao adapter nho co embed_documents() va embed_query().
```

---

## 5. Query Clarification / Context Completion

Không nên embed/search ngay mọi query người dùng nhập vào.

Trước clarification, nên chặn greeting/smalltalk:

```text
hi
hello
chào
xin chào
alo
```

Những query này không cần retrieval. Trả lời trực tiếp và hỏi user muốn hỏi về nội dung nào.

Một số query quá ngắn hoặc thiếu đối tượng, ví dụ:

```text
điều kiện là gì
hồ sơ gồm gì
nộp ở đâu
cần giấy gì
```

Những query này chỉ có nghĩa khi biết người dùng đang hỏi về thủ tục/tài liệu nào.

Rule:

```text
Neu query la greeting/smalltalk -> tra loi truc tiep, khong retrieval.
Neu query du ro -> retrieval binh thuong.
Neu query thieu object va khong co context -> hoi lai nguoi dung.
Neu UI co current_document_key/current_version_key -> bo sung filter theo document/version.
Neu chat history vua nhac object ro rang -> rewrite query bang object do roi retrieval.
```

Bảng quyết định:

| Trường hợp | Xử lý |
|---|---|
| `hi` / `xin chào` | Trả greeting response, không search |
| `điều kiện xin giấy khai sinh là gì` | Retrieval bình thường |
| `điều kiện là gì` và không có context | Trả clarification question |
| `điều kiện là gì` và UI đang xem document `xin-giay-khai-sinh` | Search với `document_key=xin-giay-khai-sinh` |
| `điều kiện là gì` sau câu trước vừa nói `xin giấy khai sinh` | Rewrite thành `điều kiện xin giấy khai sinh là gì` |

Model đề xuất:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalContext:
    current_document_key: str | None = None
    current_version_key: str | None = None
    recent_topic: str | None = None


@dataclass(frozen=True)
class QueryDecision:
    should_search: bool
    query: str
    clarification_question: str | None = None
    document_key: str | None = None
    version_key: str | None = None
```

Function:

```python
def is_greeting_or_smalltalk(query: str) -> bool:
    normalized = query.strip().lower()
    return normalized in {"hi", "hello", "chào", "xin chào", "alo"}


AMBIGUOUS_PATTERNS = [
    "điều kiện",
    "hồ sơ",
    "nộp ở đâu",
    "cần gì",
    "cần giấy gì",
]


def complete_or_clarify_query(
    query: str,
    *,
    context: RetrievalContext | None = None,
) -> QueryDecision:
    normalized = query.strip()
    if not normalized:
        return QueryDecision(should_search=False, query="")

    if is_greeting_or_smalltalk(normalized):
        return QueryDecision(
            should_search=False,
            query=normalized,
            clarification_question=(
                "Chào bạn, mình là trợ lý hỗ trợ tra cứu thông tin sinh viên CTU. "
                "Bạn muốn hỏi về thủ tục, quy định, học bổng, ký túc xá hay nội dung nào?"
            ),
        )

    context = context or RetrievalContext()
    is_ambiguous = any(pattern in normalized.lower() for pattern in AMBIGUOUS_PATTERNS)
    has_context = bool(
        context.current_document_key
        or context.current_version_key
        or context.recent_topic
    )

    if is_ambiguous and not has_context:
        return QueryDecision(
            should_search=False,
            query=normalized,
            clarification_question=(
                "Bạn muốn hỏi điều kiện/hồ sơ của thủ tục hoặc nội dung nào?"
            ),
        )

    if is_ambiguous and context.recent_topic:
        normalized = f"{normalized} cho {context.recent_topic}"

    return QueryDecision(
        should_search=True,
        query=normalized,
        document_key=context.current_document_key,
        version_key=context.current_version_key,
    )
```

Lưu ý:

```text
Day la rule toi thieu, khong phai LLM answer generation.
Clarification question la output hop le cua retrieval layer/API orchestration.
Neu co current_document_key/current_version_key, truyen xuong Qdrant metadata filter.
Neu rewrite bang chat history, phai log query goc va query da rewrite de debug.
```

Ví dụ:

```text
Input: "hi"
Output: should_search=False, clarification_question="Chào bạn..."

Input: "điều kiện là gì"
Context: none
Output: should_search=False, clarification_question="Bạn muốn hỏi điều kiện/hồ sơ của thủ tục hoặc nội dung nào?"

Input: "điều kiện là gì"
Context: current_document_key="xin-giay-khai-sinh"
Output: should_search=True, query="điều kiện là gì", document_key="xin-giay-khai-sinh"

Input: "điều kiện là gì"
Context: recent_topic="xin giấy khai sinh"
Output: should_search=True, query="điều kiện là gì cho xin giấy khai sinh"
```

---

## 6. Retriever Class

```python
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding.embedder import TextEmbedder
from app.vectorstore.repository import DEFAULT_COLLECTION


class Retriever:
    def __init__(
        self,
        *,
        embedder: TextEmbedder,
        qdrant_client: QdrantClient,
        collection_name: str,
    ) -> None:
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        audience: str = "student",
        context: RetrievalContext | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            return []

        decision = complete_or_clarify_query(query, context=context)
        if not decision.should_search:
            return []

        retriever = build_langchain_qdrant_retriever(
            qdrant_client=self.qdrant_client,
            embedder=self.embedder,
            collection_name=self.collection_name,
            top_k=top_k,
            audience=audience,
        )

        docs = retriever.invoke(decision.query)
        return await hydrate_langchain_documents(session, docs)
```

API/service layer nên truyền `top_k` từ runtime settings nếu request không override. Không đặt fallback kiểu `top_k = provided_top_k or settings.retrieval.top_k`; hãy phân biệt rõ `None` với giá trị sai.

Lưu ý:

```text
Skeleton tren tra `[]` khi can clarification de giu guide retrieval toi thieu.
Khi lam API/LLM orchestration, nen tra object rieng gom `clarification_question` thay vi list rong.
```

---

## 7. Hydrate Results Từ PostgreSQL

LangChain retriever trả về `Document` có `metadata` lấy từ Qdrant payload.

Qdrant payload/metadata cần có:

```text
postgres_chunk_id
```

Lấy full content từ DB:

```python
from sqlalchemy import select

from app.databases.models import DocumentChunk
from langchain_core.documents import Document


async def hydrate_langchain_documents(
    session: AsyncSession,
    docs: list[Document],
) -> list[RetrievalResult]:
    results: list[RetrievalResult] = []

    for doc in docs:
        metadata = doc.metadata or {}
        db_chunk_id = metadata.get("postgres_chunk_id")
        if db_chunk_id is None:
            continue

        chunk = await session.get(DocumentChunk, int(db_chunk_id))
        if chunk is None:
            continue

        heading_path = metadata.get("heading_path") or chunk.heading_path
        source_file = metadata.get("source_file", "")
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")

        results.append(
            RetrievalResult(
                chunk_key=metadata.get("chunk_key", chunk.chunk_key),
                score=float(metadata.get("_score", 0.0)),
                content=chunk.content,
                title=metadata.get("title", ""),
                page_start=page_start,
                page_end=page_end,
                source_file=source_file,
                source_url=metadata.get("source_url", ""),
                citation=build_citation(
                    source_file=source_file,
                    page_start=page_start,
                    page_end=page_end,
                    heading_path=heading_path,
                ),
            )
        )

    return results
```

Lưu ý:

```text
Khong tin Qdrant payload lam canonical content.
Content lay tu PostgreSQL.
LangChain Document.page_content chi dung de debug hoac fallback, khong lam source of truth.
```

---

## 8. Student Filter Ở Đâu?

Student filter nằm trong:

```text
app/vectorstore/repository.py::build_student_filter
```

LangChain retriever phải truyền filter vào `search_kwargs`:

```python
search_kwargs["filter"] = build_student_filter()
```

Không bỏ filter để debug nếu đang dùng endpoint student.

---

## 9. Test Retriever Không Cần Qdrant Thật

Dùng monkeypatch/fake retriever.

```python
from app.embedding.embedder import FakeEmbedder
from app.retrieval.retriever import Retriever
from langchain_core.documents import Document
```

Monkeypatch `build_langchain_qdrant_retriever`:

```python
async def test_retriever_returns_empty_for_blank_query(session):
    retriever = Retriever(
        embedder=FakeEmbedder(),
        qdrant_client=FakeQdrantClient(),
        collection_name="test",
    )

    results = await retriever.search(session, query="   ")

    assert results == []
```

Hydrate test:

```python
async def test_hydrate_langchain_documents_returns_citation(session, saved_child_chunk):
    docs = [
        Document(
            page_content="payload content is not canonical",
            metadata={
                "postgres_chunk_id": saved_child_chunk.id,
                "chunk_key": saved_child_chunk.chunk_key,
                "title": "Test",
                "source_file": "test.md",
                "page_start": 1,
                "page_end": 1,
                "heading_path": ["Test", "Dieu 1"],
            },
        )
    ]

    results = await hydrate_langchain_documents(session, docs)

    assert results[0].content == saved_child_chunk.content
    assert "trang 1" in results[0].citation
```

---

## 10. Test Query Clarification

```python
def test_greeting_does_not_search():
    decision = complete_or_clarify_query("hi")

    assert decision.should_search is False
    assert "CTU" in decision.clarification_question


def test_ambiguous_query_without_context_asks_clarification():
    decision = complete_or_clarify_query("điều kiện là gì")

    assert decision.should_search is False
    assert decision.clarification_question


def test_ambiguous_query_with_current_document_searches_with_filter_context():
    decision = complete_or_clarify_query(
        "điều kiện là gì",
        context=RetrievalContext(current_document_key="xin-giay-khai-sinh"),
    )

    assert decision.should_search is True
    assert decision.document_key == "xin-giay-khai-sinh"


def test_ambiguous_query_with_recent_topic_is_rewritten():
    decision = complete_or_clarify_query(
        "điều kiện là gì",
        context=RetrievalContext(recent_topic="xin giấy khai sinh"),
    )

    assert decision.should_search is True
    assert "xin giấy khai sinh" in decision.query
```

---

## 11. Test Student Filter

Filter test nằm ở vectorstore:

```python
def test_student_filter_contains_required_statuses():
    filter_obj = build_student_filter()
    text = str(filter_obj)

    assert "approved" in text
    assert "published" in text
    assert "audience_student" in text
```

Retriever test cần đảm bảo khi `audience="student"` thì `search_kwargs` có filter.

```python
def test_student_filter_used_for_langchain_retriever(monkeypatch):
    captured = {}

    class FakeVectorStore:
        def __init__(self, **kwargs):
            pass

        def as_retriever(self, *, search_kwargs):
            captured["search_kwargs"] = search_kwargs
            return object()

    monkeypatch.setattr(
        "app.retrieval.retriever.QdrantVectorStore",
        FakeVectorStore,
    )

    build_langchain_qdrant_retriever(
        qdrant_client=object(),
        embedder=FakeEmbedder(),
        collection_name="test",
        top_k=5,
        audience="student",
    )

    assert captured["search_kwargs"]["k"] == 5
    assert captured["search_kwargs"]["filter"] is not None
```

---

## 12. Lệnh Test

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/retrieval
```

Nếu hydrate cần DB:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/retrieval
```

---

## 13. Done Khi

- [ ] Blank query trả `[]`.
- [ ] Greeting/smalltalk như `hi`, `xin chào` không search Qdrant.
- [ ] Query thiếu object như `điều kiện là gì` không search nếu không có context.
- [ ] Query thiếu object nhưng có `current_document_key` thì truyền context/filter xuống retrieval.
- [ ] Query thiếu object nhưng có `recent_topic` thì rewrite query trước retrieval.
- [ ] Query được embed bằng embedder.
- [ ] Student retrieval dùng LangChain Qdrant retriever với hard filter.
- [ ] Result lấy full content từ PostgreSQL.
- [ ] Citation có source file và page/heading.
- [ ] Expired/unpublished documents bị filter ở vectorstore.
- [ ] Unit test retriever pass.

---

## 14. Lỗi Dễ Gặp

### Lỗi: retrieval có score nhưng content rỗng

Nguyên nhân:

```text
Qdrant payload thieu postgres_chunk_id hoac DB chunk da bi xoa.
```

Xử lý:

```text
Kiem tra payload upsert.
Khi reingest/delete chunks, can deactivate/delete old Qdrant points.
```

### Lỗi: student thấy tài liệu chưa duyệt

Nguyên nhân:

```text
student_only=False hoac filter thieu review_status=approved/rag_status=published.
```

Xử lý:

```text
Endpoint student khong cho override filter.
```

### Lỗi: citation không có page

Nguyên nhân:

```text
Markdown thieu page marker.
```

Xử lý:

```text
Fallback sang heading_path trong build_citation.
```
