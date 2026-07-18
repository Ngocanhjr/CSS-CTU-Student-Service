from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import DocumentVersion
from app.databases.models.ingestion import IngestionJob
from app.databases.repositories.chunks import replace_version_chunks
from app.ingestion.chunking.chunker import ChunkingResult, chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.schemas.chunks import Chunk
from app.schemas.ingestion.indexing import (
    ChunkPreviewItem,
    ChunkPreviewResponse,
    IndexingResponse,
)


def _report(report: Any) -> dict[str, Any]:
    return {"code": report.code, "page": report.page, "reason": report.reason}


def _chunking(document: Any) -> ChunkingResult:
    from app.core.settings_loader import get_rag_settings

    settings = get_rag_settings().chunking
    return chunk_markdown_document(
        document,
        child_chunk_size=settings.child_chunk_size,
        child_chunk_overlap=settings.child_chunk_overlap,
    )


def _all_chunks(result: ChunkingResult) -> list[Chunk]:
    return [*result.parent_chunks, *result.child_chunks]


def _preview_item(chunk: Chunk) -> ChunkPreviewItem:
    return ChunkPreviewItem(
        chunk_key=chunk.chunk_key,
        parent_chunk_key=chunk.parent_chunk_key,
        chunk_index=chunk.chunk_index,
        chunk_type=chunk.chunk_type,
        content_preview=chunk.content[:500],
        heading_path=chunk.heading_path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        token_count=chunk.token_count,
        item_marker=chunk.metadata.get("item_marker"),
        item_level=chunk.metadata.get("item_level"),
        item_path=list(chunk.metadata.get("item_path", [])),
        logical_item_key=chunk.metadata.get("logical_item_key"),
        parent_item_key=chunk.metadata.get("parent_item_key"),
    )


def _read_document(version: DocumentVersion):
    from app.ingestion.canonical_storage import _resolve_canonical_path

    return read_markdown_document(_resolve_canonical_path(version.canonical_markdown_path))


async def build_chunk_preview(session: AsyncSession, *, document_version_id: int) -> ChunkPreviewResponse:
    version = await session.scalar(select(DocumentVersion).where(DocumentVersion.id == document_version_id))
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {document_version_id}")
    result = _chunking(_read_document(version))
    return ChunkPreviewResponse(
        document_version_id=version.id,
        parent_chunks=len(result.parent_chunks),
        child_chunks=len(result.child_chunks),
        total_chunks=len(result.parent_chunks) + len(result.child_chunks),
        chunks=[_preview_item(chunk) for chunk in _all_chunks(result)],
        warnings=[_report(item) for item in result.warnings],
        errors=[_report(item) for item in result.errors],
    )


async def index_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
    qdrant_client: Any | None = None,
    qdrant_upserter: Callable[..., int] | None = None,
) -> IndexingResponse:
    version = await session.scalar(select(DocumentVersion).where(DocumentVersion.id == document_version_id).with_for_update())
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {document_version_id}")
    if version.review_status != "approved":
        raise ValueError("Chỉ index document version đã review approved")

    markdown_document = _read_document(version)
    result = _chunking(markdown_document)
    if result.errors:
        raise ValueError("Chunking có lỗi, không thể index")

    job = IngestionJob(
        document_version_id=version.id,
        job_type="indexing",
        status="processing",
        current_step="persist_chunks",
        total_chunks=len(result.parent_chunks) + len(result.child_chunks),
        processed_chunks=0,
        started_at=datetime.now(timezone.utc),
    )
    session.add(job)
    rows = await replace_version_chunks(
        session,
        document_version_id=version.id,
        chunks=_all_chunks(result),
    )
    version.rag_status = "chunked"
    await session.commit()
    await session.refresh(job)

    try:
        job.current_step = "embedding"
        await session.commit()
        child_chunks = result.child_chunks
        if embedder is None:
            from app.embedding.embedder import embed_chunks_with_cache
            embedder = lambda texts: __import__("app.embedding.embedder", fromlist=["embed_texts"]).embed_texts(texts)
            vectors = embed_chunks_with_cache(markdown_document, child_chunks)
        else:
            from app.embedding.embedder import build_embedding_enriched_text
            vectors = embedder([build_embedding_enriched_text(markdown_document, chunk) for chunk in child_chunks])

        job.current_step = "qdrant_upsert"
        await session.commit()
        if qdrant_client is None:
            from app.vectorstore.qdrant_client import get_qdrant_client
            qdrant_client = get_qdrant_client()
        if qdrant_upserter is None:
            from app.vectorstore.repository import upsert_chunks
            qdrant_upserter = upsert_chunks
        row_by_key = {row.chunk_key: row for row in rows}
        postgres_ids = {
            chunk.chunk_key: (row_by_key[chunk.chunk_key].id, row_by_key[chunk.parent_chunk_key].id)
            for chunk in child_chunks
        }
        points = qdrant_upserter(
            qdrant_client,
            markdown_document,
            child_chunks,
            vectors,
            postgres_ids=postgres_ids,
            review_status="approved",
            rag_status="indexed",
        )
        for chunk in child_chunks:
            row = row_by_key[chunk.chunk_key]
            row.index_status = "indexed"
            from app.vectorstore.repository import make_point_id
            row.qdrant_point_id = make_point_id(chunk.version_key, chunk.chunk_key)
        version.rag_status = "indexed"
        job.status = "completed"
        job.current_step = "completed"
        job.processed_chunks = len(child_chunks)
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()
        return IndexingResponse(
            document_version_id=version.id,
            ingestion_job_id=job.id,
            job_status=job.status,
            current_step=job.current_step,
            parent_chunks=len(result.parent_chunks),
            child_chunks=len(child_chunks),
            total_chunks=len(rows),
            indexed_chunks=len(child_chunks),
            qdrant_points=points,
            rag_status=version.rag_status,
            warnings=[_report(item) for item in result.warnings],
        )
    except Exception as exc:
        await session.rollback()
        version = await session.scalar(select(DocumentVersion).where(DocumentVersion.id == document_version_id).with_for_update())
        if version is not None:
            version.rag_status = "failed"
        job = await session.scalar(select(IngestionJob).where(IngestionJob.id == job.id).with_for_update())
        if job is not None:
            job.status = "failed"
            job.current_step = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
        await session.commit()
        raise
