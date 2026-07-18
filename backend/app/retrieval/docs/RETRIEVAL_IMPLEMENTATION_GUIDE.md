# Hướng Dẫn Code Từng File Cho Tầng Retrieval

## 1. Mục tiêu

Tài liệu này hướng dẫn triển khai từng file theo kiến trúc trong `RETRIEVAL_ARCHITECTURE_GUIDE.md`.

Pipeline hoàn chỉnh:

```text
Query Resolver
→ Dense Retrieval (Qdrant)
→ Sparse Retrieval (PostgreSQL FTS)
→ Attach Qdrant Payload
→ RRF Fusion
→ Hydration từ PostgreSQL
→ Rerank
→ Structural Expansion
→ Finalize
→ list[RetrievalResult]
```

> Lưu ý: tên cột SQLAlchemy, tên collection và kiểu payload phải đối chiếu với code thật của dự án trước khi chạy.

---

## 2. Cấu trúc thư mục

```text
chatbot/backend/app/
├── retrieval/
│   ├── __init__.py
│   ├── models.py
│   ├── eligibility.py
│   ├── query_resolver.py
│   ├── dense_retriever.py
│   ├── sparse_retriever.py
│   ├── payload.py
│   ├── fusion.py
│   ├── hydration.py
│   ├── reranker.py
│   ├── expansion.py
│   ├── finalizer.py
│   └── retriever.py
├── embedding/
│   └── embedder.py
├── vectorstore/
│   └── repository.py
├── databases/
│   └── models.py
└── llm/
    └── prompts.py
```

---

# 3. Code từng file

## 3.1. `app/retrieval/__init__.py`

Mục đích: công khai các thành phần chính của package retrieval.

```python
from app.retrieval.models import (
    ExpansionReason,
    QueryDecision,
    RetrievalContext,
    RetrievalResult,
)
from app.retrieval.query_resolver import complete_or_clarify_query
from app.retrieval.retriever import Retriever

__all__ = [
    "ExpansionReason",
    "QueryDecision",
    "RetrievalContext",
    "RetrievalResult",
    "complete_or_clarify_query",
    "Retriever",
]
```

Không đặt business logic trong file này.

---

## 3.2. `app/retrieval/models.py`

Mục đích: định nghĩa kiểu dữ liệu truyền giữa các bước retrieval.

```python
from __future__ import annotations

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

### Quy tắc

- Không dùng dictionary tự do làm output cuối.
- `content` luôn là canonical content từ PostgreSQL.
- Metadata cấu trúc có thể đến từ Qdrant payload.

---

## 3.3. `app/retrieval/eligibility.py`

Mục đích: định nghĩa duy nhất quy tắc tài liệu nào được phép retrieval.

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import models as qmodels

from app.databases.models import Document, DocumentVersion


@dataclass(frozen=True)
class EligibilityContext:
    audience: str = "student"
    document_key: str | None = None
    version_key: str | None = None


class EligibilityPolicy:
    @staticmethod
    def build_postgres_conditions(
        context: EligibilityContext,
    ) -> list[Any]:
        conditions: list[Any] = [
            DocumentVersion.review_status == "approved",
            DocumentVersion.rag_status == "published",
            DocumentVersion.is_latest.is_(True),
        ]

        if context.audience == "student":
            conditions.append(Document.audience_student.is_(True))

        if context.document_key:
            conditions.append(
                Document.document_key == context.document_key
            )

        if context.version_key:
            conditions.append(
                DocumentVersion.version_key == context.version_key
            )

        return conditions

    @staticmethod
    def build_qdrant_filter(
        context: EligibilityContext,
        *,
        chunk_type: str = "child",
    ) -> qmodels.Filter:
        must: list[qmodels.FieldCondition] = [
            qmodels.FieldCondition(
                key="review_status",
                match=qmodels.MatchValue(value="approved"),
            ),
            qmodels.FieldCondition(
                key="rag_status",
                match=qmodels.MatchValue(value="published"),
            ),
            qmodels.FieldCondition(
                key="is_latest",
                match=qmodels.MatchValue(value=True),
            ),
            qmodels.FieldCondition(
                key="chunk_type",
                match=qmodels.MatchValue(value=chunk_type),
            ),
        ]

        if context.audience == "student":
            must.append(
                qmodels.FieldCondition(
                    key="audience_student",
                    match=qmodels.MatchValue(value=True),
                )
            )

        if context.document_key:
            must.append(
                qmodels.FieldCondition(
                    key="document_key",
                    match=qmodels.MatchValue(
                        value=context.document_key
                    ),
                )
            )

        if context.version_key:
            must.append(
                qmodels.FieldCondition(
                    key="version_key",
                    match=qmodels.MatchValue(
                        value=context.version_key
                    ),
                )
            )

        return qmodels.Filter(must=must)
```

### Cần kiểm tra

Tên field trong Qdrant payload phải đúng với dữ liệu upsert thực tế.

---

## 3.4. `app/retrieval/query_resolver.py`

Mục đích: quyết định query có được search hay không.

```python
from __future__ import annotations

from app.retrieval.models import QueryDecision, RetrievalContext


GREETINGS = {
    "hi",
    "hello",
    "chào",
    "xin chào",
    "alo",
}

UNDERSPECIFIED_QUERIES = {
    "điều kiện là gì",
    "hồ sơ gồm gì",
    "nộp ở đâu",
    "cần gì",
    "cần giấy gì",
}


def normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def is_greeting_or_smalltalk(query: str) -> bool:
    return normalize_query(query).lower() in GREETINGS


def complete_or_clarify_query(
    query: str,
    *,
    context: RetrievalContext | None = None,
) -> QueryDecision:
    normalized = normalize_query(query)

    if not normalized:
        return QueryDecision(
            should_search=False,
            query="",
            clarification_question="Vui lòng nhập câu hỏi.",
        )

    if is_greeting_or_smalltalk(normalized):
        return QueryDecision(
            should_search=False,
            query=normalized,
            clarification_question=(
                "Chào bạn, mình là trợ lý hỗ trợ tra cứu thông tin "
                "sinh viên CTU. Bạn muốn hỏi về nội dung nào?"
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
                "Bạn muốn hỏi điều kiện hoặc hồ sơ của thủ tục nào?"
            ),
        )

    resolved_query = normalized
    if is_ambiguous and context.recent_topic:
        resolved_query = f"{normalized} cho {context.recent_topic}"

    return QueryDecision(
        should_search=True,
        query=resolved_query,
        document_key=context.current_document_key,
        version_key=context.current_version_key,
    )
```

### Không nên làm

```python
if "hồ sơ" in query:
    # xem là query mơ hồ
```

Rule này sai với câu rõ nghĩa như `hồ sơ xin bảng điểm gồm gì`.

---

## 3.5. `app/embedding/embedder.py`

Nếu dự án đã có file này, chỉ cần bảo đảm interface rõ ràng.

```python
from __future__ import annotations

from typing import Protocol

from langchain_core.embeddings import Embeddings


class TextEmbedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class LangChainEmbeddingsAdapter(Embeddings):
    def __init__(self, embedder: TextEmbedder) -> None:
        self._embedder = embedder

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return self._embedder.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed_query(text)
```

Nếu `TextEmbedder` trong dự án là class thật, không cần khai báo lại Protocol.

---

## 3.6. `app/vectorstore/repository.py`

Mục đích: gom cấu hình và helper Qdrant cấp thấp.

```python
from __future__ import annotations

from qdrant_client import QdrantClient


DEFAULT_COLLECTION = "ctu_student_documents"
VECTOR_NAME = "embedding"


def get_qdrant_client() -> QdrantClient:
    # Thay bằng config thật của dự án.
    return QdrantClient(url="http://localhost:6333")
```

Có thể bổ sung:

```python
def retrieve_points_by_ids(...):
    ...


def delete_points(...):
    ...


def upsert_points(...):
    ...
```

Không hard-code collection hoặc vector name trong nhiều file.

---

## 3.7. `app/retrieval/dense_retriever.py`

Mục đích: semantic search bằng LangChain Qdrant retriever.

```python
from __future__ import annotations

from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.embedding.embedder import (
    LangChainEmbeddingsAdapter,
    TextEmbedder,
)
from app.retrieval.eligibility import (
    EligibilityContext,
    EligibilityPolicy,
)
from app.vectorstore.repository import (
    DEFAULT_COLLECTION,
    VECTOR_NAME,
)


DEFAULT_TOP_K = 5


def build_dense_retriever(
    *,
    qdrant_client: QdrantClient,
    embedder: TextEmbedder,
    collection_name: str = DEFAULT_COLLECTION,
    top_k: int = DEFAULT_TOP_K,
    audience: str = "student",
    document_key: str | None = None,
    version_key: str | None = None,
) -> VectorStoreRetriever:
    vectorstore = QdrantVectorStore(
        client=qdrant_client,
        collection_name=collection_name,
        embedding=LangChainEmbeddingsAdapter(embedder),
        vector_name=VECTOR_NAME,
    )

    qdrant_filter = EligibilityPolicy.build_qdrant_filter(
        EligibilityContext(
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        ),
        chunk_type="child",
    )

    return vectorstore.as_retriever(
        search_kwargs={
            "k": top_k,
            "filter": qdrant_filter,
        }
    )
```

### Điểm bắt buộc

- `vector_name=VECTOR_NAME`.
- Dense side dùng cùng `EligibilityPolicy` với sparse side.
- Chỉ lấy child chunk cho direct retrieval nếu đó là contract của dự án.

---

## 3.8. `app/retrieval/sparse_retriever.py`

Mục đích: tìm kiếm từ khóa bằng PostgreSQL FTS.

```python
from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
)
from app.retrieval.eligibility import (
    EligibilityContext,
    EligibilityPolicy,
)


async def search_sparse_documents(
    session: AsyncSession,
    *,
    query: str,
    top_k: int,
    audience: str,
    document_key: str | None = None,
    version_key: str | None = None,
) -> list[LangChainDocument]:
    if not query.strip():
        return []

    ts_query = func.websearch_to_tsquery("simple", query)
    search_vector = func.to_tsvector(
        "simple",
        DocumentChunk.content,
    )
    rank = func.ts_rank_cd(
        search_vector,
        ts_query,
    ).label("score")

    eligibility_conditions = (
        EligibilityPolicy.build_postgres_conditions(
            EligibilityContext(
                audience=audience,
                document_key=document_key,
                version_key=version_key,
            )
        )
    )

    statement = (
        select(
            DocumentChunk,
            DocumentVersion,
            Document,
            rank,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id
            == DocumentChunk.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            DocumentChunk.chunk_type == "child",
            DocumentChunk.index_status == "indexed",
            DocumentChunk.qdrant_point_id.is_not(None),
            *eligibility_conditions,
            search_vector.op("@@")(ts_query),
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
```

### Migration GIN index tham khảo

```sql
CREATE INDEX IF NOT EXISTS ix_document_chunks_content_fts
ON document_chunks
USING GIN (to_tsvector('simple', content));
```

Tên bảng phải sửa theo schema thật.

---

## 3.9. `app/retrieval/payload.py`

Mục đích: lấy Qdrant flat payload cho cả dense và sparse candidate.

```python
from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
from qdrant_client import QdrantClient


def attach_point_id_from_document(
    docs: list[LangChainDocument],
) -> list[LangChainDocument]:
    enriched: list[LangChainDocument] = []

    for doc in docs:
        metadata = dict(doc.metadata or {})
        metadata.setdefault(
            "qdrant_point_id",
            metadata.get("_id"),
        )

        enriched.append(
            LangChainDocument(
                page_content=doc.page_content,
                metadata=metadata,
            )
        )

    return enriched


def attach_qdrant_payloads(
    client: QdrantClient,
    *,
    collection_name: str,
    docs: list[LangChainDocument],
) -> list[LangChainDocument]:
    point_ids = [
        doc.metadata.get("qdrant_point_id")
        for doc in docs
        if doc.metadata.get("qdrant_point_id") is not None
    ]

    if not point_ids:
        return docs

    records = client.retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=True,
        with_vectors=False,
    )

    payload_by_id = {
        str(record.id): dict(record.payload or {})
        for record in records
    }

    enriched_docs: list[LangChainDocument] = []

    for doc in docs:
        point_id = doc.metadata.get("qdrant_point_id")
        payload = payload_by_id.get(str(point_id), {})

        enriched_docs.append(
            LangChainDocument(
                page_content=doc.page_content,
                metadata={
                    **doc.metadata,
                    **payload,
                    "qdrant_point_id": point_id,
                },
            )
        )

    return enriched_docs
```

### Cần test

- Candidate không có point ID không làm hàm crash.
- Payload được merge nhưng vẫn giữ `_score` của candidate.
- `chunk_key` xuất hiện trước fusion.

---

## 3.10. `app/retrieval/fusion.py`

Mục đích: hợp nhất dense và sparse bằng Reciprocal Rank Fusion.

```python
from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument


def reciprocal_rank_fusion(
    dense_docs: list[LangChainDocument],
    sparse_docs: list[LangChainDocument],
    *,
    limit: int,
    rank_constant: int = 60,
) -> list[LangChainDocument]:
    docs_by_key: dict[str, LangChainDocument] = {}
    fusion_scores: dict[str, float] = {}

    for ranked_docs in (dense_docs, sparse_docs):
        for rank, doc in enumerate(ranked_docs, start=1):
            chunk_key = doc.metadata.get("chunk_key")
            if not chunk_key:
                continue

            key = str(chunk_key)
            docs_by_key.setdefault(key, doc)
            fusion_scores[key] = (
                fusion_scores.get(key, 0.0)
                + 1.0 / (rank_constant + rank)
            )

    ordered_keys = sorted(
        fusion_scores,
        key=fusion_scores.get,
        reverse=True,
    )[:limit]

    return [
        LangChainDocument(
            page_content=docs_by_key[key].page_content,
            metadata={
                **docs_by_key[key].metadata,
                "_score": fusion_scores[key],
            },
        )
        for key in ordered_keys
    ]
```

### Ý nghĩa

RRF không so sánh trực tiếp dense score và sparse score vì hai score có thang đo khác nhau. Nó kết hợp dựa trên thứ hạng.

---

## 3.11. `app/retrieval/hydration.py`

Mục đích: lấy canonical content từ PostgreSQL và chuyển thành `RetrievalResult`.

```python
from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import DocumentChunk
from app.retrieval.models import ExpansionReason, RetrievalResult


def build_citation(
    *,
    source_file: str,
    page_start: int | None,
    page_end: int | None,
    heading_path: list[str] | None = None,
) -> str:
    if page_start is not None and page_end is not None:
        if page_start == page_end:
            return f"{source_file}, trang {page_start}"
        return f"{source_file}, trang {page_start}-{page_end}"

    if heading_path:
        return f"{source_file}, mục {heading_path[-1]}"

    return source_file


async def hydrate_langchain_documents(
    session: AsyncSession,
    docs: list[LangChainDocument],
    *,
    expansion_reason: ExpansionReason = "direct_hit",
) -> list[RetrievalResult]:
    results: list[RetrievalResult] = []

    for doc in docs:
        metadata = dict(doc.metadata or {})
        db_chunk_id = metadata.get("postgres_chunk_id")

        if db_chunk_id is None:
            continue

        chunk = await session.get(
            DocumentChunk,
            int(db_chunk_id),
        )
        if chunk is None:
            continue

        parent_chunk_key = metadata.get("parent_chunk_key")
        if (
            parent_chunk_key is None
            and chunk.parent_chunk_id is not None
        ):
            parent = await session.get(
                DocumentChunk,
                chunk.parent_chunk_id,
            )
            if parent is not None:
                parent_chunk_key = parent.chunk_key

        heading_path = (
            metadata.get("heading_path")
            or getattr(chunk, "heading_path", None)
            or []
        )
        item_path = metadata.get("item_path") or []

        page_start = metadata.get("page_start")
        if page_start is None:
            page_start = getattr(chunk, "page_start", None)

        page_end = metadata.get("page_end")
        if page_end is None:
            page_end = getattr(chunk, "page_end", None)

        source_file = metadata.get("source_file", "")
        logical_item_key = metadata.get("logical_item_key")
        logical_item_keys = (
            metadata.get("logical_item_keys")
            or ([logical_item_key] if logical_item_key else [])
        )

        results.append(
            RetrievalResult(
                postgres_chunk_id=int(db_chunk_id),
                postgres_parent_chunk_id=(
                    metadata.get("postgres_parent_chunk_id")
                    or chunk.parent_chunk_id
                ),
                document_key=metadata.get("document_key", ""),
                version_key=metadata.get("version_key", ""),
                chunk_key=metadata.get(
                    "chunk_key",
                    chunk.chunk_key,
                ),
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
                legal_unit_type=metadata.get(
                    "legal_unit_type",
                    "none",
                ),
                block_type=metadata.get("block_type"),
                logical_item_key=logical_item_key,
                logical_item_keys=logical_item_keys,
                parent_item_key=metadata.get("parent_item_key"),
                logical_table_key=metadata.get(
                    "logical_table_key"
                ),
                logical_code_key=metadata.get(
                    "logical_code_key"
                ),
                split_index=int(metadata.get("split_index", 0)),
                split_count=int(metadata.get("split_count", 1)),
                chunk_index=metadata.get("chunk_index"),
                item_marker=metadata.get("item_marker"),
                item_level=metadata.get("item_level"),
                expansion_reason=expansion_reason,
            )
        )

    return results
```

### Tối ưu sau này

Skeleton trên gọi DB từng chunk. Production nên batch query bằng `WHERE id IN (...)` để tránh N+1 query.

---

## 3.12. `app/retrieval/reranker.py`

Mục đích: cung cấp interface rerank độc lập với vendor.

```python
from __future__ import annotations

from typing import Protocol

from app.retrieval.models import RetrievalResult


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        ...


class IdentityReranker:
    """Chỉ dùng cho test hoặc giai đoạn chưa tích hợp model rerank."""

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        del query
        return results
```

Khi tích hợp NVIDIA rerank hoặc cross-encoder, tạo class mới implement cùng interface.

---

## 3.13. `app/retrieval/expansion.py`

Mục đích: bổ sung context cha, con, cùng cấp và split neighbor.

Phần này phụ thuộc mạnh vào payload thực tế. Code dưới đây là khung triển khai.

```python
from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.hydration import hydrate_langchain_documents
from app.retrieval.models import RetrievalResult
from langchain_core.documents import Document as LangChainDocument


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
    return any(
        pattern in normalized
        for pattern in LIST_QUERY_PATTERNS
    )


def _record_to_document(record) -> LangChainDocument:
    payload = dict(record.payload or {})
    return LangChainDocument(
        page_content="",
        metadata={
            **payload,
            "qdrant_point_id": record.id,
        },
    )


def _retrieve_by_filter(
    client: QdrantClient,
    *,
    collection_name: str,
    query_filter: qmodels.Filter,
    limit: int = 20,
) -> list[LangChainDocument]:
    records, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [_record_to_document(record) for record in records]


async def find_parent_item(
    session: AsyncSession,
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    hit: RetrievalResult,
) -> list[RetrievalResult]:
    if not hit.parent_item_key:
        return []

    docs = _retrieve_by_filter(
        qdrant_client,
        collection_name=collection_name,
        query_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="version_key",
                    match=qmodels.MatchValue(value=hit.version_key),
                ),
                qmodels.FieldCondition(
                    key="logical_item_key",
                    match=qmodels.MatchValue(
                        value=hit.parent_item_key
                    ),
                ),
            ]
        ),
    )
    return await hydrate_langchain_documents(
        session,
        docs,
        expansion_reason="parent_context",
    )


async def find_direct_children(
    session: AsyncSession,
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    hit: RetrievalResult,
) -> list[RetrievalResult]:
    if not hit.logical_item_key:
        return []

    docs = _retrieve_by_filter(
        qdrant_client,
        collection_name=collection_name,
        query_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="version_key",
                    match=qmodels.MatchValue(value=hit.version_key),
                ),
                qmodels.FieldCondition(
                    key="parent_item_key",
                    match=qmodels.MatchValue(
                        value=hit.logical_item_key
                    ),
                ),
            ]
        ),
    )
    return await hydrate_langchain_documents(
        session,
        docs,
        expansion_reason="child_expansion",
    )


async def find_siblings(
    session: AsyncSession,
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    hit: RetrievalResult,
) -> list[RetrievalResult]:
    if not hit.parent_item_key:
        return []

    must = [
        qmodels.FieldCondition(
            key="version_key",
            match=qmodels.MatchValue(value=hit.version_key),
        ),
        qmodels.FieldCondition(
            key="parent_item_key",
            match=qmodels.MatchValue(value=hit.parent_item_key),
        ),
    ]

    if hit.parent_chunk_key:
        must.append(
            qmodels.FieldCondition(
                key="parent_chunk_key",
                match=qmodels.MatchValue(
                    value=hit.parent_chunk_key
                ),
            )
        )

    docs = _retrieve_by_filter(
        qdrant_client,
        collection_name=collection_name,
        query_filter=qmodels.Filter(must=must),
    )
    return await hydrate_langchain_documents(
        session,
        docs,
        expansion_reason="sibling_expansion",
    )


async def find_split_neighbors(
    session: AsyncSession,
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    hit: RetrievalResult,
) -> list[RetrievalResult]:
    if not hit.logical_item_key or hit.split_count <= 1:
        return []

    docs = _retrieve_by_filter(
        qdrant_client,
        collection_name=collection_name,
        query_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="version_key",
                    match=qmodels.MatchValue(value=hit.version_key),
                ),
                qmodels.FieldCondition(
                    key="logical_item_key",
                    match=qmodels.MatchValue(
                        value=hit.logical_item_key
                    ),
                ),
            ]
        ),
    )

    # Giữ các phần gần direct hit. Có thể đổi thành lấy toàn group nếu budget cho phép.
    neighbor_docs = [
        doc
        for doc in docs
        if abs(
            int(doc.metadata.get("split_index", 0))
            - hit.split_index
        ) <= 1
    ]

    return await hydrate_langchain_documents(
        session,
        neighbor_docs,
        expansion_reason="split_neighbor",
    )


async def expand_structural_context(
    session: AsyncSession,
    *,
    qdrant_client: QdrantClient,
    collection_name: str,
    direct_hits: list[RetrievalResult],
    query: str,
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
                )
            )

        if list_query and hit.logical_item_key:
            candidates.extend(
                await find_direct_children(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                )
            )

        if list_query and hit.parent_item_key:
            candidates.extend(
                await find_siblings(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                )
            )

        if hit.split_count > 1 and hit.logical_item_key:
            candidates.extend(
                await find_split_neighbors(
                    session,
                    qdrant_client=qdrant_client,
                    collection_name=collection_name,
                    hit=hit,
                )
            )

    return candidates
```

### Bắt buộc kiểm tra

- Mọi lookup phải scope ít nhất bằng `version_key`.
- Sibling nên thêm `parent_chunk_key` khi có.
- Neighbor phải hydrate content từ PostgreSQL.
- Không mở rộng toàn bộ document vô điều kiện.

---

## 3.14. `app/retrieval/finalizer.py`

Mục đích: deduplicate, source-order và context budget.

```python
from __future__ import annotations

from app.retrieval.models import RetrievalResult


def deduplicate_results(
    results: list[RetrievalResult],
) -> list[RetrievalResult]:
    by_key: dict[str, RetrievalResult] = {}

    for result in results:
        current = by_key.get(result.chunk_key)

        if current is None:
            by_key[result.chunk_key] = result
            continue

        if (
            current.expansion_reason != "direct_hit"
            and result.expansion_reason == "direct_hit"
        ):
            by_key[result.chunk_key] = result

    return list(by_key.values())


def sort_by_source_order(
    results: list[RetrievalResult],
) -> list[RetrievalResult]:
    return sorted(
        results,
        key=lambda item: (
            item.version_key,
            item.chunk_index
            if item.chunk_index is not None
            else 10**12,
            item.split_index,
        ),
    )


def apply_character_budget(
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
    deduplicated = deduplicate_results(results)
    ordered = sort_by_source_order(deduplicated)
    return apply_character_budget(
        ordered,
        context_budget=context_budget,
    )
```

Nếu dùng token budget, thay `len(content)` bằng tokenizer phù hợp.

---

## 3.15. `app/retrieval/retriever.py`

Mục đích: điều phối toàn bộ pipeline retrieval.

```python
from __future__ import annotations

from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding.embedder import TextEmbedder
from app.retrieval.dense_retriever import (
    DEFAULT_TOP_K,
    build_dense_retriever,
)
from app.retrieval.expansion import expand_structural_context
from app.retrieval.finalizer import finalize_retrieval_results
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.hydration import hydrate_langchain_documents
from app.retrieval.models import RetrievalResult
from app.retrieval.payload import (
    attach_point_id_from_document,
    attach_qdrant_payloads,
)
from app.retrieval.reranker import Reranker
from app.retrieval.sparse_retriever import (
    search_sparse_documents,
)
from app.vectorstore.repository import DEFAULT_COLLECTION


class Retriever:
    def __init__(
        self,
        *,
        embedder: TextEmbedder,
        qdrant_client: QdrantClient,
        reranker: Reranker,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        self.reranker = reranker
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

        dense_retriever = build_dense_retriever(
            qdrant_client=self.qdrant_client,
            embedder=self.embedder,
            collection_name=self.collection_name,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )

        dense_docs = dense_retriever.invoke(query)
        dense_docs = attach_point_id_from_document(dense_docs)
        dense_docs = attach_qdrant_payloads(
            self.qdrant_client,
            collection_name=self.collection_name,
            docs=dense_docs,
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

        fused_docs = reciprocal_rank_fusion(
            dense_docs,
            sparse_docs,
            limit=top_k,
        )

        direct_hits = await hydrate_langchain_documents(
            session,
            fused_docs,
            expansion_reason="direct_hit",
        )

        reranked_hits = self.reranker.rerank(
            query,
            direct_hits,
        )

        expanded = await expand_structural_context(
            session,
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
            direct_hits=reranked_hits,
            query=query,
        )

        return finalize_retrieval_results(
            expanded,
            context_budget=context_budget,
        )
```

### Trách nhiệm không thuộc `Retriever`

- Greeting/smalltalk.
- Clarification question.
- Prompt construction.
- LLM answer generation.

---

## 3.16. Tầng orchestration hoặc API

Ví dụ cách gọi resolver và retriever:

```python
from app.retrieval.models import RetrievalContext
from app.retrieval.query_resolver import complete_or_clarify_query


async def handle_question(
    *,
    question: str,
    session,
    retriever,
    retrieval_context: RetrievalContext | None = None,
):
    decision = complete_or_clarify_query(
        question,
        context=retrieval_context,
    )

    if not decision.should_search:
        return {
            "answer": decision.clarification_question,
            "retrieval_results": [],
        }

    results = await retriever.search_resolved_query(
        session,
        query=decision.query,
        top_k=5,
        audience="student",
        document_key=decision.document_key,
        version_key=decision.version_key,
    )

    context_text = "\n\n".join(
        (
            f"[{result.chunk_key}]\n"
            f"{result.content}\n"
            f"Nguồn: {result.citation}"
        )
        for result in results
    )

    return {
        "resolved_query": decision.query,
        "context": context_text,
        "retrieval_results": results,
    }
```

Sau đó tầng LLM mới nhận `context` và `resolved_query` để sinh câu trả lời.

---

# 4. Thứ tự triển khai khuyến nghị

## Giai đoạn 1: Retrieval tối thiểu

```text
models.py
eligibility.py
query_resolver.py
dense_retriever.py
payload.py
hydration.py
finalizer.py
retriever.py
```

Mục tiêu: dense search có filter, payload, canonical content và citation.

## Giai đoạn 2: Hybrid retrieval

```text
sparse_retriever.py
fusion.py
reranker.py
```

Mục tiêu: dense + sparse + RRF + rerank.

## Giai đoạn 3: Structural retrieval

```text
expansion.py
```

Mục tiêu: parent, children, siblings và split neighbor.

---

# 5. Test tối thiểu cho từng file

## `test_query_resolver.py`

- Greeting không search.
- Blank query không search.
- Query mơ hồ không context trả clarification.
- Query mơ hồ có recent topic được rewrite.
- Document/version context được giữ lại.

## `test_eligibility.py`

- Student có approved/published/is_latest/audience_student.
- Admin vẫn có approved/published/is_latest.
- Document/version filter được thêm đúng.

## `test_dense_retriever.py`

- Dùng `VECTOR_NAME`.
- Có filter trong `search_kwargs`.
- `k` đúng.

## `test_sparse_retriever.py`

- Blank query trả `[]`.
- Dùng `EligibilityPolicy`.
- Candidate có `postgres_chunk_id` và `qdrant_point_id`.

## `test_payload.py`

- `_id` được chuyển thành `qdrant_point_id`.
- Flat payload được merge.
- Không mất `_score`.

## `test_fusion.py`

- Dense và sparse trùng chunk được deduplicate.
- Chunk xuất hiện ở cả hai danh sách có rank tốt hơn.
- Candidate thiếu `chunk_key` bị bỏ qua an toàn.

## `test_hydration.py`

- Content lấy từ PostgreSQL, không lấy `page_content`.
- Citation có page hoặc heading.
- Parent key fallback qua parent row.

## `test_expansion.py`

- Child hit lấy parent.
- List query lấy children.
- List query lấy sibling.
- Split chunk lấy neighbor.
- Lookup có `version_key` scope.

## `test_finalizer.py`

- Direct hit được ưu tiên khi duplicate.
- Source order đúng.
- Budget không vượt giới hạn.

## `test_retriever.py`

- Blank resolved query không gọi Qdrant.
- Flow đúng thứ tự: dense/sparse → payload → fusion → hydration → rerank → expansion → finalize.

---

# 6. Các lỗi thường gặp

## 6.1. `QdrantVectorStoreError`

Nguyên nhân thường gặp: không truyền named vector.

```python
vector_name=VECTOR_NAME
```

## 6.2. Dense result có score nhưng thiếu metadata

Nguyên nhân: payload Qdrant là flat trong khi LangChain mong `metadata` lồng.

Xử lý:

```text
attach_point_id_from_document()
→ attach_qdrant_payloads()
```

## 6.3. Fusion lỗi `chunk_key`

Nguyên nhân: chưa attach payload trước fusion.

## 6.4. Content rỗng hoặc cũ

Nguyên nhân: dùng Qdrant payload hoặc `page_content` làm canonical source.

Xử lý: hydrate bằng `postgres_chunk_id` từ PostgreSQL.

## 6.5. Dense và sparse cho ra hai tập eligibility khác nhau

Nguyên nhân: hai phía tự hard-code filter riêng.

Xử lý: cả hai phải gọi `EligibilityPolicy`.

## 6.6. Expansion nối nhầm section hoặc version

Nguyên nhân: lookup chỉ theo `logical_item_key`.

Xử lý: luôn thêm `version_key`, và thêm `parent_chunk_key` khi có.

---

# 7. Checklist hoàn thành

- [ ] Query resolver xử lý greeting và query mơ hồ.
- [ ] Dense retrieval dùng named vector.
- [ ] Dense và sparse dùng cùng eligibility policy.
- [ ] Dense và sparse đều có full Qdrant payload trước fusion.
- [ ] RRF deduplicate theo `chunk_key`.
- [ ] Canonical content lấy từ PostgreSQL.
- [ ] Rerank chạy trước structural expansion.
- [ ] Expansion có scope theo version/parent.
- [ ] Finalizer ưu tiên direct hit.
- [ ] Source order đúng.
- [ ] Context budget được áp dụng.
- [ ] Citation có source và page/heading.
- [ ] Unit test pass.
