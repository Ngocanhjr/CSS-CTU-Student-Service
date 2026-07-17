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


router = APIRouter(
    prefix="/admin",
    tags=["admin-ingestion"],
)


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
            detail=str(exc),
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