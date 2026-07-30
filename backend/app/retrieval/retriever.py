"""Retrieval service for RAG chat.

Wraps vectorstore search with timing and response formatting.
"""

import time

from app.embedding.embedder import embed_query
from app.vectorstore.models import RetrievalFilter
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import search_points


def retrieve_relevant_chunks(
    query: str,
    *,
    top_k: int = 5,
    filters: dict | None = None,
) -> dict:
    """
    Search Qdrant for relevant chunks based on query.

    Args:
        query: User's question text
        top_k: Number of chunks to retrieve
        filters: Optional filters (document_type, domain)

    Returns:
        dict with 'chunks' list and 'retrieval_time_ms'
    """
    start = time.perf_counter()

    # 1. Embed the query
    query_vector = embed_query(query)

    # 2. Build retrieval filter
    retrieval_filter = RetrievalFilter(
        document_type=filters.get("document_type") if filters else None,
        domain=filters.get("domain") if filters else None,
    )

    # 3. Search Qdrant
    client = get_qdrant_client()
    results = search_points(
        client,
        query_vector=query_vector,
        top_k=top_k,
        filters=retrieval_filter,
    )

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # 4. Format results
    chunks = []
    for hit in results:
        payload = hit.payload
        chunks.append({
            "chunk_key": payload.get("chunk_key", ""),
            "document_key": payload.get("document_key", ""),
            "version_key": payload.get("version_key", ""),
            "title": payload.get("title", ""),
            "content": payload.get("content", ""),
            "heading_path": payload.get("heading_path", []),
            "page_start": payload.get("page_start"),
            "page_end": payload.get("page_end"),
            "score": hit.score,
        })

    return {
        "chunks": chunks,
        "retrieval_time_ms": elapsed_ms,
    }
