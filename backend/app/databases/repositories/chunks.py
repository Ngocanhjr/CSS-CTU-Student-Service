from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.chunks import DocumentChunk
from app.schemas.chunks import Chunk


async def replace_version_chunks(
    session: AsyncSession,
    *,
    document_version_id: int,
    chunks: Sequence[Chunk],
) -> list[DocumentChunk]:
    """Replace a version's chunk rows. The caller owns commit/rollback."""
    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_version_id == document_version_id)
    )
    await session.flush()

    parents = [chunk for chunk in chunks if chunk.chunk_type == "parent"]
    children = [chunk for chunk in chunks if chunk.chunk_type == "child"]
    by_key: dict[str, DocumentChunk] = {}
    rows: list[DocumentChunk] = []

    for chunk in parents:
        row = DocumentChunk(
            document_version_id=document_version_id,
            chunk_key=chunk.chunk_key,
            chunk_index=chunk.chunk_index,
            chunk_type=chunk.chunk_type,
            heading_path=chunk.heading_path,
            section_title=chunk.heading_path[-1] if chunk.heading_path else "",
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            token_count=chunk.token_count,
            index_status="not_indexed",
        )
        session.add(row)
        rows.append(row)
        by_key[chunk.chunk_key] = row
    await session.flush()

    for chunk in children:
        parent = by_key.get(chunk.parent_chunk_key or "")
        if parent is None:
            raise ValueError(f"Missing parent chunk: {chunk.parent_chunk_key}")
        row = DocumentChunk(
            document_version_id=document_version_id,
            parent_chunk_id=parent.id,
            chunk_key=chunk.chunk_key,
            chunk_index=chunk.chunk_index,
            chunk_type=chunk.chunk_type,
            heading_path=chunk.heading_path,
            section_title=chunk.heading_path[-1] if chunk.heading_path else "",
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            token_count=chunk.token_count,
            index_status="not_indexed",
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def get_version_chunks(session: AsyncSession, document_version_id: int) -> list[DocumentChunk]:
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == document_version_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


async def delete_chunks_by_version(
    session: AsyncSession,
    document_version_id: int,
) -> int:
    """Delete all chunks for a document version. Returns count deleted."""

    # Count before delete
    count_result = await session.execute(
        select(func.count()).where(
            DocumentChunk.document_version_id == document_version_id
        )
    )
    count = count_result.scalar() or 0

    # Delete chunks
    await session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_version_id == document_version_id
        )
    )

    return count
