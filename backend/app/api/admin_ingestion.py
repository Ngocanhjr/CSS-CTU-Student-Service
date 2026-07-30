from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session

from app.ingestion.review_service import (
    review_canonical_document,
)
from app.ingestion.upload_service import (
    upload_canonical_document,
)

from app.schemas.ingestion.responses import (
    CanonicalUploadResponse,
    ReviewCanonicalResponse,
)
from pydantic import ValidationError
from app.schemas.ingestion.indexing import ChunkPreviewResponse, IndexingJobProgress
from app.ingestion.indexing_service import (
    build_chunk_preview,
    get_indexing_job_progress,
    run_indexing_job,
    start_index_document_version,
)
from app.admin.debug_service import (
    get_chunks_debug,
    get_vectors_debug,
    search_test,
)
from app.schemas.admin_debug import (
    ChunksDebugResponse,
    VectorsDebugResponse,
    SearchTestResponse,
)

from app.ingestion.markdown_reader import split_frontmatter
from app.schemas.ingestion.responses import (
    CanonicalUploadResponse,
    MarkdownMetadataPreviewResponse,
    ReviewCanonicalResponse,
)

from fastapi import Form
from app.ingestion.canonical_storage import MAX_MARKDOWN_BYTES, MAX_SOURCE_BYTES, get_source_preview_url
from app.schemas.ingestion.requests import (
    RawMarkdownUploadMetadata,
    ReviewCanonicalRequest,
)

from fastapi.responses import RedirectResponse

from app.databases.models.documents import DocumentVersion

from pathlib import Path

from sqlalchemy import select

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
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    try:
        job = await start_index_document_version(session, document_version_id=document_version_id)
        # ponytail: in-process job; use a queue when restart-safe workers are required.
        background_tasks.add_task(run_indexing_job, job.ingestion_job_id)
        return job
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/ingestion-jobs/{ingestion_job_id}", response_model=IndexingJobProgress)
async def get_indexing_job(
    ingestion_job_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await get_indexing_job_progress(session, ingestion_job_id=ingestion_job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

PREVIEW_METADATA_KEYS = {
    "title",
    "document_key",
    "version_key",
    "document_type",
    "domain",
    "audience",
    "code",
    "issued_date",
    "effective_date",
    "source_url",
}


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
            raise ValueError("File Markdown vượt quá 10 MB")

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
            canonical_markdown=payload.canonical_markdown,
            assets=payload.assets,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Canonical Markdown trong database "
                "không tồn tại trên filesystem"
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/chunks/{document_version_id}",
    response_model=ChunksDebugResponse,
)
async def debug_chunks(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get all chunks for a document version (debug endpoint)."""
    try:
        return await get_chunks_debug(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/vectors/{document_version_id}",
    response_model=VectorsDebugResponse,
)
async def debug_vectors(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get vectors from Qdrant for a document version (debug endpoint)."""
    try:
        # Verify document version exists first
        from app.databases.models.documents import DocumentVersion
        version = await session.get(DocumentVersion, document_version_id)
        if not version:
            raise HTTPException(status_code=404, detail=f"Document version {document_version_id} not found")
        return await get_vectors_debug(document_version_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Qdrant unavailable") from exc


@router.get(
    "/search-test",
    response_model=SearchTestResponse,
)
async def test_search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    department_id: int | None = Query(default=None),
):
    """Test vector search without LLM generation (debug endpoint)."""
    try:
        return await search_test(
            query=q,
            top_k=top_k,
            department_id=department_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    
    
@router.get(
    "/document-versions/{document_version_id}/source-preview",
    response_class=RedirectResponse,
)
async def preview_source_file(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    version = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == document_version_id
        )
    )

    if version is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy document version",
        )

    if not version.source_path:
        raise HTTPException(
            status_code=404,
            detail="Version này không có file nguồn",
        )

    return RedirectResponse(
        url=get_source_preview_url(version.source_path),
        status_code=307,
    )
