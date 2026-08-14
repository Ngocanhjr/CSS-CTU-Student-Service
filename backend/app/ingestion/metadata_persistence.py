from __future__ import annotations

import json

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import (
    Department,
    Document,
    DocumentRecipient,
    DocumentVersion,
)
from app.core.exceptions import ConflictError
from app.schemas.documents import DocumentMetadata
from app.schemas.enums import ReviewStatus


async def persist_document_metadata(
    session: AsyncSession,
    *,
    document: Document,
    version: DocumentVersion,
    document_type_id: int,
    metadata: DocumentMetadata,
    review_status: ReviewStatus,
) -> None:
    """Persist the shared Upload/Review metadata projection."""

    await validate_shared_document_metadata(
        session,
        document=document,
        version=version,
        document_type_id=document_type_id,
        metadata=metadata,
    )

    document.title = metadata.title
    document.domain = metadata.domain
    document.audience = list(metadata.audience)
    document.document_type_id = document_type_id

    version.title = metadata.title
    version.code = metadata.code
    version.issued_date = metadata.issued_date
    version.issuing_authority = metadata.issuing_authority
    version.signer_name = metadata.signer_name
    version.is_latest = metadata.is_latest
    version.source_url = metadata.source_url
    version.source_path = metadata.source_path or ""
    version.file_type = metadata.file_type
    version.language = metadata.language
    version.accessed_date = metadata.accessed_date
    version.extra_metadata = _build_extra_metadata(metadata)
    version.ocr_status = "done"
    version.review_status = review_status
    version.rag_status = "not_indexed"
    version.status_note = None

    # New versions need an id before recipients can reference them.
    await session.flush()

    if metadata.is_latest:
        await session.execute(
            update(DocumentVersion)
            .where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.id != version.id,
                DocumentVersion.is_latest.is_(True),
            )
            .values(is_latest=False)
        )

    await _replace_recipients(
        session,
        document_version_id=version.id,
        metadata=metadata,
    )


async def validate_shared_document_metadata(
    session: AsyncSession,
    *,
    document: Document,
    version: DocumentVersion,
    document_type_id: int,
    metadata: DocumentMetadata,
) -> None:
    """Reject version-local changes to fields stored on Document."""

    sibling_version_id = await session.scalar(
        select(DocumentVersion.id)
        .where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.id != version.id,
        )
        .limit(1)
    )
    if sibling_version_id is not None:
        shared_changes = []
        if document.domain != metadata.domain:
            shared_changes.append("domain")
        if set(document.audience) != set(metadata.audience):
            shared_changes.append("audience")
        if document.document_type_id != document_type_id:
            shared_changes.append("document_type")
        if shared_changes:
            raise ConflictError(
                "Các trường dùng chung không thể khác giữa các version: "
                + ", ".join(shared_changes)
            )


def _build_extra_metadata(metadata: DocumentMetadata) -> dict:
    extra_fields = set(metadata.model_extra or {}) | {
        "parser",
        "ocr_engine",
        "notes",
        "effective_date",
        "expiry_date",
        "validity_status",
        "responsible_department",
    }
    return json.loads(metadata.model_dump_json(include=extra_fields))


async def _replace_recipients(
    session: AsyncSession,
    *,
    document_version_id: int,
    metadata: DocumentMetadata,
) -> None:
    department_codes = list(
        dict.fromkeys(metadata.responsible_department)
    )
    effective_date = metadata.effective_date or metadata.issued_date

    if department_codes and effective_date is None:
        raise ValueError(
            "responsible_department yêu cầu "
            "effective_date hoặc issued_date"
        )

    departments: list[Department] = []
    if department_codes:
        departments = list(
            (
                await session.scalars(
                    select(Department).where(
                        Department.code.in_(department_codes),
                        Department.is_active.is_(True),
                    )
                )
            ).all()
        )
        found_codes = {department.code for department in departments}
        missing_codes = [
            code for code in department_codes if code not in found_codes
        ]
        if missing_codes:
            raise ValueError(
                "Department chưa được seed hoặc đã bị khóa: "
                + ", ".join(missing_codes)
            )

    await session.execute(
        delete(DocumentRecipient).where(
            DocumentRecipient.document_version_id
            == document_version_id
        )
    )

    if effective_date is not None:
        session.add_all(
            [
                DocumentRecipient(
                    document_version_id=document_version_id,
                    department_id=department.id,
                    effective_date=effective_date,
                )
                for department in departments
            ]
        )
