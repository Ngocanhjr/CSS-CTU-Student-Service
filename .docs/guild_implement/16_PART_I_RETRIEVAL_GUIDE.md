# 16. Part I - Huong Dan Implement Retrieval Toi Thieu

**Last Updated:** 2026-06-20

File nay tach chi tiet tu guide 07, phan I.

Muc tieu:

```text
Nhan query
retrieval qua LangChain Qdrant retriever
van ap dung filter student
lay full content/citation
tra ve retrieval results
```

Guide nay chua lam LLM answer generation.

---

## 1. File Can Sua/Tao

```text
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/test/retrieval/test_retriever.py
```

Phu thuoc:

```text
app.embedding.embedder
app.vectorstore.repository
app.databases.models
langchain-qdrant
langchain-core
```

Da chot RAG pipeline di theo LangChain:

```text
Embedding: LangChain NVIDIAEmbeddings
Vector retrieval: LangChain QdrantVectorStore/retriever
Hydration/citation/status: project code rieng
```

Ly do van can project code:

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


def build_langchain_qdrant_retriever(
    *,
    qdrant_client: QdrantClient,
    embedder: TextEmbedder,
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = 5,
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

Luu y:

```text
TextEmbedder can tuong thich LangChain Embeddings interface.
Neu TextEmbedder wrapper rieng khong du interface, tao adapter nho co embed_documents() va embed_query().
```

---

## 5. Query Clarification / Context Completion

Khong nen embed/search ngay moi query nguoi dung nhap vao.

Truoc clarification, nen chan greeting/smalltalk:

```text
hi
hello
chào
xin chào
alo
```

Nhung query nay khong can retrieval. Tra loi truc tiep va hoi user muon hoi ve noi dung nao.

Mot so query qua ngan hoac thieu doi tuong, vi du:

```text
điều kiện là gì
hồ sơ gồm gì
nộp ở đâu
cần giấy gì
```

Nhung query nay chi co nghia khi biet nguoi dung dang hoi ve thu tuc/tai lieu nao.

Rule:

```text
Neu query la greeting/smalltalk -> tra loi truc tiep, khong retrieval.
Neu query du ro -> retrieval binh thuong.
Neu query thieu object va khong co context -> hoi lai nguoi dung.
Neu UI co current_document_key/current_version_key -> bo sung filter theo document/version.
Neu chat history vua nhac object ro rang -> rewrite query bang object do roi retrieval.
```

Bang quyet dinh:

| Truong hop | Xu ly |
|---|---|
| `hi` / `xin chào` | Tra greeting response, khong search |
| `điều kiện xin giấy khai sinh là gì` | Retrieval binh thuong |
| `điều kiện là gì` va khong co context | Tra clarification question |
| `điều kiện là gì` va UI dang xem document `xin-giay-khai-sinh` | Search voi `document_key=xin-giay-khai-sinh` |
| `điều kiện là gì` sau cau truoc vua noi `xin giấy khai sinh` | Rewrite thanh `điều kiện xin giấy khai sinh là gì` |

Model de xuat:

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

Luu y:

```text
Day la rule toi thieu, khong phai LLM answer generation.
Clarification question la output hop le cua retrieval layer/API orchestration.
Neu co current_document_key/current_version_key, truyen xuong Qdrant metadata filter.
Neu rewrite bang chat history, phai log query goc va query da rewrite de debug.
```

Vi du:

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
        top_k: int = 5,
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

Luu y:

```text
Skeleton tren tra `[]` khi can clarification de giu guide retrieval toi thieu.
Khi lam API/LLM orchestration, nen tra object rieng gom `clarification_question` thay vi list rong.
```

---

## 7. Hydrate Results Tu PostgreSQL

LangChain retriever tra ve `Document` co `metadata` lay tu Qdrant payload.

Qdrant payload/metadata can co:

```text
postgres_chunk_id
```

Lay full content tu DB:

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

Luu y:

```text
Khong tin Qdrant payload lam canonical content.
Content lay tu PostgreSQL.
LangChain Document.page_content chi dung de debug hoac fallback, khong lam source of truth.
```

---

## 8. Student Filter O Dau?

Student filter nam trong:

```text
app/vectorstore/repository.py::build_student_filter
```

LangChain retriever phai truyen filter vao `search_kwargs`:

```python
search_kwargs["filter"] = build_student_filter()
```

Khong bo filter de debug neu dang dung endpoint student.

---

## 9. Test Retriever Khong Can Qdrant That

Dung monkeypatch/fake retriever.

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

Filter test nam o vectorstore:

```python
def test_student_filter_contains_required_statuses():
    filter_obj = build_student_filter()
    text = str(filter_obj)

    assert "approved" in text
    assert "published" in text
    assert "audience_student" in text
```

Retriever test can dam bao khi `audience="student"` thi `search_kwargs` co filter.

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

## 12. Lenh Test

```powershell
cd E:\RHNA\#Visual\NLCS\CTU-Service\chatbot\backend
..\..\.venv\Scripts\python.exe -m pytest test/retrieval
```

Neu hydrate can DB:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://ct239h:1232@localhost:5432/ctu_student_service_test"
..\..\.venv\Scripts\python.exe -m pytest test/retrieval
```

---

## 13. Done Khi

- [ ] Blank query tra `[]`.
- [ ] Greeting/smalltalk nhu `hi`, `xin chào` khong search Qdrant.
- [ ] Query thieu object nhu `điều kiện là gì` khong search neu khong co context.
- [ ] Query thieu object nhung co `current_document_key` thi truyen context/filter xuong retrieval.
- [ ] Query thieu object nhung co `recent_topic` thi rewrite query truoc retrieval.
- [ ] Query duoc embed bang embedder.
- [ ] Student retrieval dung LangChain Qdrant retriever voi hard filter.
- [ ] Result lay full content tu PostgreSQL.
- [ ] Citation co source file va page/heading.
- [ ] Expired/unpublished documents bi filter o vectorstore.
- [ ] Unit test retriever pass.

---

## 14. Loi De Gap

### Loi: retrieval co score nhung content rong

Nguyen nhan:

```text
Qdrant payload thieu postgres_chunk_id hoac DB chunk da bi xoa.
```

Xu ly:

```text
Kiem tra payload upsert.
Khi reingest/delete chunks, can deactivate/delete old Qdrant points.
```

### Loi: student thay tai lieu chua duyet

Nguyen nhan:

```text
student_only=False hoac filter thieu review_status=approved/rag_status=published.
```

Xu ly:

```text
Endpoint student khong cho override filter.
```

### Loi: citation khong co page

Nguyen nhan:

```text
Markdown thieu page marker.
```

Xu ly:

```text
Fallback sang heading_path trong build_citation.
```
