"""Admin debug services for inspecting chunks and vectors."""

from __future__ import annotations

import time

from qdrant_client.http.exceptions import UnexpectedResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.chunks import DocumentChunk
from app.databases.models.documents import DocumentVersion
from app.embedding.embedder import embed_query
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import COLLECTION_NAME, VECTOR_NAME


async def get_chunks_debug(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Get all chunks for a document version."""

    # Verify document version exists
    version = await session.get(DocumentVersion, document_version_id)
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")

    # Get chunks
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == document_version_id)
        .order_by(DocumentChunk.id)
    )
    chunks = result.scalars().all()

    parent_count = sum(1 for c in chunks if c.chunk_type == "parent")
    child_count = sum(1 for c in chunks if c.chunk_type == "child")

    return {
        "document_version_id": document_version_id,
        "total_chunks": len(chunks),
        "parent_chunks": parent_count,
        "child_chunks": child_count,
        "chunks": [
            {
                "id": c.id,
                "chunk_key": c.chunk_key,
                "chunk_type": c.chunk_type,
                "parent_chunk_key": c.parent.chunk_key if c.parent else None,
                "heading_path": c.heading_path or [],
                "page_start": c.page_start,
                "page_end": c.page_end,
                "token_count": c.token_count,
                "content_preview": (c.content[:150] + "...") if c.content and len(c.content) > 150 else (c.content or ""),
                "has_embedding": c.qdrant_point_id is not None,
            }
            for c in chunks
        ],
    }


async def get_vectors_debug(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Get vectors from Qdrant for a document version."""

    # Verify document version exists
    version = await session.get(DocumentVersion, document_version_id)
    if not version:
        raise LookupError(f"Document version {document_version_id} not found")

    client = get_qdrant_client()

    # Scroll through all points with matching version_key
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter={
            "must": [
                {"key": "version_key", "match": {"value": version.version_key}}
            ]
        },
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )

    return {
        "document_version_id": document_version_id,
        "collection": COLLECTION_NAME,
        "total_vectors": len(points),
        "vectors": [
            {
                "point_id": str(p.id),
                "chunk_key": p.payload.get("chunk_key", "") if p.payload else "",
                "score": None,
                "payload": p.payload or {},
            }
            for p in points
        ],
    }


async def search_test(
    query: str,
    top_k: int = 5,
    department_id: int | None = None,
) -> dict:
    """Test vector search without LLM generation."""

    # Embed query
    embed_start = time.perf_counter()
    query_vector = embed_query(query)
    embed_time = int((time.perf_counter() - embed_start) * 1000)

    # Search Qdrant
    client = get_qdrant_client()

    search_filter_conditions = [
        {"key": "rag_status", "match": {"value": "published"}}
    ]

    if department_id:
        search_filter_conditions.append(
            {"key": "department_id", "match": {"value": department_id}}
        )

    search_start = time.perf_counter()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        using=VECTOR_NAME,
        query_filter={"must": search_filter_conditions},
        limit=top_k,
        with_payload=True,
    )
    search_time = int((time.perf_counter() - search_start) * 1000)

    return {
        "query": query,
        "embedding_time_ms": embed_time,
        "search_time_ms": search_time,
        "results": [
            {
                "chunk_key": r.payload.get("chunk_key", "") if r.payload else "",
                "document_version_id": r.payload.get("postgres_chunk_id") if r.payload else None,
                "title": r.payload.get("title", "") if r.payload else "",
                "score": round(r.score, 4),
                "content_preview": (r.payload.get("content", "") or "")[:200] if r.payload else "",
            }
            for r in results.points
        ],
    }
