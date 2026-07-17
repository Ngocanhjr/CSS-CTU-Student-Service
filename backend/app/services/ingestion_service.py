from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import Document, DocumentChunk, DocumentVersion, IngestionJob
from app.embedding.embedder import embed_chunks_with_cache
from app.ingestion.chunking.chunker import chunk_markdown_document
from app.ingestion.markdown_reader import read_markdown_document
from app.vectorstore.qdrant_client import get_qdrant_client
from app.vectorstore.repository import (
    delete_points_by_version,
    make_point_id,
    upsert_chunks,
)


@dataclass(frozen=True)
class IngestionResult:
    version_id: int
    parent_chunks: int
    child_chunks: int
    qdrant_points: int
    job_id: int


class IngestionService:
    async def ingest_version(
        self,
        session: AsyncSession,
        *,
        version_id: int,
        markdown_path: str | Path,
    ) -> IngestionResult:
        version = await session.get(DocumentVersion, version_id)
        if version is None:
            raise ValueError(f"Document version {version_id} was not found")

        document = await session.get(Document, version.document_id)
        if document is None:
            raise ValueError(f"Document for version {version_id} was not found")
        if version.ocr_status != "done" or version.review_status != "approved":
            raise ValueError("Ingestion requires ocr_status=done and review_status=approved")

        markdown_document = read_markdown_document(markdown_path)
        if markdown_document.metadata.document_key != document.document_key:
            raise ValueError("Markdown document_key does not match the stored document")
        if markdown_document.metadata.version_key != version.version_key:
            raise ValueError("Markdown version_key does not match the stored version")

        chunks = chunk_markdown_document(markdown_document)
        parent_chunks = [chunk for chunk in chunks if chunk.chunk_type == "parent"]
        child_chunks = [chunk for chunk in chunks if chunk.chunk_type == "child"]
        if not child_chunks:
            raise ValueError("Ingestion requires at least one child chunk")

        vectors = embed_chunks_with_cache(markdown_document, child_chunks)
        now = datetime.now(timezone.utc)
        job = IngestionJob(
            document_version_id=version.id,
            status="running",
            current_step="persisting_chunks",
            total_chunks=len(chunks),
            started_at=now,
        )
        session.add(job)

        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_version_id == version.id)
        )
        await session.flush()

        chunk_records: dict[str, DocumentChunk] = {}
        child_records: list[DocumentChunk] = []
        for chunk in chunks:
            parent = chunk_records.get(chunk.parent_chunk_key or "")
            record = DocumentChunk(
                document_version_id=version.id,
                parent_chunk_id=parent.id if parent is not None else None,
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
            session.add(record)
            await session.flush()
            chunk_records[chunk.chunk_key] = record
            if chunk.chunk_type == "child":
                child_records.append(record)

        job.current_step = "upserting_qdrant"
        client = get_qdrant_client()
        delete_points_by_version(client, version_key=version.version_key)
        point_count = upsert_chunks(
            client,
            markdown_document,
            child_chunks,
            vectors,
            postgres_chunk_ids=[record.id for record in child_records],
            review_status=version.review_status,
            rag_status="published",
            is_latest=version.is_latest,
            audience=list(document.audience),
        )

        for record in child_records:
            record.qdrant_point_id = make_point_id(version.version_key, record.chunk_key)
            record.index_status = "indexed"

        version.rag_status = "published"
        job.status = "completed"
        job.current_step = "published"
        job.processed_chunks = len(chunks)
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()

        return IngestionResult(
            version_id=version.id,
            parent_chunks=len(parent_chunks),
            child_chunks=len(child_chunks),
            qdrant_points=point_count,
            job_id=job.id,
        )
