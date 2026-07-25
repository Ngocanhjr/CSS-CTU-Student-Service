from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import yaml
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.databases.models.documents import (
    Department,
    Document,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
)
from app.ingestion.canonical_storage import read_canonical_markdown
from app.ingestion.markdown_reader import split_frontmatter
from app.ingestion.review_service import review_canonical_document
from app.schemas.documents_management import (
    DocumentVersionDetail,
    DocumentVersionSummary,
    DocumentVersionUpdateRequest,
    DocumentVersionUpdateResponse,
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


async def get_document_version(
    session: AsyncSession,
    *,
    document_version_id: int,
) -> DocumentVersionDetail:
    statement = (
        select(DocumentVersion)
        .options(
            selectinload(DocumentVersion.document),
            selectinload(DocumentVersion.recipients),
            selectinload(DocumentVersion.ingestion_jobs),
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

    return DocumentVersionDetail(
        **summary.model_dump(),
        canonical_markdown=markdown,
        canonical_markdown_path=version.canonical_markdown_path,
        source_path=version.source_path,
        source_url=version.source_url,
        checksum=version.checksum,
        last_job_id=job.id if job else None,
        last_job_status=job.status if job else None,
        last_job_step=job.current_step if job else None,
        last_job_error=job.error_message if job else None,
        last_job_processed_chunks=job.processed_chunks if job else None,
        last_job_total_chunks=job.total_chunks if job else None,
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

    if metadata.department_id is not None:
        department = await session.scalar(
            select(Department).where(
                Department.id == metadata.department_id,
                Department.is_active.is_(True),
            )
        )
        if department is None:
            raise ValueError("Department không tồn tại hoặc đã bị khóa")
        frontmatter["responsible_department"] = [department.code]

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
