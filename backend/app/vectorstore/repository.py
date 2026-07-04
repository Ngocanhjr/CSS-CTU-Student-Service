"""Qdrant CRUD operations for vector store.

Functions:
    ensure_collection: Create Qdrant collection if not exists.
    point_id_from_chunk_key: Generate stable UUID5 from chunk_key.
    build_context_filter: Convert RetrievalFilter to Qdrant Filter.
    build_payload: Build Qdrant payload dict from document + chunk.
    upsert_points: Upsert chunk vectors with payload.
    search_points: Search top-k chunks with optional metadata filter.
"""


import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
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


COLLECTION_NAME = "ctu_chunks_test"
VECTOR_NAME = "embedding"

def point_id_from_chunk_key(chunk_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_key))

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
    
    collections = client.get_collections().collections
    if collection_name in [c.name for c in collections]:
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

    conditions = []

    if filters.department:
        conditions.append(
            FieldCondition(
                key="department",
                match=MatchValue(value=filters.department),
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
    if filters.chunk_type:
        conditions.append(
            FieldCondition(
                key="chunk_type",
                match=MatchValue(value=filters.chunk_type),
            )
        )

    if not conditions:
        return None

    return Filter(must=conditions)

def build_payload(document: MarkdownDocument, chunk: Chunk) -> dict:
    metadata = document.metadata
    payload = QdrantChunkPayload(
        document_key=chunk.document_key,
        version_key=chunk.version_key,
        title=metadata.title,
        department=metadata.department,
        document_type=metadata.document_type,
        domain=metadata.domain,
        chunk_key=chunk.chunk_key,
        parent_chunk_key=chunk.parent_chunk_key,
        chunk_type=chunk.chunk_type,
        heading_path=chunk.heading_path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        content=chunk.content,
    )
    return payload.model_dump()

def upsert_chunks(
    client: QdrantClient,
    document: MarkdownDocument,
    chunks: list[Chunk],
    vectors: list[list[float]],
    collection_name: str = COLLECTION_NAME
    ) ->   int:
    
    if not chunks:
        return 0
    
    ensure_collection(client, collection_name=collection_name, vector_size=len(vectors[0]))
    
    points = [
        PointStruct(
            id=point_id_from_chunk_key(chunk.chunk_key),
            vector={VECTOR_NAME: vector},
            payload=build_payload(document, chunk),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    
    client.upsert(
        collection_name=collection_name,
        points=points,
    )
    return len(points)

def search_points(
    client: QdrantClient,
    *,
    query_vector: list[float],
    collection_name: str = COLLECTION_NAME,
    top_k: int = 5,
    filters: RetrievalFilter | None = None,
    ) -> list[QdrantSearchResult]:
    
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=VECTOR_NAME,
        query_filter=build_context_filter(filters),
        limit=top_k,
        with_payload=True,
    )
    
    return [
        QdrantSearchResult(
            score=result.score,
            payload=result.payload or {},
        )
        for result in response.points
    ]
