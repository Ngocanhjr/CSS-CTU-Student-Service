from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.databases.models.documents import DocumentVersion
from app.databases.models.chunks import DocumentChunk
from app.databases.models.ingestion import IngestionJob
from app.databases.repositories.chunks import get_version_chunks, replace_version_chunks
from app.databases.session import AsyncSessionLocal
from app.ingestion.chunking.chunker import ChunkingResult, chunk_markdown_document
from app.ingestion.canonical_storage import read_canonical_markdown
from app.ingestion.markdown_reader import parse_markdown_document
from app.schemas.chunks import Chunk
from app.schemas.ingestion.indexing import (
    ChunkApprovalResponse,
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


def _approved_chunk_signature(rows: list[DocumentChunk]) -> list[tuple]:
    key_by_id = {row.id: row.chunk_key for row in rows}
    return [
        (
            row.chunk_key,
            key_by_id.get(row.parent_chunk_id),
            row.chunk_index,
            row.chunk_type,
            row.content,
            tuple(row.heading_path),
            row.page_start,
            row.page_end,
            row.token_count,
        )
        for row in sorted(rows, key=lambda item: item.chunk_index)
    ]


def _generated_chunk_signature(chunks: list[Chunk]) -> list[tuple]:
    return [
        (
            chunk.chunk_key,
            chunk.parent_chunk_key,
            chunk.chunk_index,
            chunk.chunk_type,
            chunk.content,
            tuple(chunk.heading_path),
            chunk.page_start,
            chunk.page_end,
            chunk.token_count,
        )
        for chunk in sorted(chunks, key=lambda item: item.chunk_index)
    ]


def _assert_approved_chunks_match(
    rows: list[DocumentChunk],
    generated: list[Chunk],
) -> None:
    if not rows or _approved_chunk_signature(rows) != _generated_chunk_signature(generated):
        raise ConflictError(
            "Canonical Markdown đã thay đổi; vui lòng preview và approve chunks lại"
        )


async def _get_chunk_approval_job(
    session: AsyncSession,
    document_version_id: int,
    *,
    for_update: bool = False,
) -> IngestionJob | None:
    statement = (
        select(IngestionJob)
        .where(
            IngestionJob.document_version_id == document_version_id,
            IngestionJob.job_type == "ingestion",
        )
        .order_by(IngestionJob.id.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


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


def _read_document(
    canonical_markdown_path: str,
    domain: str,
    audience: list[str],
):
    markdown_document = parse_markdown_document(
        read_canonical_markdown(canonical_markdown_path)
    )
    # PostgreSQL owns document-level business metadata. Overlay mirrors so an
    # older canonical file cannot restore stale Qdrant filter payload.
    markdown_document.metadata.domain = domain
    markdown_document.metadata.audience = list(audience)
    return markdown_document


async def _build_chunking_snapshot(
    session: AsyncSession,
    *,
    document_version_id: int,
) -> tuple[dict[str, Any], Any, ChunkingResult]:
    version = await session.scalar(
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.document))
        .where(DocumentVersion.id == document_version_id)
    )
    if version is None:
        raise NotFoundError(f"Không tìm thấy document version: {document_version_id}")
    canonical_path = version.canonical_markdown_path
    domain = version.document.domain
    audience = list(version.document.audience)
    snapshot = {
        "version_id": version.id,
        "canonical_path": canonical_path,
        "domain": domain,
        "audience": audience,
    }
    await session.rollback()
    markdown_document = await asyncio.to_thread(
        _read_document,
        canonical_path,
        domain,
        audience,
    )
    result = await asyncio.to_thread(_chunking, markdown_document)
    return snapshot, markdown_document, result


async def build_chunk_preview(session: AsyncSession, *, document_version_id: int) -> ChunkPreviewResponse:
    snapshot, _, result = await _build_chunking_snapshot(
        session,
        document_version_id=document_version_id,
    )
    return ChunkPreviewResponse(
        document_version_id=snapshot["version_id"],
        parent_chunks=len(result.parent_chunks),
        child_chunks=len(result.child_chunks),
        total_chunks=len(result.parent_chunks) + len(result.child_chunks),
        chunks=[_preview_item(chunk) for chunk in _all_chunks(result)],
        warnings=[_report(item) for item in result.warnings],
        errors=[_report(item) for item in result.errors],
    )


async def approve_chunk_preview(
    session: AsyncSession,
    *,
    document_version_id: int,
) -> ChunkApprovalResponse:
    snapshot, _, result = await _build_chunking_snapshot(
        session,
        document_version_id=document_version_id,
    )
    if result.errors:
        raise ConflictError("Chunk preview có lỗi; chưa thể approve")

    chunks = _all_chunks(result)
    async with session.begin():
        version = await session.scalar(
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.document))
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is None:
            raise NotFoundError(
                f"Không tìm thấy document version: {document_version_id}"
            )
        if version.ocr_status != "done" or version.review_status != "approved":
            raise ConflictError(
                "Chỉ approve chunks khi OCR done và Markdown đã approved"
            )
        if version.rag_status not in {"not_indexed", "failed"}:
            raise ConflictError(
                f"Không thể approve chunks khi rag_status={version.rag_status}"
            )
        if (
            version.canonical_markdown_path != snapshot["canonical_path"]
            or version.document.domain != snapshot["domain"]
            or set(version.document.audience) != set(snapshot["audience"])
        ):
            raise ConflictError(
                "Document đã thay đổi; vui lòng tạo chunk preview lại"
            )

        await replace_version_chunks(
            session,
            document_version_id=version.id,
            chunks=chunks,
        )
        job = await _get_chunk_approval_job(
            session,
            version.id,
            for_update=True,
        )
        if job is None:
            job = IngestionJob(
                document_version_id=version.id,
                job_type="ingestion",
                status="pending",
                current_step="chunks_approved",
                processed_chunks=0,
            )
            session.add(job)
        job.status = "pending"
        job.current_step = "chunks_approved"
        job.total_chunks = len(chunks)
        job.processed_chunks = 0
        job.error_message = None

    return ChunkApprovalResponse(
        document_version_id=document_version_id,
        approved=True,
        parent_chunks=len(result.parent_chunks),
        child_chunks=len(result.child_chunks),
        total_chunks=len(chunks),
        current_step="chunks_approved",
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
    version = await session.scalar(
        select(DocumentVersion)
        .options(selectinload(DocumentVersion.document))
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise NotFoundError(f"Không tìm thấy document version: {document_version_id}")
    if version.rag_status not in {"not_indexed", "failed"}:
        raise ConflictError(
            f"Không thể index khi rag_status={version.rag_status}"
        )
    if version.ocr_status != "done" or version.review_status != "approved":
        raise ConflictError("Chỉ index document version có ocr done và review approved")

    approval_job = await _get_chunk_approval_job(session, version.id)
    approved_rows = await get_version_chunks(session, version.id)
    if approval_job is None or approval_job.current_step != "chunks_approved":
        raise ConflictError("Chunks chưa được approve")
    if approval_job.total_chunks != len(approved_rows) or not approved_rows:
        raise ConflictError("Dữ liệu chunks đã duyệt không đầy đủ; vui lòng approve lại")
    approved_signature = _approved_chunk_signature(approved_rows)

    canonical_path = version.canonical_markdown_path
    domain = version.document.domain
    audience = list(version.document.audience)
    await session.rollback()
    markdown_document = await asyncio.to_thread(
        _read_document,
        canonical_path,
        domain,
        audience,
    )
    result = await asyncio.to_thread(_chunking, markdown_document)
    if result.errors:
        raise ConflictError("Chunking có lỗi, không thể index")
    if approved_signature != _generated_chunk_signature(_all_chunks(result)):
        raise ConflictError(
            "Canonical Markdown đã thay đổi; vui lòng preview và approve chunks lại"
        )

    async with session.begin():
        version = await session.scalar(
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.document))
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is None:
            raise NotFoundError(
                f"Không tìm thấy document version: {document_version_id}"
            )
        if version.rag_status not in {"not_indexed", "failed"}:
            raise ConflictError(
                f"Không thể index khi rag_status={version.rag_status}"
            )
        if (
            version.canonical_markdown_path != canonical_path
            or version.document.domain != domain
            or set(version.document.audience) != set(audience)
        ):
            raise ConflictError("Document đã thay đổi; vui lòng tạo preview lại")

        approval_job = await _get_chunk_approval_job(
            session,
            version.id,
            for_update=True,
        )
        approved_rows = await get_version_chunks(session, version.id)
        if approval_job is None or approval_job.current_step != "chunks_approved":
            raise ConflictError("Chunks chưa được approve")
        if approval_job.total_chunks != len(approved_rows):
            raise ConflictError("Dữ liệu chunks đã duyệt đã thay đổi")
        _assert_approved_chunks_match(approved_rows, _all_chunks(result))

        job = IngestionJob(
            document_version_id=version.id,
            job_type="indexing",
            status="processing",
            current_step="embedding",
            total_chunks=len(result.child_chunks),
            processed_chunks=0,
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        version.rag_status = "chunked"
        await session.flush()
    return _progress(job, version)


async def get_indexing_job_progress(
    session: AsyncSession,
    *,
    ingestion_job_id: int,
) -> IndexingJobProgress:
    job = await session.get(IngestionJob, ingestion_job_id)
    if job is None:
        raise NotFoundError(f"Không tìm thấy ingestion job: {ingestion_job_id}")
    version = await session.get(DocumentVersion, job.document_version_id)
    if version is None:
        raise NotFoundError(f"Không tìm thấy document version: {job.document_version_id}")
    return _progress(job, version)


async def run_indexing_job(ingestion_job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, ingestion_job_id)
        if job is None:
            return
        version = await session.scalar(
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.document))
            .where(DocumentVersion.id == job.document_version_id)
        )
        if version is None:
            return

        try:
            version_id = version.id
            canonical_path = version.canonical_markdown_path
            domain = version.document.domain
            audience = list(version.document.audience)
            job.current_step = "embedding"
            await session.commit()

            markdown_document = await asyncio.to_thread(
                _read_document,
                canonical_path,
                domain,
                audience,
            )
            result = await asyncio.to_thread(_chunking, markdown_document)
            child_chunks = result.child_chunks
            if result.errors:
                raise ValueError("Chunking có lỗi, không thể index")
            approved_rows = await get_version_chunks(session, version_id)
            _assert_approved_chunks_match(approved_rows, _all_chunks(result))
            await session.rollback()

            processed_chunks = 0

            async def record_batch(count: int) -> None:
                nonlocal processed_chunks
                processed_chunks = min(processed_chunks + count, len(child_chunks))
                async with session.begin():
                    current_job = await session.scalar(
                        select(IngestionJob)
                        .where(IngestionJob.id == ingestion_job_id)
                        .with_for_update()
                    )
                    if current_job is None or current_job.status != "processing":
                        raise ConflictError("Indexing job đã thay đổi")
                    current_job.processed_chunks = processed_chunks

            from app.embedding.embedder import embed_chunks_with_cache

            vectors = await embed_chunks_with_cache(
                markdown_document,
                child_chunks,
                progress_callback=record_batch,
            )

            async with session.begin():
                current_job = await session.scalar(
                    select(IngestionJob)
                    .where(IngestionJob.id == ingestion_job_id)
                    .with_for_update()
                )
                if current_job is None or current_job.status != "processing":
                    raise ConflictError("Indexing job đã thay đổi")
                current_job.current_step = "qdrant_upsert"
            rows = await get_version_chunks(session, version_id)
            row_by_key = {row.chunk_key: row for row in rows}
            postgres_ids = {
                chunk.chunk_key: (
                    row_by_key[chunk.chunk_key].id,
                    row_by_key[chunk.parent_chunk_key].id,
                )
                for chunk in child_chunks
            }
            await session.rollback()

            from app.vectorstore.qdrant_client import get_qdrant_client
            from app.vectorstore.repository import make_point_id, upsert_chunks

            await asyncio.to_thread(
                upsert_chunks,
                get_qdrant_client(),
                markdown_document,
                child_chunks,
                vectors,
                postgres_ids=postgres_ids,
                review_status="approved",
                rag_status="indexed",
            )

            async with session.begin():
                job = await session.scalar(
                    select(IngestionJob)
                    .where(IngestionJob.id == ingestion_job_id)
                    .with_for_update()
                )
                version = await session.scalar(
                    select(DocumentVersion)
                    .where(DocumentVersion.id == version_id)
                    .with_for_update()
                )
                if job is None or version is None:
                    raise NotFoundError("Indexing state không còn tồn tại")
                if job.status != "processing" or version.rag_status != "chunked":
                    raise ConflictError("Indexing state đã thay đổi")

                rows = await get_version_chunks(session, version_id)
                row_by_key = {row.chunk_key: row for row in rows}
                for chunk in child_chunks:
                    row = row_by_key[chunk.chunk_key]
                    row.index_status = "indexed"
                    row.qdrant_point_id = make_point_id(
                        chunk.version_key,
                        chunk.chunk_key,
                    )
                version.rag_status = "indexed"
                job.status = "completed"
                job.current_step = "completed"
                job.processed_chunks = len(child_chunks)
                job.finished_at = datetime.now(timezone.utc)
        except BaseException as exc:
            await session.rollback()
            job = await session.get(IngestionJob, ingestion_job_id)
            version = await session.get(DocumentVersion, job.document_version_id) if job else None
            if version is not None and version.rag_status in {"chunked", "embedded"}:
                version.rag_status = "failed"
            if job is not None and job.status == "processing":
                job.status = "failed"
                job.current_step = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            if not isinstance(exc, Exception):
                raise
