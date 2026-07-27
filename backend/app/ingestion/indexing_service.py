from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import DocumentVersion
from app.databases.models.chunks import DocumentChunk
from app.databases.models.ingestion import IngestionJob
from app.databases.repositories.chunks import get_version_chunks, replace_version_chunks
from app.databases.session import AsyncSessionLocal
from app.ingestion.chunking.chunker import ChunkingResult, chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.schemas.chunks import Chunk
from app.schemas.ingestion.indexing import (
    ChunkPreviewItem,
    ChunkPreviewResponse,
    IndexingJobProgress,
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


def _progress(job: IngestionJob, version: DocumentVersion) -> IndexingJobProgress:
    total = job.total_chunks or 0
    processed = min(job.processed_chunks, total)
    return IndexingJobProgress(
        ingestion_job_id=job.id,
        document_version_id=version.id,
        job_status=job.status,
        current_step=job.current_step,
        total_chunks=total,
        processed_chunks=processed,
        remaining_chunks=max(total - processed, 0),
        rag_status=version.rag_status,
        error_message=job.error_message,
    )


async def start_index_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
) -> IndexingJobProgress:
    version = await session.scalar(select(DocumentVersion).where(DocumentVersion.id == document_version_id).with_for_update())
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {document_version_id}")
    if version.ocr_status != "done" or version.review_status != "approved":
        raise ValueError("Chỉ index document version có ocr done và review approved")

    markdown_document = _read_document(version)
    result = _chunking(markdown_document)
    if result.errors:
        raise ValueError("Chunking có lỗi, không thể index")

    job = IngestionJob(
        document_version_id=version.id,
        job_type="indexing",
        status="processing",
        current_step="persist_chunks",
        total_chunks=len(result.child_chunks),
        processed_chunks=0,
        started_at=datetime.now(timezone.utc),
    )
    session.add(job)
    await replace_version_chunks(
        session,
        document_version_id=version.id,
        chunks=_all_chunks(result),
    )
    version.rag_status = "chunked"
    await session.commit()
    await session.refresh(job)
    return _progress(job, version)


async def get_indexing_job_progress(
    session: AsyncSession,
    *,
    ingestion_job_id: int,
) -> IndexingJobProgress:
    job = await session.get(IngestionJob, ingestion_job_id)
    if job is None:
        raise LookupError(f"Không tìm thấy ingestion job: {ingestion_job_id}")
    version = await session.get(DocumentVersion, job.document_version_id)
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {job.document_version_id}")
    return _progress(job, version)


async def run_indexing_job(ingestion_job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, ingestion_job_id)
        if job is None:
            return
        version = await session.get(DocumentVersion, job.document_version_id)
        if version is None:
            return

        try:
            markdown_document = _read_document(version)
            result = _chunking(markdown_document)
            child_chunks = result.child_chunks
            if result.errors:
                raise ValueError("Chunking có lỗi, không thể index")

            job.current_step = "embedding"
            await session.commit()

            async def record_batch(count: int) -> None:
                job.processed_chunks = min(job.processed_chunks + count, job.total_chunks or 0)
                await session.commit()

            from app.embedding.embedder import embed_chunks_with_cache

            vectors = await embed_chunks_with_cache(
                markdown_document,
                child_chunks,
                progress_callback=record_batch,
            )

            job.current_step = "qdrant_upsert"
            await session.commit()
            rows = await get_version_chunks(session, version.id)
            row_by_key = {row.chunk_key: row for row in rows}
            postgres_ids = {
                chunk.chunk_key: (
                    row_by_key[chunk.chunk_key].id,
                    row_by_key[chunk.parent_chunk_key].id,
                )
                for chunk in child_chunks
            }

            from app.vectorstore.qdrant_client import get_qdrant_client
            from app.vectorstore.repository import make_point_id, upsert_chunks

            points = await asyncio.to_thread(
                upsert_chunks,
                get_qdrant_client(),
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
                row.qdrant_point_id = make_point_id(chunk.version_key, chunk.chunk_key)
            version.rag_status = "indexed"
            job.status = "completed"
            job.current_step = "completed"
            job.processed_chunks = len(child_chunks)
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            job = await session.get(IngestionJob, ingestion_job_id)
            version = await session.get(DocumentVersion, job.document_version_id) if job else None
            if version is not None:
                version.rag_status = "failed"
            if job is not None:
                job.status = "failed"
                job.current_step = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.now(timezone.utc)
            await session.commit()
