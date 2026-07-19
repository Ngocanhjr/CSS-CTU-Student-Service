# Mục đích: bổ sung context cha, con, cùng cấp và split neighbor.
# Phần này phụ thuộc mạnh vào payload thực tế. Code dưới đây là khung triển khai.

### Bắt buộc kiểm tra
# - Mọi lookup phải scope ít nhất bằng `version_key`.
# - Sibling nên thêm `parent_chunk_key` khi có.
# - Neighbor phải hydrate content từ PostgreSQL.
# - Không mở rộng toàn bộ document vô điều kiện.

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.s7_hydration import hydrate_langchain_documents
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
