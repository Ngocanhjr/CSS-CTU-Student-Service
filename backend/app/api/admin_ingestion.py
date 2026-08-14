from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pathlib import Path
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session

from app.ingestion.review_service import (
    review_canonical_document,
)
from app.ingestion.upload_service import (
    upload_canonical_document,
)

from app.schemas.ingestion.indexing import ChunkPreviewResponse, IndexingJobProgress
from app.ingestion.indexing_service import (
    build_chunk_preview,
    get_indexing_job_progress,
    run_indexing_job,
    start_index_document_version,
)
from app.ingestion.markdown_reader import split_frontmatter
from app.schemas.ingestion.responses import (
    CanonicalUploadResponse,
    MarkdownMetadataPreviewResponse,
    ReviewCanonicalResponse,
)

from app.ingestion.canonical_storage import MAX_MARKDOWN_BYTES, MAX_SOURCE_BYTES
from app.schemas.ingestion.requests import (
    RawMarkdownUploadMetadata,
    ReviewCanonicalRequest,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-ingestion"],
)


def _upload_error_detail(exc: Exception) -> dict:
    if isinstance(exc, ValidationError):
        return {
            "code": "metadata_validation_failed",
            "phase": "metadata",
            "message": "YAML frontmatter không hợp lệ",
            "fields": [
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors()
            ],
        }

    message = str(exc)
    if "document_type chưa được seed" in message:
        code, phase = "reference_data_missing", "database_reference"
    elif "version_key đã tồn tại" in message:
        code, phase = "duplicate_version", "database"
    elif "frontmatter" in message.lower():
        code, phase = "invalid_frontmatter", "markdown"
    else:
        code, phase = "upload_validation_failed", "upload"

    return {"code": code, "phase": phase, "message": message, "fields": []}


@router.post("/document-versions/{document_version_id}/chunk-preview", response_model=ChunkPreviewResponse)
async def preview_chunks(document_version_id: int, session: AsyncSession = Depends(get_session)):
    try:
        return await build_chunk_preview(session, document_version_id=document_version_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/document-versions/{document_version_id}/index",
    response_model=IndexingJobProgress,
    status_code=202,
)
async def index_version(
    document_version_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    job = await start_index_document_version(
        session,
        document_version_id=document_version_id,
    )
    # ponytail: in-process job; use a queue when restart-safe workers are required.
    background_tasks.add_task(run_indexing_job, job.ingestion_job_id)
    return job


@router.get("/ingestion-jobs/{ingestion_job_id}", response_model=IndexingJobProgress)
async def get_indexing_job(
    ingestion_job_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await get_indexing_job_progress(
        session,
        ingestion_job_id=ingestion_job_id,
    )

PREVIEW_METADATA_KEYS = set(RawMarkdownUploadMetadata.model_fields)


@router.post(
    "/canonical-markdown/metadata-preview",
    response_model=MarkdownMetadataPreviewResponse,
)
async def preview_markdown_metadata(
    file: UploadFile = File(...),
) -> MarkdownMetadataPreviewResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file bị thiếu")

    try:
        if Path(file.filename).suffix.lower() not in {".md", ".markdown"}:
            raise ValueError("Chỉ chấp nhận file Markdown")

        content = await file.read(MAX_MARKDOWN_BYTES + 1)
        if len(content) > MAX_MARKDOWN_BYTES:
            raise ValueError(f"File Markdown vượt quá {MAX_MARKDOWN_BYTES // 1024 // 1024} MB")

        try:
            markdown = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Markdown phải dùng UTF-8") from exc

        # Markdown thô không có YAML vẫn hợp lệ: chỉ trả form rỗng.
        frontmatter = {}
        if markdown.replace("\r\n", "\n").startswith("---\n"):
            frontmatter, _ = split_frontmatter(markdown)

        return MarkdownMetadataPreviewResponse(
            metadata={
                key: value
                for key, value in frontmatter.items()
                if key in PREVIEW_METADATA_KEYS
            }
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
        
@router.post(
    "/canonical-markdown",
    response_model=CanonicalUploadResponse,
    status_code=201,
)
async def upload_canonical_markdown(
    # Canonical Markdown bắt buộc: nội dung sẽ được chuẩn hóa rồi lưu R2.
    file: UploadFile = File(...),
    # Metadata form frontend, gửi dạng JSON trong multipart/form-data.
    metadata_json: str = Form(...),
    # Stable department.code, dùng kiểm tra quyền/active và tạo R2 object key.
    source_department_code: str = Form(...),
    # File gốc tùy chọn (PDF/DOC/DOCX/PPT/PPTX/Markdown), lưu R2 nguyên bản.
    source_file: UploadFile | None = File(default=None),
    session: AsyncSession = Depends(get_session),
) -> CanonicalUploadResponse:
    """Nhận một canonical Markdown và tối đa một file nguồn trong một multipart request."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Tên file Markdown bị thiếu")

    try:
        # Parse trước để trả lỗi metadata sớm, trước khi gọi storage/database.
        metadata = RawMarkdownUploadMetadata.model_validate_json(metadata_json)

        # Đọc tối đa limit + 1 byte; service sẽ trả lỗi nếu vượt giới hạn.
        content = await file.read(MAX_MARKDOWN_BYTES + 1)

        source_content = None
        source_filename = None
        if source_file is not None:
            if not source_file.filename:
                raise ValueError("Tên file nguồn bị thiếu")

            source_filename = source_file.filename
            source_content = await source_file.read(MAX_SOURCE_BYTES + 1)

        # Service sở hữu validation, R2 rollback và transaction PostgreSQL.
        return await upload_canonical_document(
            session,
            filename=file.filename,
            content=content,
            metadata_input=metadata,
            source_department_code=source_department_code,
            source_filename=source_filename,
            source_content=source_content,
        )

    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "Metadata không hợp lệ", "fields": exc.errors()},
        ) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="Canonical Markdown của version này đã tồn tại",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=_upload_error_detail(exc),
        ) from exc
    finally:
        await file.close()
        if source_file is not None:
            await source_file.close()

@router.put(
    "/canonical-markdown/{document_version_id}/review",
    response_model=ReviewCanonicalResponse,
)
async def review_canonical_markdown(
    document_version_id: int,
    payload: ReviewCanonicalRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewCanonicalResponse:
    try:
        return await review_canonical_document(
            session,
            document_version_id=document_version_id,
            markdown_body=payload.markdown_body,
            metadata=payload.metadata,
            assets=payload.assets,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Canonical Markdown trong database "
                "không tồn tại trên filesystem"
            ),
        ) from exc

