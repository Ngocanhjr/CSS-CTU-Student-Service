from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import yaml
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.databases.asset_repository import replace_document_assets
from app.databases.models.assets import DocumentAsset
from app.databases.models.documents import (
    Document,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
)
from app.databases.models.ingestion import IngestionJob
from app.ingestion.canonical_storage import (
    delete_canonical_markdown,
    delete_source_file,
    read_canonical_markdown,
)
from app.ingestion.markdown_reader import split_frontmatter
from app.ingestion.review_service import review_canonical_document
from app.schemas.documents_management import (
    DocumentAssetsUpdateRequest,
    DocumentVersionDetail,
    DocumentVersionSummary,
    DocumentVersionUpdateRequest,
    DocumentVersionUpdateResponse,
)
from app.schemas.assets import LinkedAssetResponse

logger = logging.getLogger(__name__)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _extra(version: DocumentVersion, key: str, default: Any = None) -> Any:
    return (version.extra_metadata or {}).get(key, default)


def _department_id(version: DocumentVersion) -> int | None:
    return version.recipients[0].department_id if version.recipients else None


def _last_job(version: DocumentVersion):
    return max(version.ingestion_jobs, key=lambda job: job.id, default=None)


def _to_summary(version: DocumentVersion) -> DocumentVersionSummary:
    document = version.document
    return DocumentVersionSummary(
        id=version.id,
        document_id=document.id,
        document_key=document.document_key,
        title=version.title or document.title,
        version_key=version.version_key,
        version_label=version.version_key,
        document_type_id=document.document_type_id,
        department_id=_department_id(version),
        domain=document.domain,
        audience=list(document.audience),
        code=version.code,
        issued_date=_iso(version.issued_date),
        effective_date=_extra(version, "effective_date"),
        expiry_date=_extra(version, "expiry_date"),
        review_status=version.review_status,
        validity_status=_extra(version, "validity_status", "unknown"),
        ocr_status=version.ocr_status,
        rag_status=version.rag_status,
        updated_at=version.updated_at.isoformat() if version.updated_at else None,
    )


async def list_document_versions(
    session: AsyncSession,
    *,
    query: str | None = None,
    department_id: int | None = None,
    document_type_id: int | None = None,
    rag_status: str | None = None,
    review_status: str | None = None,
) -> list[DocumentVersionSummary]:
    statement = (
        select(DocumentVersion)
        .options(
            selectinload(DocumentVersion.document),
            selectinload(DocumentVersion.recipients),
            selectinload(DocumentVersion.ingestion_jobs),
        )
        .join(Document, Document.id == DocumentVersion.document_id)
        .order_by(DocumentVersion.updated_at.desc(), DocumentVersion.id.desc())
    )

    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(Document.title.ilike(pattern), Document.document_key.ilike(pattern))
        )
    if department_id is not None:
        statement = statement.where(
            DocumentVersion.recipients.any(
                DocumentRecipient.department_id == department_id
            )
        )
    if document_type_id is not None:
        statement = statement.where(Document.document_type_id == document_type_id)
    if rag_status:
        statement = statement.where(DocumentVersion.rag_status == rag_status)
    if review_status:
        statement = statement.where(DocumentVersion.review_status == review_status)

    result = await session.execute(statement)
    return [_to_summary(version) for version in result.scalars().unique().all()]


async def get_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
) -> DocumentVersionDetail:
    statement = (
        select(DocumentVersion)
        .options(
            selectinload(DocumentVersion.document).selectinload(
                Document.document_type
            ),
            selectinload(DocumentVersion.recipients).selectinload(
                DocumentRecipient.department
            ),
            selectinload(DocumentVersion.ingestion_jobs),
            selectinload(DocumentVersion.asset_links).selectinload(
                DocumentAsset.asset
            ),
        )
        .where(DocumentVersion.id == document_version_id)
    )
    version = await session.scalar(statement)
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {document_version_id}")

    summary = _to_summary(version)
    job = _last_job(version)
    try:
        markdown = read_canonical_markdown(version.canonical_markdown_path)
    except FileNotFoundError:
        markdown = ""

    assets = [
        LinkedAssetResponse(
            asset_key=link.asset.asset_key,
            title=link.asset.title,
            url=link.asset.url,
            asset_type=link.asset.asset_type,
            relation_type=link.relation_type,
            display_order=link.display_order,
        )
        for link in sorted(
            version.asset_links,
            key=lambda item: item.display_order,
        )
    ]
    responsible_departments = [
        recipient.department.code for recipient in version.recipients
    ] or list(_extra(version, "responsible_department", []))

    return DocumentVersionDetail(
        **summary.model_dump(),
        document_type_code=version.document.document_type.code,
        canonical_markdown=markdown,
        canonical_markdown_path=version.canonical_markdown_path,
        source_path=version.source_path,
        source_url=version.source_url,
        checksum=version.checksum,
        responsible_department=responsible_departments,
        issuing_authority=version.issuing_authority,
        signer_name=version.signer_name,
        is_latest=version.is_latest,
        language=version.language,
        accessed_date=_iso(version.accessed_date),
        parser=_extra(version, "parser"),
        ocr_engine=_extra(version, "ocr_engine"),
        notes=_extra(version, "notes", ""),
        assets=assets,
        last_job_id=job.id if job else None,
        last_job_status=job.status if job else None,
        last_job_step=job.current_step if job else None,
        last_job_error=job.error_message if job else None,
        last_job_processed_chunks=job.processed_chunks if job else None,
        last_job_total_chunks=job.total_chunks if job else None,
    )


async def update_document_version_assets(
    session: AsyncSession,
    *,
    document_version_id: int,
    payload: DocumentAssetsUpdateRequest,
) -> DocumentVersionDetail:
    async with session.begin():
        version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is None:
            raise LookupError(
                f"Không tìm thấy document version: {document_version_id}"
            )

        await replace_document_assets(
            session,
            document_version_id=version.id,
            assets=payload.assets,
        )

    return await get_document_version(
        session,
        document_version_id=document_version_id,
    )


async def update_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
    payload: DocumentVersionUpdateRequest,
) -> DocumentVersionUpdateResponse:
    version = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {document_version_id}")
    if version.rag_status != "not_indexed":
        raise ValueError("Không thể sửa version đã index; cần deindex trước")

    frontmatter, body = split_frontmatter(payload.canonical_markdown)
    metadata = payload.metadata

    if metadata.document_type_id is not None:
        document_type = await session.scalar(
            select(DocumentType).where(
                DocumentType.id == metadata.document_type_id,
                DocumentType.is_active.is_(True),
            )
        )
        if document_type is None:
            raise ValueError("Document type không tồn tại hoặc đã bị khóa")
        frontmatter["document_type"] = document_type.code

    frontmatter["responsible_department"] = metadata.responsible_department

    frontmatter.update(
        {
            "title": metadata.title,
            "domain": metadata.domain,
            "audience": metadata.audience,
            "code": metadata.code,
            "issued_date": _iso(metadata.issued_date),
            "effective_date": _iso(metadata.effective_date),
            "expiry_date": _iso(metadata.expiry_date),
            "validity_status": metadata.validity_status,
            "ocr_status": "done",
            "review_status": "approved",
            "rag_status": "not_indexed",
        }
    )

    edited_markdown = (
        "---\n"
        + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
        + "---\n\n"
        + body.strip()
        + "\n"
    )
    # review_canonical_document owns its transaction; end read-only lookups first.
    await session.rollback()
    await review_canonical_document(
        session,
        document_version_id=document_version_id,
        canonical_markdown=edited_markdown,
    )
    return DocumentVersionUpdateResponse(
        updated=True,
        document=await get_document_version(
            session,
            document_version_id=document_version_id,
        ),
    )


async def delete_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> None:
    """Delete a document version and remove its parent when it becomes empty."""

    # 1. Fetch version
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise LookupError(f"Document version {document_version_id} not found")

    # 2. Check rag_status
    if version.rag_status not in ("not_indexed", "failed"):
        raise ValueError(
            f"Cannot delete indexed document (rag_status={version.rag_status}). "
            "Deindex first."
        )

    canonical_path = version.canonical_markdown_path
    source_path = version.source_path
    await session.rollback()

    # R2 is external I/O; finish the read transaction before deleting objects.
    if canonical_path:
        await asyncio.to_thread(delete_canonical_markdown, canonical_path)
    if source_path:
        await asyncio.to_thread(delete_source_file, source_path)

    version = await session.scalar(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    if version is None:
        return

    has_other_versions = await session.scalar(
        select(DocumentVersion.id)
        .where(
            DocumentVersion.document_id == version.document_id,
            DocumentVersion.id != document_version_id,
        )
        .limit(1)
    )

    # 3. Delete related ingestion jobs
    await session.execute(
        delete(IngestionJob).where(
            IngestionJob.document_version_id == document_version_id
        )
    )

    # 4. Delete version record
    document_id = version.document_id
    await session.delete(version)
    await session.flush()
    if has_other_versions is None:
        await session.execute(delete(Document).where(Document.id == document_id))
    await session.commit()


async def publish_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Mark document version as published."""
    from datetime import datetime, timezone

    result = await session.execute(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    version = result.scalar_one_or_none()

    if not version:
        raise LookupError(f"Document version {document_version_id} not found")

    if version.rag_status != "indexed":
        raise ValueError(
            f"Document must be indexed before publishing (current: {version.rag_status})"
        )

    now = datetime.now(timezone.utc)
    version.rag_status = "published"
    # Store published_at in extra_metadata
    extra = dict(version.extra_metadata or {})
    extra["published_at"] = now.isoformat()
    version.extra_metadata = extra
    await session.commit()

    try:
        from app.vectorstore.qdrant_client import get_qdrant_client
        from app.vectorstore.repository import set_version_rag_status

        await asyncio.to_thread(
            set_version_rag_status,
            get_qdrant_client(),
            version_key=version.version_key,
            rag_status="published",
        )
    except Exception as exc:
        await session.rollback()
        version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is not None and version.rag_status == "published":
            version.rag_status = "indexed"
            extra = dict(version.extra_metadata or {})
            extra.pop("published_at", None)
            version.extra_metadata = extra
            await session.commit()
        raise RuntimeError(f"Không cập nhật được trạng thái Qdrant: {exc}") from exc

    return {
        "document_version_id": document_version_id,
        "rag_status": "published",
        "published_at": now,
    }


async def unpublish_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Mark document version as unpublished (but keep vectors)."""
    from datetime import datetime, timezone

    result = await session.execute(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    version = result.scalar_one_or_none()

    if not version:
        raise LookupError(f"Document version {document_version_id} not found")

    if version.rag_status != "published":
        raise ValueError(f"Document is not published (current: {version.rag_status})")

    now = datetime.now(timezone.utc)
    version.rag_status = "indexed"
    # Store unpublished_at in extra_metadata
    extra = dict(version.extra_metadata or {})
    extra["unpublished_at"] = now.isoformat()
    version.extra_metadata = extra
    await session.commit()

    try:
        from app.vectorstore.qdrant_client import get_qdrant_client
        from app.vectorstore.repository import set_version_rag_status

        await asyncio.to_thread(
            set_version_rag_status,
            get_qdrant_client(),
            version_key=version.version_key,
            rag_status="indexed",
        )
    except Exception as exc:
        await session.rollback()
        version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is not None and version.rag_status == "indexed":
            version.rag_status = "published"
            extra = dict(version.extra_metadata or {})
            extra.pop("unpublished_at", None)
            version.extra_metadata = extra
            await session.commit()
        raise RuntimeError(f"Không cập nhật được trạng thái Qdrant: {exc}") from exc

    return {
        "document_version_id": document_version_id,
        "rag_status": "indexed",
        "unpublished_at": now,
    }


INDEXED_STATUSES = {"chunked", "embedded", "indexed", "published"}


async def deindex_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Remove chunks and vectors for a document version."""
    from sqlalchemy import func

    from app.databases.models.chunks import DocumentChunk
    from app.databases.repositories.chunks import delete_chunks_by_version
    from app.vectorstore.qdrant_client import get_qdrant_client
    from app.vectorstore.repository import COLLECTION_NAME, delete_vectors_by_chunk_ids

    # 1. Fetch version
    result = await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == document_version_id)
    )
    version = result.scalar_one_or_none()

    if not version:
        raise LookupError(f"Document version {document_version_id} not found")

    # 2. Check rag_status
    if version.rag_status not in INDEXED_STATUSES:
        raise ValueError(
            f"Document not indexed (rag_status={version.rag_status})"
        )

    # 3. Get child chunk IDs for Qdrant deletion (only child chunks are in Qdrant)
    chunk_ids_result = await session.execute(
        select(DocumentChunk.id).where(
            DocumentChunk.document_version_id == document_version_id,
            DocumentChunk.chunk_type == "child",
        )
    )
    child_chunk_ids = [row[0] for row in chunk_ids_result.all()]

    # 4. Delete vectors from Qdrant
    client = get_qdrant_client()
    vectors_deleted = delete_vectors_by_chunk_ids(
        client,
        collection_name=COLLECTION_NAME,
        postgres_chunk_ids=child_chunk_ids,
    )

    # 5. Delete chunks from PostgreSQL
    chunks_deleted = await delete_chunks_by_version(session, document_version_id)

    # 6. Update rag_status
    version.rag_status = "not_indexed"
    await session.commit()

    return {
        "document_version_id": document_version_id,
        "chunks_deleted": chunks_deleted,
        "vectors_deleted": vectors_deleted,
        "new_rag_status": "not_indexed",
    }
