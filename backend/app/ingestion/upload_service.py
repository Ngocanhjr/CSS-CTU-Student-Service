from __future__ import annotations

import asyncio
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.ingestion import IngestionJob
from app.ingestion.canonical_storage import (
    MAX_MARKDOWN_BYTES,
    create_canonical_markdown,
    delete_object,
    make_canonical_relative_path,
    MAX_SOURCE_BYTES,
    create_source_file,
    make_source_relative_path,
)

from app.databases.models.documents import (
    Department,
    Document,
    DocumentType,
    DocumentVersion,
)
from app.ingestion.metadata_persistence import persist_document_metadata

from app.schemas.documents import DocumentMetadata
from app.schemas.ingestion.responses import CanonicalUploadResponse

from hashlib import sha256
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from app.ingestion.markdown_reader import (
    render_markdown_document,
    split_frontmatter,
)
from app.schemas.ingestion.requests import RawMarkdownUploadMetadata

SAFE_VERSION_KEY = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,250}"
)

SOURCE_TYPE_BY_EXTENSION = {
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "docx",
    ".ppt": "ppt",
    ".pptx": "pptx",
    ".md": "md",
    ".markdown": "md",
}

SOURCE_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "md": "text/markdown; charset=utf-8",
}


def get_source_type(filename: str, content: bytes) -> tuple[str, str]:
    extension = Path(filename).suffix.lower()
    source_type = SOURCE_TYPE_BY_EXTENSION.get(extension)

    if source_type is None:
        raise ValueError(
            "File nguồn chỉ hỗ trợ PDF, DOC, DOCX, PPT, PPTX, MD hoặc Markdown"
        )

    if source_type == "pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("File nguồn PDF không hợp lệ")

    if source_type == "doc" and not content.startswith(
        bytes.fromhex("D0CF11E0A1B11AE1")
    ):
        raise ValueError("File nguồn DOC không hợp lệ")

    if source_type in {"docx", "pptx"}:
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
        except BadZipFile as exc:
            raise ValueError(
                f"File nguồn {source_type.upper()} không hợp lệ"
            ) from exc

        prefix = "word/" if source_type == "docx" else "ppt/"
        if "[Content_Types].xml" not in names or not any(
            name.startswith(prefix) for name in names
        ):
            raise ValueError(
                f"File nguồn {source_type.upper()} không hợp lệ"
            )

    if source_type == "md":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "File nguồn Markdown phải dùng UTF-8"
            ) from exc

    return source_type, ".md" if source_type == "md" else extension

async def upload_canonical_document(
    session: AsyncSession,
    *,
    filename: str,
    content: bytes,
    metadata_input: RawMarkdownUploadMetadata,
    source_department_code: str,
    source_filename: str | None = None,
    source_content: bytes | None = None,
) -> CanonicalUploadResponse:
    # 1. Kiểm tra file Markdown chính.
    if Path(filename).suffix.lower() not in {".md", ".markdown"}:
        raise ValueError(
            "Chỉ chấp nhận file Markdown có đuôi .md hoặc .markdown"
        )

    if not content:
        raise ValueError("File Markdown rỗng")

    if len(content) > MAX_MARKDOWN_BYTES:
        raise ValueError(f"File Markdown vượt quá {MAX_MARKDOWN_BYTES // 1024 // 1024} MB")

    if source_content is not None and len(source_content) > MAX_SOURCE_BYTES:
        raise ValueError(f"File nguồn vượt quá {MAX_SOURCE_BYTES // 1024 // 1024} MB")

    try:
        markdown = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Markdown phải dùng UTF-8") from exc

    # File cũ có YAML thì bỏ YAML cũ khỏi body.
    # Metadata cuối cùng luôn lấy từ metadata_input do frontend gửi.
    normalized = markdown.replace("\r\n", "\n")
    if normalized.startswith("---\n"):
        _, body = split_frontmatter(markdown)
    else:
        body = markdown.strip()

    if not body:
        raise ValueError("Nội dung Markdown rỗng")

    # version_key dùng làm định danh ổn định và một phần R2 object key.
    version_key = metadata_input.version_key
    if not SAFE_VERSION_KEY.fullmatch(version_key):
        raise ValueError(
            "version_key chỉ được chứa chữ, số, dấu chấm, "
            "gạch dưới và gạch ngang"
        )

    # 2. Kiểm tra phòng ban nguồn và các phòng ban phụ trách.
    # Transaction ngắn này kết thúc trước khi gọi R2.
    department_code = source_department_code.strip()
    if not department_code:
        raise ValueError("source_department_code là bắt buộc")

    responsible_codes = list(
        dict.fromkeys(
            code.strip()
            for code in metadata_input.responsible_department
            if code.strip()
        )
    )
    if not responsible_codes:
        raise ValueError("Phải chọn ít nhất một phòng ban phụ trách")

    all_codes = set(responsible_codes)
    all_codes.add(department_code)

    async with session.begin():
        active_codes = set(
            (
                await session.scalars(
                    select(Department.code).where(
                        Department.code.in_(all_codes),
                        Department.is_active.is_(True),
                    )
                )
            ).all()
        )

    if department_code not in active_codes:
        raise ValueError(
            "Phòng ban lưu file nguồn không tồn tại hoặc đã bị khóa"
        )

    missing_codes = set(responsible_codes) - active_codes
    if missing_codes:
        raise ValueError(
            "Phòng ban phụ trách không tồn tại hoặc đã bị khóa: "
            + ", ".join(sorted(missing_codes))
        )

    # 3. Xác định file gốc và checksum.
    # Nếu không có source_file riêng, Markdown upload là source MD.
    if source_filename is not None:
        if source_content is None:
            raise ValueError("Nội dung file nguồn bị thiếu")

        source_type, source_extension = get_source_type(
            source_filename,
            source_content,
        )
        source_bytes = source_content
        source_checksum = sha256(source_content).hexdigest()
    else:
        source_type = "md"
        source_extension = ".md"
        source_bytes = content
        source_checksum = sha256(content).hexdigest()

    # 4. Chỉ lưu R2 object key vào PostgreSQL/YAML, không lưu URL ký sẵn.
    canonical_relative_path = make_canonical_relative_path(
        version_key,
        department_code,
    )
    source_relative_path = make_source_relative_path(
        version_key,
        department_code,
        source_extension,
    )

    # 5. Backend sở hữu các field kỹ thuật và lifecycle.
    metadata = DocumentMetadata.model_validate(
        {
            **metadata_input.model_dump(exclude_none=True),
            "checksum": source_checksum,
            "canonical_markdown_path": canonical_relative_path,
            "source_path": source_relative_path,
            "file_type": source_type,
            "responsible_department": responsible_codes,
            "ocr_status": "done",
            "review_status": "reviewing",
            "rag_status": "not_indexed",
        }
    )

    canonical_markdown = render_markdown_document(metadata, body)
    provenance_checksum = metadata.checksum
    if metadata.effective_date is None and metadata.issued_date is None:
        raise ValueError(
            "responsible_department yêu cầu effective_date hoặc issued_date"
        )

    canonical_created = False
    source_created = False

    try:
        # 6. Gọi R2 trước; không giữ PostgreSQL transaction khi gọi external I/O.
        await asyncio.to_thread(
            create_canonical_markdown,
            canonical_relative_path,
            canonical_markdown,
        )
        canonical_created = True

        await asyncio.to_thread(
            create_source_file,
            source_relative_path,
            source_bytes,
            SOURCE_CONTENT_TYPES[source_type],
        )
        source_created = True

        # 7. Transaction PostgreSQL ngắn.
        async with session.begin():
            document_type = await session.scalar(
                select(DocumentType).where(
                    DocumentType.code == metadata.document_type,
                    DocumentType.is_active.is_(True),
                )
            )
            if document_type is None:
                raise ValueError(
                    "document_type chưa được seed hoặc đã bị khóa: "
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

            version = DocumentVersion(
                document_id=document.id,
                version_key=metadata.version_key,
                source_path=source_relative_path,
                canonical_markdown_path=canonical_relative_path,
                checksum=provenance_checksum,
            )
            session.add(version)
            await persist_document_metadata(
                session,
                document=document,
                version=version,
                document_type_id=document_type.id,
                metadata=metadata,
                review_status="reviewing",
            )

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

    except BaseException:
        # 8. Chỉ dọn object do request này vừa tạo.
        if source_created:
            try:
                await asyncio.to_thread(delete_object, source_relative_path)
            except Exception:
                pass

        if canonical_created:
            try:
                await asyncio.to_thread(delete_object, canonical_relative_path)
            except Exception:
                pass

        raise
