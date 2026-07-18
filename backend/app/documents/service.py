from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.databases.models.documents import Document, DocumentRecipient, DocumentVersion
from app.ingestion.canonical_storage import read_canonical_markdown
from app.schemas.documents_management import DocumentVersionDetail, DocumentVersionSummary


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _extra(version: DocumentVersion, key: str, default: Any = None) -> Any:
    return (version.extra_metadata or {}).get(key, default)


def _department_id(version: DocumentVersion) -> int | None:
    return version.recipients[0].department_id if version.recipients else None


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
        )
        .where(DocumentVersion.id == document_version_id)
    )
    version = await session.scalar(statement)
    if version is None:
        raise LookupError(f"Không tìm thấy document version: {document_version_id}")

    summary = _to_summary(version)
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
    )
