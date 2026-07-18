from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.ingestion.canonical_storage import (
    MAX_MARKDOWN_BYTES,
)
from app.ingestion.review_service import (
    review_canonical_document,
)
from app.ingestion.upload_service import (
    upload_canonical_document,
)
from app.schemas.ingestion.requests import (
    ReviewCanonicalRequest,
)
from app.schemas.ingestion.responses import (
    CanonicalUploadResponse,
    ReviewCanonicalResponse,
)
from pydantic import ValidationError
from app.schemas.ingestion.indexing import ChunkPreviewResponse, IndexingResponse
from app.ingestion.indexing_service import build_chunk_preview, index_document_version


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


@router.post("/document-versions/{document_version_id}/index", response_model=IndexingResponse)
async def index_version(document_version_id: int, session: AsyncSession = Depends(get_session)):
    try:
        return await index_document_version(session, document_version_id=document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/canonical-markdown",
    response_model=CanonicalUploadResponse,
    status_code=201,
)
async def upload_canonical_markdown(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> CanonicalUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Tên file bị thiếu",
        )

    try:
        content = await file.read(
            MAX_MARKDOWN_BYTES + 1
        )

        return await upload_canonical_document(
            session,
            filename=file.filename,
            content=content,
        )

    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Canonical Markdown của version này "
                "đã tồn tại"
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=_upload_error_detail(exc),
        ) from exc

    finally:
        await file.close()


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
            canonical_markdown=(
                payload.canonical_markdown
            ),
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
