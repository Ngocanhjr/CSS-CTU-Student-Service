# 16. Part I - Hướng Dẫn Implement Retrieval Tối Thiểu

**Last Updated:** 2026-07-10

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
chatbot/backend/app/retrieval/eligibility.py
chatbot/backend/app/retrieval/retriever.py
chatbot/backend/test/retrieval/test_eligibility.py
chatbot/backend/test/retrieval/test_retriever.py
```

`app/retrieval/eligibility.py` là nguồn duy nhất định nghĩa eligibility (`EligibilityPolicy`, Guide
22 §12.2, chi tiết implementation ở Guide 15 §8.1). `search_sparse_documents()` (§2) và
`build_langchain_qdrant_retriever()` (§4) trong file này đều gọi module đó, không tự định nghĩa
điều kiện `review_status`/`rag_status`/audience riêng. `is_latest` chỉ là ranking preference.

Phụ thuộc:

```text
app.embedding.embedder
app.retrieval.eligibility
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

`RetrievalResult` giữ trace fields, structural metadata và lý do candidate xuất hiện sau expansion. Canonical `content` luôn được hydrate từ PostgreSQL.

```python
from dataclasses import dataclass
from typing import Literal


ExpansionReason = Literal[
    "direct_hit",
    "parent_context",
    "child_expansion",
    "sibling_expansion",
    "split_neighbor",
]


@dataclass(frozen=True)
class RetrievalResult:
    postgres_chunk_id: int
    postgres_parent_chunk_id: int | None
    document_key: str
    version_key: str
    chunk_key: str
    parent_chunk_key: str | None
    score: float
    content: str
    title: str
    page_start: int | None
    page_end: int | None
    source_file: str
    source_url: str
    citation: str
    heading_path: list[str]
    item_path: list[str]
    legal_unit_type: str
    block_type: str | None = None
    logical_item_key: str | None = None
    logical_item_keys: list[str] | None = None
    parent_item_key: str | None = None
    logical_table_key: str | None = None
    logical_code_key: str | None = None
    split_index: int = 0
    split_count: int = 1
    chunk_index: int | None = None
    item_marker: str | None = None
    item_level: int | None = None
    expansion_reason: ExpansionReason = "direct_hit"
```

Structural fields nam trong Qdrant payload. Hydration lay canonical `content` va parent relation tu PostgreSQL; khong ky vong PostgreSQL co cot `structural_metadata`.

### Hybrid retrieval bắt buộc

```text
resolved query + shared hard filters
→ Qdrant dense candidates
  + PostgreSQL FTS/BM25 candidates
→ attach Qdrant payload cho sparse-only candidates bang qdrant_point_id
→ RRF hoặc weighted fusion
→ hydrate fused candidates từ PostgreSQL
→ rerank direct hits
→ structural expansion
→ hydrate expanded neighbors
→ deduplicate
→ source-order
→ context budget
```

Không gọi luồng chỉ-Qdrant là hybrid retrieval. Dense và sparse phải dùng cùng eligibility/student filters trước fusion — cụ thể là cùng gọi `EligibilityPolicy` (`app/retrieval/eligibility.py`, xem Guide 22 §12.2), không tự định nghĩa `review_status`/`rag_status`/audience riêng ở từng phía; cả hai không hard-filter `is_latest`.
Rerank la bat buoc trong production flow. Test co the truyen deterministic stub, nhung production caller khong duoc bo qua.

### PostgreSQL FTS + Qdrant payload cho sparse candidate

PostgreSQL FTS tra canonical row va `qdrant_point_id`. Vi structural metadata chi nam trong
Qdrant theo contract MVP, sparse-only candidate phai retrieve payload bang point id truoc
structural expansion.

Suggested pattern:

```python
from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import desc, func, select

from app.databases.models import Document, DocumentChunk, DocumentVersion
from app.retrieval.eligibility import EligibilityContext, EligibilityPolicy


async def search_sparse_documents(
    session: AsyncSession,
    *,
    query: str,
    top_k: int,
    audience: str,
    document_key: str | None = None,
    version_key: str | None = None,
) -> list[LangChainDocument]:
    ts_query = func.websearch_to_tsquery("simple", query)
    vector = func.to_tsvector("simple", DocumentChunk.content)
    rank = func.ts_rank_cd(vector, ts_query).label("score")
    # Eligibility (review_status/rag_status/audience) khong tu dinh nghia rieng o day;
    # phai dung cung EligibilityPolicy voi dense-side de tranh fusion hai eligibility domain khac
    # nhau (Guide 22 §12.2).
    eligibility_conditions = EligibilityPolicy.build_postgres_conditions(
        EligibilityContext(
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )
    )
    statement = (
        select(DocumentChunk, DocumentVersion, Document, rank)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(
            DocumentChunk.chunk_type == "child",
            DocumentChunk.index_status == "indexed",
            DocumentChunk.qdrant_point_id.is_not(None),
            *eligibility_conditions,
            vector.op("@@")(ts_query),
        )
        .order_by(desc(rank))
        .limit(top_k * 3)
    )

    rows = (await session.execute(statement)).all()
    return [
        LangChainDocument(
            page_content=chunk.content,
            metadata={
                "postgres_chunk_id": chunk.id,
                "qdrant_point_id": chunk.qdrant_point_id,
                "chunk_key": chunk.chunk_key,
                "parent_chunk_id": chunk.parent_chunk_id,
                "document_key": document.document_key,
                "version_key": version.version_key,
                "_score": float(score),
            },
        )
        for chunk, version, document, score in rows
    ]


def attach_qdrant_payloads(
    client: QdrantClient,
    *,
    collection_name: str,
    docs: list[LangChainDocument],
) -> list[LangChainDocument]:
    point_ids = [
        doc.metadata["qdrant_point_id"]
        for doc in docs
        if doc.metadata.get("qdrant_point_id")
    ]
    records = client.retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=True,
        with_vectors=False,
    ) if point_ids else []
    payload_by_id = {str(record.id): dict(record.payload or {}) for record in records}

    enriched: list[LangChainDocument] = []
    for doc in docs:
        point_id = doc.metadata.get("qdrant_point_id")
        payload = payload_by_id.get(str(point_id), {})
        enriched.append(
            LangChainDocument(
                page_content=doc.page_content,
                metadata={**doc.metadata, **payload},
            )
        )
    return enriched


def reciprocal_rank_fusion(
    dense_docs: list[LangChainDocument],
    sparse_docs: list[LangChainDocument],
    *,
    limit: int,
    rank_constant: int = 60,
) -> list[LangChainDocument]:
    by_key: dict[str, LangChainDocument] = {}
    scores: dict[str, float] = {}
    for ranked_docs in (dense_docs, sparse_docs):
        for rank, doc in enumerate(ranked_docs, start=1):
            key = str(doc.metadata["chunk_key"])
            by_key.setdefault(key, doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rank_constant + rank)

    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)[:limit]
    return [
        LangChainDocument(
            page_content=by_key[key].page_content,
            metadata={**by_key[key].metadata, "_score": scores[key]},
        )
        for key in ordered
    ]
```

Can co expression GIN index cho `to_tsvector('simple', content)`; migration nam trong Guide 04.

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

### 4.1. Vector name và payload key phải khớp Guide 15

`QdrantVectorStore` mặc định `vector_name=""` (unnamed vector), `content_payload_key="page_content"`,
`metadata_payload_key="metadata"`. Guide 15 tạo collection với **named vector**
`VECTOR_NAME = "embedding"` (Guide 15 §6) và payload **flat** (không có key `page_content`/`metadata`
lồng nhau, các field như `chunk_key`/`heading_path`/... nằm ngay top-level, Guide 15 §7).

Hệ quả nếu không xử lý:

```text
Khong truyen vector_name="embedding": _validate_collection_config() (mac dinh
validate_collection_config=True) raise QdrantVectorStoreError ngay khi tao QdrantVectorStore,
vi collection khong co unnamed vector.
Neu bypass validate (validate_collection_config=False): Document tra ve van co page_content=""
va metadata={} vi payload Guide 15 khong co key page_content/metadata.
```

Vì vậy bắt buộc:

```text
Truyen vector_name=VECTOR_NAME (import tu app.vectorstore.repository, khong hardcode string
lap lai o hai noi).
Sau khi lay Document tu QdrantVectorStore, phai refetch full flat payload bang point id,
dung lai attach_qdrant_payloads() (Muc 2) - giong cach xu ly sparse candidates.
```

`QdrantVectorStore._document_from_point` luôn set `metadata["_id"] = scored_point.id`, nên
`doc.metadata["_id"]` chính là `qdrant_point_id` — dùng lại được ngay để gọi
`attach_qdrant_payloads()` cho cả dense candidates.

### 4.2. Embedding adapter bắt buộc

`TextEmbedder` (Guide 14) chỉ có `embed_texts()`/`embed_query()`, không tương thích interface
LangChain `Embeddings` (`embed_documents()`/`embed_query()`). Cần adapter thật, không chỉ ghi chú
"tạo adapter nhỏ":

```python
from langchain_core.embeddings import Embeddings

from app.embedding.embedder import TextEmbedder


class LangChainEmbeddingsAdapter(Embeddings):
    def __init__(self, embedder: TextEmbedder) -> None:
        self._embedder = embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed_query(text)
```

### 4.3. Khởi tạo retriever

```python
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore

from app.embedding.embedder import TextEmbedder
from app.vectorstore.repository import (
    DEFAULT_COLLECTION,
    VECTOR_NAME,
    RetrievalFilter,
    build_eligibility_filter,
)


DEFAULT_TOP_K = 5


def build_langchain_qdrant_retriever(
    *,
    qdrant_client: QdrantClient,
    embedder: TextEmbedder,
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = DEFAULT_TOP_K,
    audience: str = "student",
    document_key: str | None = None,
    version_key: str | None = None,
):
    vectorstore = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=LangChainEmbeddingsAdapter(embedder),
        vector_name=VECTOR_NAME,
    )

    filters = RetrievalFilter(
        document_key=document_key,
        version_key=version_key,
        chunk_type="child",
    )
    search_kwargs = {"k": top_k}
    # Moi audience deu qua build_eligibility_filter() (Guide 22 §12.2, Guide 15 §8.1/§9); khong co
    # nhanh audience nao bo qua review_status/rag_status.
    search_kwargs["filter"] = build_eligibility_filter(filters, audience=audience)

    return vectorstore.as_retriever(search_kwargs=search_kwargs)
```

`QueryDecision.document_key` và `QueryDecision.version_key` phải được truyền vào đây. Eligibility hard filter (`review_status`/`rag_status` + audience) không bị context filter thay thế, và không phân biệt audience ở tầng status — chỉ khác ở điều kiện hiển thị. `is_latest` chỉ dùng sau fusion/rerank.

`VECTOR_NAME` phải import từ `app.vectorstore.repository` — nếu Guide 15 đổi tên named vector, Guide 16 phải theo tự động, không sửa 2 nơi.

### 4.4. Refetch flat payload cho dense candidates

`qdrant_retriever.invoke(query)` trả `Document` với `metadata` không có structural fields (payload
Guide 15 flat, không khớp `metadata_payload_key` mặc định). Trước khi đưa vào
`reciprocal_rank_fusion`, dense candidates phải refetch payload giống sparse candidates:

```python
def attach_point_id_from_document(docs: list[LangChainDocument]) -> list[LangChainDocument]:
    enriched = []
    for doc in docs:
        enriched.append(
            LangChainDocument(
                page_content=doc.page_content,
                metadata={**doc.metadata, "qdrant_point_id": doc.metadata.get("_id")},
            )
        )
    return enriched
```

`dense_docs` phải đi qua `attach_point_id_from_document()` rồi `attach_qdrant_payloads()` (Mục 2)
trước khi fusion — xem Mục 6 (`search_resolved_query`) đã cập nhật theo bước này. Không giả định
`Document.metadata` từ `QdrantVectorStore` đã có `chunk_key`/structural fields.

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


UNDERSPECIFIED_QUERIES = {
    "điều kiện là gì",
    "hồ sơ gồm gì",
    "nộp ở đâu",
    "cần gì",
    "cần giấy gì",
}


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
    is_ambiguous = normalized.lower() in UNDERSPECIFIED_QUERIES
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
Không dùng substring rộng như `"hồ sơ" in query`, vì query rõ như "hồ sơ xin cấp bảng điểm gồm gì" vẫn phải được search.
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

## 6. Retriever Class Và Orchestration

`complete_or_clarify_query()` thuộc lớp điều phối request/answer chain. `Retriever.search_resolved_query()` chỉ nhận query đã được quyết định là có thể search; vì vậy list rỗng chỉ còn nghĩa là không có retrieval result.

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
        rerank,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        self.rerank = rerank
        self.collection_name = collection_name

    async def search_resolved_query(
        self,
        session: AsyncSession,
        *,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        audience: str = "student",
        document_key: str | None = None,
        version_key: str | None = None,
        context_budget: int = 6000,
    ) -> list[RetrievalResult]:
        if not query.strip():
            return []

        qdrant_retriever = build_langchain_qdrant_retriever(
            qdrant_client=self.qdrant_client,
            embedder=self.embedder,
            collection_name=self.collection_name,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )

        dense_docs = qdrant_retriever.invoke(query)
        dense_docs = attach_qdrant_payloads(
            self.qdrant_client,
            collection_name=self.collection_name,
            docs=attach_point_id_from_document(dense_docs),
        )
        sparse_docs = await search_sparse_documents(
            session,
            query=query,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )
        sparse_docs = attach_qdrant_payloads(
            self.qdrant_client,
            collection_name=self.collection_name,
            docs=sparse_docs,
        )
        docs = reciprocal_rank_fusion(dense_docs, sparse_docs, limit=top_k)
        direct_hits = await hydrate_langchain_documents(
            session,
            docs,
            expansion_reason="direct_hit",
        )

        reranked_hits = self.rerank(direct_hits)
        expanded = await expand_structural_context(
            session,
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
            direct_hits=reranked_hits,
            query=query,
            context_budget=context_budget,
        )

        return finalize_retrieval_results(
            expanded,
            context_budget=context_budget,
        )
```

Caller dùng flow:

```python
decision = complete_or_clarify_query(question, context=context)
if not decision.should_search:
    # trả greeting/clarification, không gọi Retriever
    ...

results = await retriever.search_resolved_query(
    session,
    query=decision.query,
    document_key=decision.document_key,
    version_key=decision.version_key,
    top_k=top_k,
)
```

Không giữ API `Retriever.search()` trả `[]` khi cần clarification, vì như vậy không phân biệt được clarification với no-result.

---

## 7. Hydrate Results Từ PostgreSQL

LangChain retriever trả về `Document` có `metadata` lấy từ Qdrant payload.

Qdrant payload/metadata cần có:

```text
postgres_chunk_id
chunk_key
parent_chunk_key
heading_path
item_path
legal_unit_type
block_type
logical_item_key
logical_item_keys
parent_item_key
logical_table_key
logical_code_key
split_index
split_count
chunk_index
item_marker
item_level
page_start
page_end
```

Lấy full content từ DB:

```python
from sqlalchemy import select

from app.databases.models import DocumentChunk
from langchain_core.documents import Document


async def hydrate_langchain_documents(
    session: AsyncSession,
    docs: list[Document],
    *,
    expansion_reason: ExpansionReason = "direct_hit",
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
        item_path = metadata.get("item_path", [])
        legal_unit_type = metadata.get("legal_unit_type", "none")
        block_type = metadata.get("block_type")
        logical_item_key = metadata.get("logical_item_key")
        logical_item_keys = metadata.get("logical_item_keys") or ([logical_item_key] if logical_item_key else [])
        parent_item_key = metadata.get("parent_item_key")
        logical_table_key = metadata.get("logical_table_key")
        logical_code_key = metadata.get("logical_code_key")
        split_index = int(metadata.get("split_index", 0))
        split_count = int(metadata.get("split_count", 1))
        chunk_index = metadata.get("chunk_index")
        item_marker = metadata.get("item_marker")
        item_level = metadata.get("item_level")
        parent_chunk_key = metadata.get("parent_chunk_key")
        if parent_chunk_key is None and chunk.parent_chunk_id is not None:
            parent_row = await session.get(DocumentChunk, chunk.parent_chunk_id)
            if parent_row is not None:
                parent_chunk_key = parent_row.chunk_key

        source_file = metadata.get("source_file", "")
        page_start = metadata.get("page_start")
        if page_start is None:
            page_start = chunk.page_start
        page_end = metadata.get("page_end")
        if page_end is None:
            page_end = chunk.page_end

        results.append(
            RetrievalResult(
                postgres_chunk_id=int(db_chunk_id),
                postgres_parent_chunk_id=metadata.get("postgres_parent_chunk_id") or chunk.parent_chunk_id,
                document_key=metadata.get("document_key", ""),
                version_key=metadata.get("version_key", ""),
                chunk_key=metadata.get("chunk_key", chunk.chunk_key),
                parent_chunk_key=parent_chunk_key,
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
                heading_path=heading_path,
                item_path=item_path,
                legal_unit_type=legal_unit_type,
                block_type=block_type,
                logical_item_key=logical_item_key,
                logical_item_keys=logical_item_keys,
                parent_item_key=parent_item_key,
                logical_table_key=logical_table_key,
                logical_code_key=logical_code_key,
                split_index=split_index,
                split_count=split_count,
                chunk_index=chunk_index,
                item_marker=item_marker,
                item_level=item_level,
                expansion_reason=expansion_reason,
            )
        )

    return results
```

Lưu ý:

```text
Khong tin Qdrant payload lam canonical content.
Hydration thay content bang PostgreSQL canonical content, nhưng vẫn giữ structural metadata
từ retrieval candidate để parent/child/sibling/split expansion dùng tiếp.
Content lay tu PostgreSQL.
LangChain Document.page_content chi dung de debug hoac fallback, khong lam source of truth.
SQLAlchemy `DocumentChunk` không có `parent_chunk_key`; fallback phải đi qua `parent_chunk_id`/parent row như skeleton trên.
```

---

## 8. Eligibility Filter Ở Đâu?

Eligibility policy (nguồn chân lý, Guide 22 §12.2) nằm trong:

```text
app/retrieval/eligibility.py::EligibilityPolicy
```

`app/vectorstore/repository.py::build_eligibility_filter` (Qdrant) và
`app/retrieval/retriever.py::search_sparse_documents` (PostgreSQL, §2) đều gọi
`EligibilityPolicy` — không tự định nghĩa `review_status`/`rag_status`/audience riêng.

LangChain retriever phải truyền filter vào `search_kwargs`. Khi QueryDecision có document/version context, dùng cùng `RetrievalFilter` để cộng điều kiện vào eligibility hard filter:

```python
filters = RetrievalFilter(
    document_key=decision.document_key,
    version_key=decision.version_key,
    chunk_type="child",
)
search_kwargs["filter"] = build_eligibility_filter(filters, audience=audience)
```

Không bỏ eligibility filter để debug ở bất kỳ audience nào (student, admin, internal) — `review_status=approved`, `rag_status=published` luôn bắt buộc; chỉ điều kiện hiển thị (`audience_student`) khác nhau theo audience. Không hard-filter `is_latest`.

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
async def test_resolved_retriever_returns_empty_for_blank_query(session):
    retriever = Retriever(
        embedder=FakeEmbedder(),
        qdrant_client=FakeQdrantClient(),
        rerank=lambda results: results,  # deterministic test stub
        collection_name="test",
    )

    results = await retriever.search_resolved_query(session, query="   ")

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


async def test_hydration_falls_back_to_parent_row(session, saved_parent, saved_child):
    docs = [
        Document(
            page_content="not canonical",
            metadata={
                "postgres_chunk_id": saved_child.id,
                "document_key": "doc",
                "version_key": "doc-v1",
                "chunk_key": saved_child.chunk_key,
                # intentionally omit parent_chunk_key
            },
        )
    ]

    results = await hydrate_langchain_documents(session, docs)

    assert results[0].parent_chunk_key == saved_parent.chunk_key
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

## 11. Test Eligibility Filter

`EligibilityPolicy` test nằm ở `app/retrieval/eligibility.py` (Guide 15 §12 có bộ test đầy đủ cho
cả student và admin/internal — không audience nào được bỏ qua status). Ở đây chỉ test việc
retriever/sparse-search *sử dụng* policy đúng cách:

```python
def test_eligibility_filter_contains_required_statuses_for_student():
    filter_obj = build_eligibility_filter(audience="student")
    text = str(filter_obj)

    assert "approved" in text
    assert "published" in text
    assert "audience_student" in text


def test_eligibility_filter_still_requires_status_for_admin():
    filter_obj = build_eligibility_filter(audience="admin")
    text = str(filter_obj)

    assert "approved" in text
    assert "published" in text
    assert "audience_student" not in text
```

Retriever test cần đảm bảo khi `audience="student"` thì `search_kwargs` có filter, **và** khi
`audience="admin"` filter vẫn chứa status (không rẽ nhánh sang filter không status).

```python
def test_eligibility_filter_used_for_langchain_retriever(monkeypatch):
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


def test_admin_audience_still_carries_status_filter(monkeypatch):
    captured = {}

    class FakeVectorStore:
        def __init__(self, **kwargs):
            pass

        def as_retriever(self, *, search_kwargs):
            captured["filter"] = search_kwargs["filter"]
            return object()

    monkeypatch.setattr(
        "app.retrieval.retriever.QdrantVectorStore",
        FakeVectorStore,
    )

    build_langchain_qdrant_retriever(
        qdrant_client=object(),
        embedder=FakeEmbedder(),
        collection_name="test",
        audience="admin",
    )

    filter_text = str(captured["filter"])
    assert "approved" in filter_text
    assert "published" in filter_text
    assert "is_latest" not in filter_text


def test_document_and_version_context_are_forwarded(monkeypatch):
    captured = {}

    class FakeVectorStore:
        def __init__(self, **kwargs):
            pass

        def as_retriever(self, *, search_kwargs):
            captured["filter"] = search_kwargs["filter"]
            return object()

    monkeypatch.setattr(
        "app.retrieval.retriever.QdrantVectorStore",
        FakeVectorStore,
    )

    build_langchain_qdrant_retriever(
        qdrant_client=object(),
        embedder=FakeEmbedder(),
        collection_name="test",
        document_key="doc-1",
        version_key="doc-1-v1",
    )

    filter_text = str(captured["filter"])
    assert "doc-1" in filter_text
    assert "doc-1-v1" in filter_text
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

- [ ] Blank resolved query trả `[]` mà không gọi Qdrant.
- [ ] Greeting/smalltalk và query mơ hồ được `QueryDecision` xử lý trước Retriever.
- [ ] Query có `current_document_key/current_version_key` truyền filter xuống Qdrant.
- [ ] Query có `recent_topic` được rewrite trước retrieval.
- [ ] Student retrieval giữ hard filter approved/published/audience_student; không hard-filter is_latest.
- [ ] `search_sparse_documents()` gọi `EligibilityPolicy.build_postgres_conditions()`, không tự
      hard-code `review_status`/`rag_status`/`audience` riêng.
- [ ] `build_langchain_qdrant_retriever()` gọi `build_eligibility_filter()` cho mọi audience —
      không rẽ nhánh audience giữa filter có status và filter không status.
- [ ] Admin/internal retrieval vẫn giữ `review_status=approved`, `rag_status=published`; chỉ khác
      student ở việc không ép `audience_student=true`.
- [ ] Dense và sparse dùng cùng `EligibilityContext` trước fusion (RRF); cả hai không hard-filter
      `is_latest`, chỉ dùng nó làm ranking preference sau fusion/rerank.
- [ ] `QdrantVectorStore` khởi tạo với `vector_name=VECTOR_NAME` ("embedding"), không dùng default
      `""` — nếu thiếu, `_validate_collection_config()` raise lỗi ngay khi tạo instance.
- [ ] Có `LangChainEmbeddingsAdapter` implement thật `embed_documents()`/`embed_query()`, không chỉ
      ghi chú "tạo adapter nhỏ".
- [ ] `dense_docs` đi qua `attach_point_id_from_document()` + `attach_qdrant_payloads()` trước RRF,
      giống cách xử lý `sparse_docs` — không giả định `metadata` từ `QdrantVectorStore` đã có
      `chunk_key`/structural fields (payload Guide 15 là flat, không khớp `page_content`/`metadata`
      mặc định của LangChain).
- [ ] Direct hit hydrate canonical content từ PostgreSQL.
- [ ] Hydration giữ structural metadata từ Qdrant.
- [ ] `parent_chunk_key` fallback qua `parent_chunk_id`/parent row, không dùng field DB không tồn tại.
- [ ] Structural expansion được gọi trong `search_resolved_query()`.
- [ ] Parent/child/sibling/split expansion, deduplicate, source-order và context budget có test.
- [ ] Citation có source file và page/heading.
- [ ] Unit test retrieval pass.

---

## 14. Lỗi Dễ Gặp

### Lỗi: `QdrantVectorStoreError` khi khởi tạo retriever

Nguyên nhân:

```text
QdrantVectorStore(...) khong truyen vector_name="embedding" (Guide 15 tao named vector "embedding",
QdrantVectorStore mac dinh vector_name="").
```

Xử lý:

```text
Import VECTOR_NAME tu app.vectorstore.repository va truyen vao QdrantVectorStore(vector_name=...).
```

### Lỗi: dense candidate có score nhưng thiếu `chunk_key`/structural fields trước fusion

Nguyên nhân:

```text
QdrantVectorStore mac dinh content_payload_key="page_content"/metadata_payload_key="metadata",
nhung payload Guide 15 la flat (khong co key page_content/metadata). Document.metadata tra ve
rong, reciprocal_rank_fusion() se KeyError o doc.metadata["chunk_key"].
```

Xử lý:

```text
Refetch payload bang qdrant_point_id qua attach_point_id_from_document() + attach_qdrant_payloads()
(Muc 4.4) truoc khi dua dense_docs vao reciprocal_rank_fusion().
```

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
Filter thieu review_status=approved/rag_status=published, hoac khong goi qua
EligibilityPolicy.
```

Xử lý:

```text
Endpoint student khong cho override filter. Moi filter phai di qua build_eligibility_filter()/
EligibilityPolicy, khong tu dinh nghia dieu kien status rieng.
```

### Lỗi: admin thấy fusion trộn hai eligibility domain khác nhau

Nguyên nhân:

```text
Dense-side dung build_context_filter() (khong status) cho admin, con sparse-side
search_sparse_documents() van hard-code review_status/rag_status cho moi audience — hai candidate
set truoc RRF fusion thuoc hai eligibility domain khac nhau.
```

Xử lý:

```text
Ca dense va sparse phai goi cung EligibilityPolicy voi cung EligibilityContext truoc fusion. Xem
Guide 22 §12.2. Khong audience nao (ke ca admin/internal) duoc bo qua review_status/rag_status;
chi khac o dieu kien audience_student. is_latest khong nam trong eligibility hard filter.
```

### Citation Fallback Page 1

Nguyên nhân:

```text
Markdown khong co page marker nen fallback citation page 1.
```

Xử lý:

```text
Trả citation page 1. Với tài liệu nhiều trang, bổ sung marker khi review để citation chính xác hơn.
```

## 15. Structural Expansion Sau Initial Retrieval

Flow production bắt buộc:

```text
Qdrant dense + PostgreSQL FTS/BM25
→ attach Qdrant payload cho sparse-only candidates bang qdrant_point_id
→ RRF hoặc weighted fusion
→ hydrate fused candidates từ PostgreSQL
→ rerank
→ structural expansion bằng Qdrant structural payload
→ hydrate expanded neighbors từ PostgreSQL
→ deduplicate theo chunk_key
→ source-order theo chunk_index
→ enforce context budget
```

### 15.1 Detect list query

```python
LIST_QUERY_PATTERNS = (
    "gồm gì",
    "bao gồm",
    "các trường hợp nào",
    "cần giấy tờ gì",
    "có những loại nào",
    "hồ sơ gồm gì",
)


def detect_list_query(query: str) -> bool:
    normalized = query.strip().lower()
    return any(pattern in normalized for pattern in LIST_QUERY_PATTERNS)
```

### 15.2 Neighbor lookup responsibilities

Các helper lookup đọc structural fields từ Qdrant payload, sau đó hydrate canonical content bằng `postgres_chunk_id`:

```python
async def find_parent_item(..., hit: RetrievalResult) -> list[RetrievalResult]:
    """Lookup candidate có logical_item_key == hit.parent_item_key."""


async def find_direct_children(..., hit: RetrievalResult) -> list[RetrievalResult]:
    """Lookup candidate có parent_item_key == hit.logical_item_key."""


async def find_siblings(..., hit: RetrievalResult) -> list[RetrievalResult]:
    """Lookup candidate cùng parent_item_key, cùng version/parent chunk."""


async def find_split_neighbors(..., hit: RetrievalResult) -> list[RetrievalResult]:
    """Lookup cùng logical_item_key và split_index liền kề/cùng group."""
```

Mọi lookup phải scope tối thiểu theo `version_key`; khi có thể thêm `parent_chunk_key` để tránh nối nhầm cấu trúc giữa section.

### 15.3 Expansion orchestration

```python
async def expand_structural_context(
    session,
    *,
    qdrant_client,
    collection_name: str,
    direct_hits: list[RetrievalResult],
    query: str,
    context_budget: int,
) -> list[RetrievalResult]:
    candidates = list(direct_hits)
    list_query = detect_list_query(query)

    for hit in direct_hits:
        if hit.parent_item_key:
            candidates.extend(
                await find_parent_item(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                    expansion_reason="parent_context",
                )
            )

        if list_query and hit.logical_item_key:
            candidates.extend(
                await find_direct_children(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                    expansion_reason="child_expansion",
                )
            )

        if list_query and hit.parent_item_key:
            candidates.extend(
                await find_siblings(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                    expansion_reason="sibling_expansion",
                )
            )

        if hit.split_count > 1 and hit.logical_item_key:
            candidates.extend(
                await find_split_neighbors(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                    expansion_reason="split_neighbor",
                )
            )

    # Chi thu thap candidate o buoc nay. Deduplicate/order/budget
    # duoc thuc hien dung mot lan trong finalize_retrieval_results().
    return candidates
```

Rules:

```text
- Hit child lấy logical item cha bằng parent_item_key.
- Hit bullet_group dùng parent_item_key để expansion; logical_item_keys chỉ trace/citation từng bullet.
- Hit item cha + list query lấy direct children.
- List query có thể lấy siblings cùng parent_item_key.
- Hit split lấy adjacent/cùng logical_item_key trong budget.
- Không mở rộng toàn bộ Parent khi chỉ cần một nhánh.
- Canonical content của neighbor luôn hydrate từ PostgreSQL.
```

### 15.4 Finalization helpers

```python
def deduplicate_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    by_key: dict[str, RetrievalResult] = {}
    for result in results:
        current = by_key.get(result.chunk_key)
        if current is None or (
            current.expansion_reason != "direct_hit"
            and result.expansion_reason == "direct_hit"
        ):
            by_key[result.chunk_key] = result
    return list(by_key.values())


def sort_by_source_order(results: list[RetrievalResult]) -> list[RetrievalResult]:
    return sorted(
        results,
        key=lambda item: (
            item.version_key,
            item.chunk_index if item.chunk_index is not None else 10**12,
            item.split_index,
        ),
    )


def apply_context_budget(
    results: list[RetrievalResult],
    *,
    context_budget: int,
) -> list[RetrievalResult]:
    selected: list[RetrievalResult] = []
    used = 0
    for result in results:
        cost = len(result.content)
        if selected and used + cost > context_budget:
            continue
        selected.append(result)
        used += cost
    return selected


def finalize_retrieval_results(
    results: list[RetrievalResult],
    *,
    context_budget: int,
) -> list[RetrievalResult]:
    finalized = sort_by_source_order(deduplicate_results(results))
    return apply_context_budget(finalized, context_budget=context_budget)
```

Production rerank fused direct hits truoc structural expansion. Sau expansion, deduplicate va sap
xep source order trong tung document de build context mach lac.

Tests bắt buộc:

```text
- sparse FTS candidate duoc attach Qdrant payload bang qdrant_point_id;
- RRF ket hop dense + sparse va deduplicate theo chunk_key;
- production Retriever luon goi rerank truoc structural expansion;
- hit child lấy parent context;
- list query lấy direct children;
- list query lấy siblings khi phù hợp;
- hit split lấy split neighbor;
- lookup scope theo version_key/parent_chunk_key;
- deduplicate ưu tiên direct_hit;
- source-order đúng;
- context budget không bị vượt.
```
