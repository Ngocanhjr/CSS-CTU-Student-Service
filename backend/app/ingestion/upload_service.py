from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import (
    Document,
    DocumentType,
    DocumentVersion,
)
from app.databases.models.ingestion import IngestionJob
from app.ingestion.canonical_storage import (
    MAX_MARKDOWN_BYTES,
    create_canonical_markdown,
    delete_canonical_markdown,
    make_canonical_relative_path,
)
from app.ingestion.markdown_reader import (
    render_markdown_document,
    split_frontmatter,
)
from app.schemas.documents import DocumentMetadata
from app.schemas.ingestion.responses import CanonicalUploadResponse

SAFE_VERSION_KEY = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,250}"
)

async def upload_canonical_document(
    session: AsyncSession,
    *,
    filename: str,
    content: bytes,
) -> CanonicalUploadResponse:
    if Path(filename).suffix.lower() != ".md":
        raise ValueError("Chỉ chấp nhận file Markdown có đuôi .md")

    if not content:
        raise ValueError("File Markdown rỗng")

    if len(content) > MAX_MARKDOWN_BYTES:
        raise ValueError("File Markdown vượt quá 10 MB")

    try:
        markdown = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Markdown phải dùng UTF-8") from exc
    
    # Parse YAML trước khi đọc version_key.
    frontmatter, body = split_frontmatter(markdown)
    version_key = frontmatter.get("version_key")
    
    if not isinstance(version_key, str) or not SAFE_VERSION_KEY.fullmatch(version_key):
        raise ValueError(
            "version_key chỉ được chứa chữ, số, dấu chấm, gạch dưới và gạch ngang"
        )

   
    
    canonical_relative_path = make_canonical_relative_path(
        version_key
    )
    
    frontmatter.update(
        {
            "canonical_markdown_path": canonical_relative_path,
            "ocr_status": "done",
            "review_status": "reviewing",
            "rag_status": "not_indexed",
        }
    )
    
    metadata = DocumentMetadata.model_validate(frontmatter)

    if not metadata.title.strip():
        raise ValueError("Metadata title không được rỗng")
    
    canonical_markdown = render_markdown_document(
        metadata,
        body,
    )
    
    provenance_checksum = metadata.checksum
     
    extra_fields = set(metadata.model_extra or {}) | {
        "parser",
        "ocr_engine",
        "notes",
        "effective_date",
        "responsible_department",
    }

    extra_metadata = json.loads(
        metadata.model_dump_json(include=extra_fields)
    )
    
    #bridge giữa filesystem và database
    file_created = False

    try:
        create_canonical_markdown(
            canonical_relative_path,
            canonical_markdown,
        )
        file_created = True

        async with session.begin():
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

            existing_version = await session.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.version_key == metadata.version_key
                )
            )
            if existing_version is not None:
                raise ValueError(
                    f"version_key đã tồn tại: {metadata.version_key}"
                )

            document = await session.scalar(
                select(Document).where(
                    Document.document_key == metadata.document_key
                )
            )

            if document is None:
                document = Document(
                    document_key=metadata.document_key,
                    title=metadata.title,
                    domain=metadata.domain,
                    audience=list(metadata.audience),
                    document_type_id=document_type.id,
                )
                session.add(document)
                await session.flush()
            else:
                document.title = metadata.title
                document.domain = metadata.domain
                document.audience = list(metadata.audience)
                document.document_type_id = document_type.id

            if metadata.is_latest:
                await session.execute(
                    update(DocumentVersion)
                    .where(
                        DocumentVersion.document_id == document.id,
                        DocumentVersion.is_latest.is_(True),
                    )
                    .values(is_latest=False)
                )

            version = DocumentVersion(
                document_id=document.id,
                version_key=metadata.version_key,
                title=metadata.title,
                code=metadata.code,
                issued_date=metadata.issued_date,
                issuing_authority=metadata.issuing_authority,
                signer_name=metadata.signer_name,
                is_latest=metadata.is_latest,
                source_url=metadata.source_url,
                source_path=metadata.source_path or "",
                canonical_markdown_path=canonical_relative_path,
                file_type=metadata.file_type,
                language=metadata.language,
                accessed_date=metadata.accessed_date,
                checksum=provenance_checksum,
                extra_metadata=extra_metadata,
                ocr_status="done",
                review_status="reviewing",
                rag_status="not_indexed",
            )
            session.add(version)
            await session.flush()

            job = IngestionJob(
                document_version_id=version.id,
                job_type="ingestion",
                status="pending",
                current_step="review",
                processed_chunks=0,
            )
            session.add(job)
            await session.flush()

            response = CanonicalUploadResponse(
                document_id=document.id,
                document_version_id=version.id,
                ingestion_job_id=job.id,
                markdown=canonical_markdown,
                metadata=metadata,
            )

        return response

    except Exception:
        if file_created:
            try:
                delete_canonical_markdown(
                    canonical_relative_path
                )
            except OSError:
                pass
        raise
 