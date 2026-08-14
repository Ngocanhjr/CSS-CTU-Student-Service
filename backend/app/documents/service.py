from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ApplicationError,
    ConflictError,
    ExternalServiceError,
    InvalidRequestError,
    NotFoundError,
)
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
    delete_object,
    read_canonical_markdown,
    replace_canonical_markdown,
)
from app.ingestion.markdown_reader import render_markdown_document, split_frontmatter
from app.ingestion.review_service import review_canonical_document
from app.schemas.documents_management import (
    DocumentAssetsUpdateRequest,
    DocumentVersionDetail,
    DocumentVersionSummary,
    DocumentVersionUpdateMetadata,
    DocumentVersionUpdateRequest,
    DocumentVersionUpdateResponse,
)
from app.schemas.assets import LinkedAssetResponse
from app.schemas.documents import DocumentMetadata

logger = logging.getLogger(__name__)
LIFECYCLE_RETRY_AFTER = timedelta(minutes=5)


def _assert_lifecycle_job_retryable(
    job: IngestionJob,
    *,
    operation: str,
) -> None:
    if job.status != "processing":
        return

    updated_at = job.updated_at or job.created_at
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if (
        updated_at is None
        or datetime.now(timezone.utc) - updated_at < LIFECYCLE_RETRY_AFTER
    ):
        raise ConflictError(
            f"{operation} đang được xử lý; vui lòng thử lại sau"
        )


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


# Read-only document management queries. These return API DTOs rather than ORM models.
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
        raise NotFoundError(f"Không tìm thấy document version: {document_version_id}")

    summary = _to_summary(version)
    job = _last_job(version)
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
    detail = {
        **summary.model_dump(),
        "document_type_code": version.document.document_type.code,
        "canonical_markdown_path": version.canonical_markdown_path,
        "source_path": version.source_path,
        "source_url": version.source_url,
        "checksum": version.checksum,
        "responsible_department": responsible_departments,
        "issuing_authority": version.issuing_authority,
        "signer_name": version.signer_name,
        "is_latest": version.is_latest,
        "language": version.language,
        "accessed_date": _iso(version.accessed_date),
        "parser": _extra(version, "parser"),
        "ocr_engine": _extra(version, "ocr_engine"),
        "notes": _extra(version, "notes", ""),
        "assets": assets,
        "last_job_id": job.id if job else None,
        "last_job_type": job.job_type if job else None,
        "last_job_status": job.status if job else None,
        "last_job_step": job.current_step if job else None,
        "last_job_error": job.error_message if job else None,
        "last_job_processed_chunks": job.processed_chunks if job else None,
        "last_job_total_chunks": job.total_chunks if job else None,
    }
    await session.rollback()
    try:
        markdown = await asyncio.to_thread(
            read_canonical_markdown,
            detail["canonical_markdown_path"],
        )
    except FileNotFoundError:
        markdown = ""

    return DocumentVersionDetail(
        **detail,
        canonical_markdown=markdown,
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
            raise NotFoundError(
                f"Không tìm thấy document version: {document_version_id}"
            )
        if version.rag_status == "deactivated":
            raise ConflictError(
                "Document đang chờ hoàn tất Deindex/Delete; chưa thể sửa asset"
            )

        try:
            await replace_document_assets(
                session,
                document_version_id=version.id,
                assets=payload.assets,
            )
        except ValueError as exc:
            raise InvalidRequestError(str(exc)) from exc

    return await get_document_version(
        session,
        document_version_id=document_version_id,
    )


# Metadata updates may also rebuild canonical Markdown and trigger a review pass.
# Keep external storage work outside the short database transaction phases.
async def update_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
    payload: DocumentVersionUpdateRequest,
) -> DocumentVersionUpdateResponse:
    try:
        return await _update_document_version(
            session,
            document_version_id=document_version_id,
            payload=payload,
        )
    except ApplicationError:
        raise
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc
    except RuntimeError as exc:
        raise ExternalServiceError(str(exc)) from exc


async def _update_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
    payload: DocumentVersionUpdateRequest,
) -> DocumentVersionUpdateResponse:
    version = await session.scalar(
        select(DocumentVersion)
        .options(
            selectinload(DocumentVersion.document),
            selectinload(DocumentVersion.recipients).selectinload(
                DocumentRecipient.department
            ),
        )
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise NotFoundError(f"Không tìm thấy document version: {document_version_id}")
    if version.rag_status == "deactivated":
        raise ConflictError(
            "Document đang chờ hoàn tất Deindex/Delete; vui lòng thử lại lifecycle trước"
        )
    frontmatter, body = split_frontmatter(payload.canonical_markdown)
    metadata = payload.metadata

    if version.rag_status != "not_indexed":
        return await _update_indexed_version_metadata(
            session,
            version=version,
            metadata=metadata,
            submitted_body=body,
        )

    if metadata.document_type_id is not None:
        document_type = await session.scalar(
            select(DocumentType).where(
                DocumentType.id == metadata.document_type_id,
                DocumentType.is_active.is_(True),
            )
        )
        if document_type is None:
            raise InvalidRequestError("Document type không tồn tại hoặc đã bị khóa")
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

    reviewed_metadata = DocumentMetadata.model_validate(frontmatter)
    # review_canonical_document owns its transaction; end read-only lookups first.
    await session.rollback()
    await review_canonical_document(
        session,
        document_version_id=document_version_id,
        markdown_body=body,
        metadata=reviewed_metadata,
    )
    return DocumentVersionUpdateResponse(
        updated=True,
        document=await get_document_version(
            session,
            document_version_id=document_version_id,
        ),
    )


async def _update_indexed_version_metadata(
    session: AsyncSession,
    *,
    version: DocumentVersion,
    metadata: DocumentVersionUpdateMetadata,
    submitted_body: str,
) -> DocumentVersionUpdateResponse:
    """Update cheap metadata while preserving existing chunks and vectors."""
    document = version.document
    current_departments = sorted(
        recipient.department.code for recipient in version.recipients
    )
    submitted_departments = sorted(dict.fromkeys(metadata.responsible_department))
    snapshot = {
        "version_id": version.id,
        "document_id": document.id,
        "document_key": document.document_key,
        "domain": document.domain,
        "audience": list(document.audience),
        "title": version.title or document.title,
        "document_type_id": document.document_type_id,
        "departments": current_departments,
        "rag_status": version.rag_status,
        "review_status": version.review_status,
        "ocr_status": version.ocr_status,
        "code": version.code,
        "issued_date": version.issued_date,
        "canonical_path": version.canonical_markdown_path,
        "extra_metadata": dict(version.extra_metadata or {}),
    }

    # R2 is external I/O: close the read transaction before fetching the file.
    await session.rollback()
    previous_markdown = await asyncio.to_thread(
        read_canonical_markdown,
        snapshot["canonical_path"],
    )
    current_frontmatter, current_body = split_frontmatter(previous_markdown)

    restricted_changes: list[str] = []
    if metadata.title != snapshot["title"]:
        restricted_changes.append("tiêu đề")
    if metadata.document_type_id != snapshot["document_type_id"]:
        restricted_changes.append("loại tài liệu")
    if submitted_departments != snapshot["departments"]:
        restricted_changes.append("phòng ban phụ trách")
    if submitted_body.strip() != current_body.strip():
        restricted_changes.append("nội dung canonical Markdown")
    if restricted_changes:
        raise InvalidRequestError(
            "Các trường sau ảnh hưởng embedding và cần Deindex trước: "
            + ", ".join(restricted_changes)
        )

    effective_date = metadata.effective_date or metadata.issued_date
    if current_departments and effective_date is None:
        raise InvalidRequestError(
            "Phòng ban phụ trách yêu cầu ngày hiệu lực hoặc ngày ban hành"
        )

    new_audience = list(metadata.audience)
    payload_changed = (
        metadata.domain != snapshot["domain"]
        or new_audience != snapshot["audience"]
    )
    direct_metadata_changed = payload_changed or any(
        (
            metadata.code != snapshot["code"],
            metadata.issued_date != snapshot["issued_date"],
            _iso(metadata.effective_date)
            != snapshot["extra_metadata"].get("effective_date"),
            _iso(metadata.expiry_date)
            != snapshot["extra_metadata"].get("expiry_date"),
            metadata.validity_status
            != snapshot["extra_metadata"].get("validity_status", "unknown"),
        )
    )
    if not direct_metadata_changed:
        return DocumentVersionUpdateResponse(
            updated=False,
            document=await get_document_version(
                session,
                document_version_id=snapshot["version_id"],
            ),
        )

    current_frontmatter.update(
        {
            "domain": metadata.domain,
            "audience": new_audience,
            "code": metadata.code,
            "issued_date": _iso(metadata.issued_date),
            "effective_date": _iso(metadata.effective_date),
            "expiry_date": _iso(metadata.expiry_date),
            "validity_status": metadata.validity_status,
            "ocr_status": snapshot["ocr_status"],
            "review_status": snapshot["review_status"],
            "rag_status": snapshot["rag_status"],
        }
    )
    edited_markdown = render_markdown_document(
        DocumentMetadata.model_validate(current_frontmatter),
        current_body,
    )

    from app.vectorstore.qdrant_client import get_qdrant_client
    from app.vectorstore.repository import set_document_metadata_payload

    async def sync_payload(domain: str, audience: list[str]) -> None:
        try:
            await asyncio.to_thread(
                set_document_metadata_payload,
                get_qdrant_client(),
                document_key=snapshot["document_key"],
                domain=domain,
                audience=audience,
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"Không đồng bộ được metadata Qdrant: {exc}"
            ) from exc

    if payload_changed:
        await sync_payload(metadata.domain, new_audience)
    try:
        await asyncio.to_thread(
            replace_canonical_markdown,
            snapshot["canonical_path"],
            edited_markdown,
        )
    except BaseException:
        if payload_changed:
            await sync_payload(snapshot["domain"], snapshot["audience"])
        raise

    try:
        async with session.begin():
            locked_version = await session.scalar(
                select(DocumentVersion)
                .where(DocumentVersion.id == snapshot["version_id"])
                .with_for_update()
            )
            if locked_version is None:
                raise NotFoundError(
                    f"Không tìm thấy document version: {snapshot['version_id']}"
                )
            if locked_version.rag_status != snapshot["rag_status"]:
                raise InvalidRequestError(
                    "Trạng thái RAG đã thay đổi; vui lòng tải lại trang"
                )

            locked_document = await session.scalar(
                select(Document)
                .where(Document.id == snapshot["document_id"])
                .with_for_update()
            )
            if locked_document is None:
                raise NotFoundError("Không tìm thấy document của version")

            locked_document.domain = metadata.domain
            locked_document.audience = new_audience
            locked_version.code = metadata.code
            locked_version.issued_date = metadata.issued_date
            extra = dict(locked_version.extra_metadata or {})
            extra.update(
                {
                    "effective_date": _iso(metadata.effective_date),
                    "expiry_date": _iso(metadata.expiry_date),
                    "validity_status": metadata.validity_status,
                }
            )
            locked_version.extra_metadata = extra
            if effective_date is not None:
                await session.execute(
                    update(DocumentRecipient)
                    .where(
                        DocumentRecipient.document_version_id
                        == snapshot["version_id"]
                    )
                    .values(effective_date=effective_date)
                )
    except BaseException:
        await session.rollback()
        await asyncio.to_thread(
            replace_canonical_markdown,
            snapshot["canonical_path"],
            previous_markdown,
        )
        if payload_changed:
            await sync_payload(snapshot["domain"], snapshot["audience"])
        raise

    return DocumentVersionUpdateResponse(
        updated=True,
        document=await get_document_version(
            session,
            document_version_id=snapshot["version_id"],
        ),
    )


# Delete is deliberately conservative: indexed versions must be deindexed first.
# This prevents database metadata from pointing at vectors that still exist in Qdrant.
async def delete_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> None:
    """Delete a version through a retryable cross-store state machine."""

    version = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise NotFoundError(f"Document version {document_version_id} not found")
    if version.rag_status == "deactivated":
        job = await session.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.document_version_id == document_version_id,
                IngestionJob.job_type == "delete",
                IngestionJob.status.in_(["pending", "processing", "failed"]),
            )
            .order_by(IngestionJob.id.desc())
            .limit(1)
            .with_for_update()
        )
        if job is None:
            raise ConflictError("Delete state không có job tương ứng")
        _assert_lifecycle_job_retryable(job, operation="Delete")
    elif version.rag_status in ("not_indexed", "failed"):
        job = IngestionJob(
            document_version_id=version.id,
            job_type="delete",
            status="processing",
            current_step="external_cleanup",
            processed_chunks=0,
        )
        session.add(job)
        version.rag_status = "deactivated"
    else:
        raise ConflictError(
            f"Cannot delete indexed document (rag_status={version.rag_status}). "
            "Deindex first."
        )

    canonical_path = version.canonical_markdown_path
    source_path = version.source_path
    version_key = version.version_key
    job.status = "processing"
    job.current_step = "external_cleanup"
    job.error_message = None
    await session.flush()
    job_id = job.id
    await session.commit()

    # Repeating every cleanup operation is safe after a partial failure.
    try:
        await _cleanup_deleted_version_artifacts(
            version_key=version_key,
            object_paths=[canonical_path, source_path],
        )
    except Exception as exc:
        await _mark_lifecycle_job_failed(session, job_id, exc)
        raise ExternalServiceError(
            f"Không dọn được dữ liệu external của version: {exc}"
        ) from exc

    try:
        async with session.begin():
            version = await session.scalar(
                select(DocumentVersion)
                .where(DocumentVersion.id == document_version_id)
                .with_for_update()
            )
            if version is None:
                return
            if version.rag_status != "deactivated":
                raise ConflictError(
                    "Trạng thái RAG đã thay đổi trong lúc xóa document"
                )

            has_other_versions = await session.scalar(
                select(DocumentVersion.id)
                .where(
                    DocumentVersion.document_id == version.document_id,
                    DocumentVersion.id != document_version_id,
                )
                .limit(1)
            )
            document_id = version.document_id
            await session.delete(version)
            await session.flush()
            if has_other_versions is None:
                await session.execute(
                    delete(Document).where(Document.id == document_id)
                )
    except Exception as exc:
        await session.rollback()
        await _mark_lifecycle_job_failed(session, job_id, exc)
        raise



async def _cleanup_deleted_version_artifacts(
    *,
    version_key: str,
    object_paths: list[str | None],
) -> None:
    from app.vectorstore.qdrant_client import get_qdrant_client
    from app.vectorstore.repository import delete_points_by_version

    await asyncio.to_thread(
        delete_points_by_version,
        get_qdrant_client(),
        version_key=version_key,
    )

    for path in dict.fromkeys(path for path in object_paths if path):
        await asyncio.to_thread(delete_object, path)


# Publish and unpublish change lifecycle state; vector content is managed by indexing.
async def publish_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Mark document version as published."""
    return await _transition_rag_status(
        session,
        document_version_id=document_version_id,
        expected_status="indexed",
        target_status="published",
        timestamp_key="published_at",
        invalid_status_message="Document must be indexed before publishing",
    )


async def unpublish_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Mark document version as unpublished (but keep vectors)."""
    return await _transition_rag_status(
        session,
        document_version_id=document_version_id,
        expected_status="published",
        target_status="indexed",
        timestamp_key="unpublished_at",
        invalid_status_message="Document is not published",
    )


async def _transition_rag_status(
    session: AsyncSession,
    *,
    document_version_id: int,
    expected_status: str,
    target_status: str,
    timestamp_key: str,
    invalid_status_message: str,
) -> dict:
    version = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise NotFoundError(f"Document version {document_version_id} not found")
    if version.rag_status != expected_status:
        raise ConflictError(
            f"{invalid_status_message} (current: {version.rag_status})"
        )

    now = datetime.now(timezone.utc)
    version_key = version.version_key
    version.rag_status = target_status
    extra = dict(version.extra_metadata or {})
    extra[timestamp_key] = now.isoformat()
    version.extra_metadata = extra
    await session.commit()

    try:
        from app.vectorstore.qdrant_client import get_qdrant_client
        from app.vectorstore.repository import set_version_rag_status

        await asyncio.to_thread(
            set_version_rag_status,
            get_qdrant_client(),
            version_key=version_key,
            rag_status=target_status,
        )
    except Exception as exc:
        await session.rollback()
        version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
            .with_for_update()
        )
        if version is not None and version.rag_status == target_status:
            version.rag_status = expected_status
            extra = dict(version.extra_metadata or {})
            extra.pop(timestamp_key, None)
            version.extra_metadata = extra
            await session.commit()
        raise ExternalServiceError(
            f"Không cập nhật được trạng thái Qdrant: {exc}"
        ) from exc

    return {
        "document_version_id": document_version_id,
        "rag_status": target_status,
        timestamp_key: now,
    }


INDEXED_STATUSES = {"chunked", "embedded", "indexed", "published"}


# Deindex removes derived chunks/vectors while preserving the source document version.
async def deindex_document_version(
    session: AsyncSession,
    document_version_id: int,
) -> dict:
    """Remove chunks and vectors for a document version."""
    from app.databases.repositories.chunks import delete_chunks_by_version
    from app.vectorstore.qdrant_client import get_qdrant_client
    from app.vectorstore.repository import delete_points_by_version

    # Phase 1: reserve this version for deindex and commit the durable intent.
    version = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.id == document_version_id)
        .with_for_update()
    )
    if version is None:
        raise NotFoundError(f"Document version {document_version_id} not found")
    if version.rag_status == "deactivated":
        job = await session.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.document_version_id == document_version_id,
                IngestionJob.job_type == "deindex",
                IngestionJob.status.in_(["pending", "processing", "failed"]),
            )
            .order_by(IngestionJob.id.desc())
            .limit(1)
            .with_for_update()
        )
        if job is None:
            raise ConflictError("Deindex state không có job tương ứng")
        _assert_lifecycle_job_retryable(job, operation="Deindex")
    elif version.rag_status in INDEXED_STATUSES:
        active_indexing_job = await session.scalar(
            select(IngestionJob.id)
            .where(
                IngestionJob.document_version_id == document_version_id,
                IngestionJob.job_type == "indexing",
                IngestionJob.status == "processing",
            )
            .limit(1)
        )
        if active_indexing_job is not None:
            raise ConflictError(
                "Index đang được xử lý; chưa thể Deindex đồng thời"
            )
        job = IngestionJob(
            document_version_id=version.id,
            job_type="deindex",
            status="processing",
            current_step="qdrant_delete",
            processed_chunks=0,
        )
        session.add(job)
        version.rag_status = "deactivated"
    else:
        raise ConflictError(
            f"Document not indexed (rag_status={version.rag_status})"
        )
    job.status = "processing"
    job.current_step = "qdrant_delete"
    job.error_message = None
    version_key = version.version_key
    await session.flush()
    job_id = job.id
    await session.commit()

    # Phase 2: idempotent external deletion with no PostgreSQL transaction open.
    try:
        vectors_deleted = await asyncio.to_thread(
            delete_points_by_version,
            get_qdrant_client(),
            version_key=version_key,
        )
    except Exception as exc:
        await _mark_lifecycle_job_failed(session, job_id, exc)
        raise ExternalServiceError(
            f"Không xóa được vectors khỏi Qdrant: {exc}"
        ) from exc

    # Phase 3: finish PostgreSQL cleanup. A retry resumes from the deactivated
    # state and repeating the Qdrant deletion is safe.
    try:
        async with session.begin():
            version = await session.scalar(
                select(DocumentVersion)
                .where(DocumentVersion.id == document_version_id)
                .with_for_update()
            )
            job = await session.scalar(
                select(IngestionJob)
                .where(IngestionJob.id == job_id)
                .with_for_update()
            )
            if version is None or job is None:
                raise NotFoundError(
                    f"Không tìm thấy deindex state: {document_version_id}"
                )
            if version.rag_status != "deactivated":
                raise ConflictError(
                    "Trạng thái RAG đã thay đổi trong lúc deindex"
                )
            job.current_step = "postgres_cleanup"
            chunks_deleted = await delete_chunks_by_version(
                session,
                document_version_id,
            )
            version.rag_status = "not_indexed"
            job.status = "completed"
            job.current_step = "completed"
            job.error_message = None
    except Exception as exc:
        await session.rollback()
        await _mark_lifecycle_job_failed(session, job_id, exc)
        raise

    return {
        "document_version_id": document_version_id,
        "chunks_deleted": chunks_deleted,
        "vectors_deleted": vectors_deleted,
        "new_rag_status": "not_indexed",
    }


async def _mark_lifecycle_job_failed(
    session: AsyncSession,
    job_id: int,
    exc: BaseException,
) -> None:
    await session.rollback()
    async with session.begin():
        job = await session.scalar(
            select(IngestionJob)
            .where(IngestionJob.id == job_id)
            .with_for_update()
        )
        if job is not None:
            job.status = "failed"
            job.current_step = "failed"
            job.error_message = str(exc)
