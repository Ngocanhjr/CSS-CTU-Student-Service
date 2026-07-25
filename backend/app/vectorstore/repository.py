# Chứa các thao tác chính với Qdrant:

# Tạo collection
# Tạo point ID
# Build filter
# Build payload
# Upsert vector
# Search vector: tìm kiếm vector theo query vector và filter


"""Qdrant CRUD operations for vector store.

Functions:
    ensure_collection: Create Qdrant collection if not exists.
    make_point_id: Generate stable UUID5 from version_key and chunk_key.
    build_context_filter: Convert RetrievalFilter to Qdrant Filter.
    build_payload: Build Qdrant payload dict from document + chunk.
    upsert_points: Upsert chunk vectors with payload.
    search_points: Search top-k chunks with optional metadata filter.
"""


import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.ingestion.markdown_reader import MarkdownDocument
from app.schemas.chunks import Chunk
from app.vectorstore.models import (
    QdrantChunkPayload,
    QdrantSearchResult,
    RetrievalFilter,
)


COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "ctu_chunks_bge_m3")
VECTOR_NAME = "embedding"
VECTOR_SIZE = 1024

def make_point_id(version_key: str, chunk_key: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"ctu-student-service/chunk/{version_key}/{chunk_key}",
        )
    )

def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str = COLLECTION_NAME,
    vector_size: int) -> None:

    """
    Ensure a collection exists in Qdrant. Create if not exists.
    
    Args:
        client (QdrantClient): The Qdrant client instance.
        collection_name (str): The name of the collection to check or create.
        vector_size (int): The size of the vectors to be stored in the collection.
        
    Returns:
        None
    """
    
    if vector_size != VECTOR_SIZE:
        raise ValueError(f"BGE-M3 vector phải có dimension {VECTOR_SIZE}")

    collections = client.get_collections().collections
    if collection_name in [c.name for c in collections]:
        info = client.get_collection(collection_name=collection_name)
        vectors = info.config.params.vectors
        named_vector = vectors.get(VECTOR_NAME) if isinstance(vectors, dict) else vectors
        distance = getattr(getattr(named_vector, "distance", None), "name", None)
        if getattr(named_vector, "size", None) != vector_size or distance != "COSINE":
            raise ValueError(
                f"Qdrant collection {collection_name} không khớp "
                f"{VECTOR_NAME}/{vector_size}/COSINE"
            )
        return
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            VECTOR_NAME: VectorParams(size=vector_size, distance=Distance.COSINE)
        },
    )
    
def build_context_filter(filters: RetrievalFilter | None = None) -> Filter | None:
    if filters is None:
        filters = RetrievalFilter()

    # Dense retrieval always starts from the same eligibility domain as PostgreSQL.
    conditions = [
        FieldCondition(key="review_status", match=MatchValue(value="approved")),
        FieldCondition(key="rag_status", match=MatchValue(value="indexed")),
        FieldCondition(key="audience_student", match=MatchValue(value=True)),
        FieldCondition(key="chunk_type", match=MatchValue(value="child")),
    ]

    if filters.audience:
        conditions.append(
            FieldCondition(
                key="audience",
                match=MatchValue(value=filters.audience),
            )
        )
    if filters.document_type:
        conditions.append(
            FieldCondition(
                key="document_type",
                match=MatchValue(value=filters.document_type),
            )
        )
    if filters.domain:
        conditions.append(
            FieldCondition(
                key="domain",
                match=MatchValue(value=filters.domain),
            )
        )
    if filters.document_key:
        conditions.append(
            FieldCondition(
                key="document_key",
                match=MatchValue(value=filters.document_key),
            )
        )
    if filters.version_key:
        conditions.append(
            FieldCondition(
                key="version_key",
                match=MatchValue(value=filters.version_key),
            )
        )
    if filters.chunk_type and filters.chunk_type != "child":
        raise ValueError("Student retrieval chỉ hỗ trợ child chunks")
    if filters.chunk_type:
        conditions.append(
            FieldCondition(
                key="chunk_type",
                match=MatchValue(value=filters.chunk_type),
            )
        )
    if filters.review_status:
        conditions.append(
            FieldCondition(
                key="review_status",
                match=MatchValue(value=filters.review_status),
            )
        )
    if filters.rag_status:
        conditions.append(
            FieldCondition(
                key="rag_status",
                match=MatchValue(value=filters.rag_status),
            )
        )
    if filters.audience:
        conditions.append(
            FieldCondition(
                key="audience",
                match=MatchValue(value=filters.audience),
            )
        )

    if not conditions:
        return None

    return Filter(must=conditions)

def build_payload(
    document: MarkdownDocument,
    chunk: Chunk,
    *,
    postgres_chunk_id: int = 0,
    postgres_parent_chunk_id: int | None = None,
    review_status: str | None = None,
    rag_status: str | None = None,
) -> dict:
    metadata = document.metadata
    payload = QdrantChunkPayload(
        document_key=chunk.document_key,
        version_key=chunk.version_key,
        title=metadata.title,
        source_file=metadata.canonical_markdown_path or metadata.source_path,
        source_url=metadata.source_url or None,
        document_type=metadata.document_type,
        domain=metadata.domain,
        audience=list(metadata.audience),
        audience_student="sinh_vien" in metadata.audience,
        review_status=review_status or metadata.review_status,
        rag_status=rag_status or metadata.rag_status,
        is_latest=metadata.is_latest,
        chunk_key=chunk.chunk_key,
        parent_chunk_key=chunk.parent_chunk_key,
        chunk_type=chunk.chunk_type,
        heading_path=chunk.heading_path,
        item_path=list(chunk.metadata.get("item_path", [])),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        chunk_index=chunk.chunk_index,
        postgres_chunk_id=postgres_chunk_id,
        postgres_parent_chunk_id=postgres_parent_chunk_id,
        block_type=chunk.metadata.get("block_type", "paragraph"),
        legal_unit_type=chunk.metadata.get("legal_unit_type", "none"),
        logical_item_key=chunk.metadata.get("logical_item_key"),
        parent_item_key=chunk.metadata.get("parent_item_key"),
        logical_table_key=chunk.metadata.get("logical_table_key"),
        logical_code_key=chunk.metadata.get("logical_code_key"),
        logical_item_keys=list(chunk.metadata.get("logical_item_keys", [])),
        split_index=int(chunk.metadata.get("split_index", 0)),
        split_count=int(chunk.metadata.get("split_count", 1)),
        item_marker=chunk.metadata.get("item_marker"),
        item_level=chunk.metadata.get("item_level"),
    )
    return payload.model_dump()

# update hoặc insert chunks vào Qdrant
def upsert_chunks(
    client: QdrantClient,
    document: MarkdownDocument,
    chunks: list[Chunk],
    vectors: list[list[float]],
    collection_name: str = COLLECTION_NAME,
    postgres_ids: dict[str, tuple[int, int | None]] | None = None,
    review_status: str | None = None,
    rag_status: str | None = None,
    ) ->   int:
    
    if not chunks:
        return 0
    if any(chunk.chunk_type != "child" for chunk in chunks):
        raise ValueError("Qdrant chỉ nhận child chunks")
    if len(chunks) != len(vectors):
        raise ValueError("Số vector phải bằng số child chunks")
    if not postgres_ids or any(
        chunk.chunk_key not in postgres_ids or postgres_ids[chunk.chunk_key][0] <= 0
        for chunk in chunks
    ):
        raise ValueError("Qdrant point phải có postgres_chunk_id")
    
    ensure_collection(client, collection_name=collection_name, vector_size=len(vectors[0]))

    points = [
        PointStruct(
            id=make_point_id(chunk.version_key, chunk.chunk_key),
            vector={VECTOR_NAME: vector},
            payload=build_payload(
                document,
                chunk,
                postgres_chunk_id=(postgres_ids or {}).get(chunk.chunk_key, (0, None))[0],
                postgres_parent_chunk_id=(postgres_ids or {}).get(chunk.chunk_key, (0, None))[1],
                review_status=review_status,
                rag_status=rag_status,
            ),
        )
    ]
    
    client.upsert(
        collection_name=collection_name,
        points=points,
    )
    return len(points)


def delete_points_by_version(
    client: QdrantClient,
    *,
    version_key: str,
    collection_name: str = COLLECTION_NAME,
) -> None:
    collections = client.get_collections().collections
    if collection_name not in {collection.name for collection in collections}:
        return

    client.delete(
        collection_name=collection_name,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="version_key",
                        match=MatchValue(value=version_key),
                    )
                ]
            )
        ),
    )

# 
def search_points(
    client: QdrantClient,
    *,
    query_vector: list[float],
    collection_name: str = COLLECTION_NAME,
    top_k: int = 5,
    filters: RetrievalFilter | None = None,
    query_filter: Filter | None = None,
    ) -> list[QdrantSearchResult]:
    if filters is not None and query_filter is not None:
        raise ValueError("Pass either filters or query_filter, not both")

    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=VECTOR_NAME,
        query_filter=query_filter or build_context_filter(filters),
        limit=top_k,
        with_payload=True,
    )
    
    return [
        QdrantSearchResult(
            point_id=str(result.id),
            score=result.score,
            payload=result.payload or {},
        )
        for result in response.points
    ]
