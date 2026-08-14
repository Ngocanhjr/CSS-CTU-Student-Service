from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ApplicationError,
    ConflictError,
    ConflictError,
    ExternalServiceError,
    InvalidRequestError,
    NotFoundError,
)
from app.databases.asset_repository import replace_document_assets
from app.databases.models.documents import (
    Document,
    DocumentType,
    DocumentVersion,
)
from app.databases.models.ingestion import IngestionJob
from app.ingestion.canonical_storage import (
    MAX_MARKDOWN_BYTES,
    create_canonical_markdown,
    delete_object,
    make_canonical_revision_path,
)

from app.ingestion.markdown_reader import (
    render_markdown_document,
)
from app.ingestion.metadata_persistence import (
    persist_document_metadata,
    validate_shared_document_metadata,
)

from app.schemas.documents import DocumentMetadata
from app.schemas.ingestion.responses import ReviewCanonicalResponse
from app.schemas.assets import AssetWrite

REVIEW_METADATA_FIELDS = {
    "title",
    "document_type",
    "domain",
    "audience",
    "responsible_department",
    "code",
    "issuing_authority",
    "signer_name",
    "issued_date",
    "effective_date",
    "expiry_date",
    "validity_status",
    "is_latest",
    "source_url",
    "language",
    "accessed_date",
    "parser",
    "ocr_engine",
    "notes",
}

logger = logging.getLogger(__name__)

async def review_canonical_document(
    session: AsyncSession,
    *,
    document_version_id: int,
    markdown_body: str,
    metadata: DocumentMetadata,
    assets: list[AssetWrite] | None = None,
) -> ReviewCanonicalResponse:
    try:
        return await _review_canonical_document(
            session,
            document_version_id=document_version_id,
            markdown_body=markdown_body,
            submitted_metadata=metadata,
            assets=assets,
        )
    except ApplicationError:
        raise
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc
    except RuntimeError as exc:
        raise ExternalServiceError(str(exc)) from exc


async def _review_canonical_document(
    session: AsyncSession,
    *,
    document_version_id: int,
    markdown_body: str,
    submitted_metadata: DocumentMetadata,
    assets: list[AssetWrite] | None = None,
) -> ReviewCanonicalResponse:
    # Phase 1: validate and snapshot using only a short PostgreSQL transaction.
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

        previous_canonical_path = version.canonical_markdown_path
        next_canonical_path = make_canonical_revision_path(
            previous_canonical_path
        )
        reviewed_markdown, metadata = _prepare_reviewed_markdown(
            markdown_body=markdown_body,
            submitted_metadata=submitted_metadata,
            stored_document_key=document.document_key,
            stored_version_key=version.version_key,
            stored_checksum=version.checksum,
            stored_source_path=version.source_path,
            stored_file_type=version.file_type,
            canonical_markdown_path=next_canonical_path,
        )
        document_type = await session.scalar(
            select(DocumentType).where(
                DocumentType.code == metadata.document_type,
                DocumentType.is_active.is_(True),
            )
        )
        if document_type is None:
            raise ValueError(
                f"document_type chưa được seed hoặc đã bị khóa: "
                f"{metadata.document_type}"
            )
        await validate_shared_document_metadata(
            session,
            document=document,
            version=version,
            document_type_id=document_type.id,
            metadata=metadata,
        )

    # Phase 2: create a new immutable R2 object outside PostgreSQL.
    try:
        await asyncio.to_thread(
            create_canonical_markdown,
            next_canonical_path,
            reviewed_markdown,
        )
    except Exception as exc:
        raise ExternalServiceError(
            f"Không thể lưu canonical Markdown lên R2: {exc}"
        ) from exc

    try:
        # Phase 3: atomically point PostgreSQL at the completed object.
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
            if (
                version.rag_status != "not_indexed"
                or version.canonical_markdown_path
                != previous_canonical_path
            ):
                raise ConflictError(
                    "Document version đã thay đổi; vui lòng tải lại trang"
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

            document_type = await session.scalar(
                select(DocumentType).where(
                    DocumentType.code == metadata.document_type,
                    DocumentType.is_active.is_(True),
                )
            )
            if document_type is None:
                raise ValueError(
                    f"document_type chưa được seed hoặc đã bị khóa: "
                    f"{metadata.document_type}"
                )

            version.canonical_markdown_path = next_canonical_path
            await persist_document_metadata(
                session,
                document=document,
                version=version,
                document_type_id=document_type.id,
                metadata=metadata,
                review_status="approved",
            )

            if assets is not None:
                await replace_document_assets(
                    session,
                    document_version_id=version.id,
                    assets=assets,
                )

            job = await session.scalar(
                select(IngestionJob)
                .where(
                    IngestionJob.document_version_id == version.id,
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

            await session.flush()
            response = ReviewCanonicalResponse(
                document_version_id=version.id,
                review_status="approved",
                rag_status="not_indexed",
                markdown=reviewed_markdown,
                metadata=metadata,
            )
    except BaseException:
        try:
            await asyncio.to_thread(delete_object, next_canonical_path)
        except Exception:
            logger.warning(
                "Không thể dọn canonical revision sau review lỗi: %s",
                next_canonical_path,
                exc_info=True,
            )
        raise

    # The database now points at the new object; old-object cleanup is harmless
    # and retryable, so it must not turn a successful review into an error.
    if previous_canonical_path != next_canonical_path:
        try:
            await asyncio.to_thread(delete_object, previous_canonical_path)
        except Exception:
            logger.warning(
                "Không thể dọn canonical revision cũ: %s",
                previous_canonical_path,
                exc_info=True,
            )

    return response


def _prepare_reviewed_markdown(
    *,
    markdown_body: str,
    submitted_metadata: DocumentMetadata,
    stored_document_key: str,
    stored_version_key: str,
    stored_checksum: str,
    stored_source_path: str,
    stored_file_type: str,
    canonical_markdown_path: str,
) -> tuple[str, DocumentMetadata]:
    if not markdown_body.strip():
        raise ValueError("Nội dung Markdown rỗng")

    frontmatter = submitted_metadata.model_dump(
        mode="json",
        include=REVIEW_METADATA_FIELDS,
    )
    frontmatter.update(
        {
            "document_key": stored_document_key,
            "version_key": stored_version_key,
            "checksum": stored_checksum,
            "source_path": stored_source_path,
            "file_type": stored_file_type,
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
        markdown_body,
    )
    if len(reviewed_markdown.encode("utf-8")) > MAX_MARKDOWN_BYTES:
        raise ValueError(
            "Canonical Markdown vượt quá "
            f"{MAX_MARKDOWN_BYTES // 1024 // 1024} MB"
        )

    return reviewed_markdown, metadata


