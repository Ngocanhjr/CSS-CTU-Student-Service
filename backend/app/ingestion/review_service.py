from __future__ import annotations

import json

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import (
    Department,
    Document,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
)
from app.databases.models.ingestion import IngestionJob
from app.ingestion.canonical_storage import (
    MAX_MARKDOWN_BYTES,
    read_canonical_markdown,
    replace_canonical_markdown,
)
from app.ingestion.markdown_reader import (
    render_markdown_document,
    split_frontmatter,
)
from app.schemas.documents import DocumentMetadata
from app.schemas.ingestion.responses import ReviewCanonicalResponse


async def review_canonical_document(
    session: AsyncSession,
    *,
    document_version_id: int,
    canonical_markdown: str,
) -> ReviewCanonicalResponse:
    previous_markdown: str | None = None
    canonical_path: str | None = None
    file_replaced = False

    try:
        async with session.begin():
            version = await session.scalar(
                select(DocumentVersion)
                .where(DocumentVersion.id == document_version_id)
                .with_for_update()
            )

            if version is None:
                raise LookupError(
                    f"Không tìm thấy document version: "
                    f"{document_version_id}"
                )

            if version.rag_status != "not_indexed":
                raise ValueError(
                    "Không thể review version đã được đưa vào RAG; "
                    "cần deindex trước"
                )

            document = await session.scalar(
                select(Document)
                .where(Document.id == version.document_id)
                .with_for_update()
            )

            if document is None:
                raise RuntimeError(
                    "DocumentVersion không có Document tương ứng"
                )

            reviewed_markdown, metadata = _prepare_reviewed_markdown(
                canonical_markdown=canonical_markdown,
                stored_document_key=document.document_key,
                stored_version_key=version.version_key,
                stored_checksum=version.checksum,
                canonical_markdown_path=(
                    version.canonical_markdown_path
                ),
            )

            document_type = await session.scalar(
                select(DocumentType).where(
                    DocumentType.code == metadata.document_type
                )
            )

            if document_type is None:
                raise ValueError(
                    f"document_type chưa được seed: "
                    f"{metadata.document_type}"
                )

            await _sync_recipients(
                session,
                document_version_id=version.id,
                metadata=metadata,
            )

            if metadata.is_latest:
                await session.execute(
                    update(DocumentVersion)
                    .where(
                        DocumentVersion.document_id
                        == document.id,
                        DocumentVersion.id != version.id,
                        DocumentVersion.is_latest.is_(True),
                    )
                    .values(is_latest=False)
                )

            document.title = metadata.title
            document.domain = metadata.domain
            document.audience = list(metadata.audience)
            document.document_type_id = document_type.id

            version.title = metadata.title
            version.code = metadata.code
            version.issued_date = metadata.issued_date
            version.issuing_authority = (
                metadata.issuing_authority
            )
            version.signer_name = metadata.signer_name
            version.is_latest = metadata.is_latest
            version.source_url = metadata.source_url
            version.source_path = metadata.source_path or ""
            version.file_type = metadata.file_type
            version.language = metadata.language
            version.accessed_date = metadata.accessed_date
            version.extra_metadata = _build_extra_metadata(
                metadata
            )
            version.ocr_status = "done"
            version.review_status = "approved"
            version.rag_status = "not_indexed"
            version.status_note = None

            job = await session.scalar(
                select(IngestionJob)
                .where(
                    IngestionJob.document_version_id
                    == version.id,
                    IngestionJob.job_type == "ingestion",
                )
                .order_by(IngestionJob.id.desc())
                .limit(1)
                .with_for_update()
            )

            if job is None:
                job = IngestionJob(
                    document_version_id=version.id,
                    job_type="ingestion",
                    status="pending",
                    current_step="chunking",
                    processed_chunks=0,
                )
                session.add(job)
            else:
                job.status = "pending"
                job.current_step = "chunking"
                job.error_message = None

            # Phát hiện lỗi constraint trước khi thay file.
            await session.flush()

            canonical_path = version.canonical_markdown_path
            previous_markdown = read_canonical_markdown(
                canonical_path
            )

            replace_canonical_markdown(
                canonical_path,
                reviewed_markdown,
            )
            file_replaced = True

            response = ReviewCanonicalResponse(
                document_version_id=version.id,
                review_status="approved",
                rag_status="not_indexed",
                markdown=reviewed_markdown,
                metadata=metadata,
            )

        return response

    except BaseException:
        # PostgreSQL rollback thì khôi phục canonical file cũ.
        if (
            file_replaced
            and previous_markdown is not None
            and canonical_path is not None
        ):
            try:
                replace_canonical_markdown(
                    canonical_path,
                    previous_markdown,
                )
            except OSError as restore_error:
                raise RuntimeError(
                    "Review thất bại và không thể khôi phục "
                    "canonical Markdown"
                ) from restore_error

        raise


def _prepare_reviewed_markdown(
    *,
    canonical_markdown: str,
    stored_document_key: str,
    stored_version_key: str,
    stored_checksum: str,
    canonical_markdown_path: str,
) -> tuple[str, DocumentMetadata]:
    if not canonical_markdown.strip():
        raise ValueError("Canonical Markdown rỗng")

    if (
        len(canonical_markdown.encode("utf-8"))
        > MAX_MARKDOWN_BYTES
    ):
        raise ValueError("Canonical Markdown vượt quá 10 MB")

    frontmatter, body = split_frontmatter(
        canonical_markdown
    )

    immutable_fields = {
        "document_key": stored_document_key,
        "version_key": stored_version_key,
        "checksum": stored_checksum,
    }

    for field, expected_value in immutable_fields.items():
        if frontmatter.get(field) != expected_value:
            raise ValueError(
                f"Không được thay đổi {field} khi review"
            )

    frontmatter.update(
        {
            "canonical_markdown_path": (
                canonical_markdown_path
            ),
            "ocr_status": "done",
            "review_status": "approved",
            "rag_status": "not_indexed",
            "status_note": None,
        }
    )

    metadata = DocumentMetadata.model_validate(
        frontmatter
    )

    if not metadata.title.strip():
        raise ValueError("Metadata title không được rỗng")

    reviewed_markdown = render_markdown_document(
        metadata,
        body,
    )

    return reviewed_markdown, metadata


def _build_extra_metadata(
    metadata: DocumentMetadata,
) -> dict:
    extra_fields = set(metadata.model_extra or {}) | {
        "parser",
        "ocr_engine",
        "notes",
        "effective_date",
        "responsible_department",
    }

    return json.loads(
        metadata.model_dump_json(
            include=extra_fields
        )
    )


async def _sync_recipients(
    session: AsyncSession,
    *,
    document_version_id: int,
    metadata: DocumentMetadata,
) -> None:
    department_codes = list(
        dict.fromkeys(metadata.responsible_department)
    )

    effective_date = (
        metadata.effective_date
        or metadata.issued_date
    )

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
                        Department.code.in_(
                            department_codes
                        ),
                        Department.is_active.is_(True),
                    )
                )
            ).all()
        )

        found_codes = {
            department.code
            for department in departments
        }

        missing_codes = [
            code
            for code in department_codes
            if code not in found_codes
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

    if effective_date is None:
        return

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