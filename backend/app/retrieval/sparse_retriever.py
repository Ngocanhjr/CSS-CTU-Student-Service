# Mục đích: tìm kiếm từ khóa bằng PostgreSQL FTS.

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