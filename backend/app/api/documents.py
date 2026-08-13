from __future__ import annotations

from typing import Literal

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.databases.models import DocumentVersion
from app.databases.session import get_session
from app.documents.service import (
    deindex_document_version,
    delete_document_version,
    get_document_version,
    list_document_versions,
    publish_document_version,
    unpublish_document_version,
    update_document_version,
    update_document_version_assets,
)
from app.ingestion.canonical_storage import get_object_preview_url
from app.schemas.base import StrictSchema
from app.schemas.documents_management import (
    DeindexResponse,
    DocumentAssetsUpdateRequest,
    DocumentVersionDetail,
    DocumentVersionSummary,
    DocumentVersionUpdateRequest,
    DocumentVersionUpdateResponse,
    PublishResponse,
    UnpublishResponse,
)


router = APIRouter(prefix="/versions", tags=["documents"])

PreviewFileType = Literal["source", "canonical_markdown"]


class DocumentPreviewUrlResponse(StrictSchema):
    version_key: str
    file_type: PreviewFileType
    url: str
    expires_minutes: int = 5


@router.get("", response_model=list[DocumentVersionSummary])
async def list_versions(
    query: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    document_type_id: int | None = Query(default=None),
    rag_status: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentVersionSummary]:
    return await list_document_versions(
        session,
        query=query,
        department_id=department_id,
        document_type_id=document_type_id,
        rag_status=rag_status,
        review_status=review_status,
    )


@router.get(
    "/preview-url/{version_key}",
    response_model=DocumentPreviewUrlResponse,
)
async def get_version_preview_url(
    version_key: str,
    file_type: PreviewFileType = Query(...),
    session: AsyncSession = Depends(get_session),
) -> DocumentPreviewUrlResponse:
    """Tạo URL tạm thời để client xem file nguồn hoặc bản OCR trên R2."""

    version = (
        await session.execute(
            select(DocumentVersion).where(
                DocumentVersion.version_key == version_key
            )
        )
    ).scalar_one_or_none()

    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên bản tài liệu.",
        )

    if file_type == "source":
        relative_path = version.source_path
    else:
        relative_path = version.canonical_markdown_path

    if not relative_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên bản tài liệu không có file tương ứng.",
        )

    try:
        preview_url = await run_in_threadpool(
            get_object_preview_url,
            relative_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy file trên Cloudflare R2.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except (RuntimeError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tạo đường dẫn xem file trên Cloudflare R2.",
        ) from exc

    return DocumentPreviewUrlResponse(
        version_key=version.version_key,
        file_type=file_type,
        url=preview_url,
        expires_minutes=5,
    )


@router.get(
    "/{document_version_id}",
    response_model=DocumentVersionDetail,
)
async def get_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> DocumentVersionDetail:
    return await get_document_version(
        session,
        document_version_id=document_version_id,
    )


@router.put(
    "/{document_version_id}",
    response_model=DocumentVersionUpdateResponse,
)
async def update_version(
    document_version_id: int,
    payload: DocumentVersionUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentVersionUpdateResponse:
    return await update_document_version(
        session,
        document_version_id=document_version_id,
        payload=payload,
    )


@router.put(
    "/{document_version_id}/assets",
    response_model=DocumentVersionDetail,
)
async def update_version_assets(
    document_version_id: int,
    payload: DocumentAssetsUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentVersionDetail:
    return await update_document_version_assets(
        session,
        document_version_id=document_version_id,
        payload=payload,
    )


@router.delete(
    "/{document_version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a document version if it has not been indexed."""

    await delete_document_version(
        session,
        document_version_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_version_id}/publish",
    response_model=PublishResponse,
)
async def publish_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> PublishResponse:
    """Publish a document version to make it available in the RAG chatbot."""

    return await publish_document_version(
        session,
        document_version_id,
    )


@router.post(
    "/{document_version_id}/unpublish",
    response_model=UnpublishResponse,
)
async def unpublish_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> UnpublishResponse:
    """Unpublish a document version to hide it from the RAG chatbot."""

    return await unpublish_document_version(
        session,
        document_version_id,
    )


@router.post(
    "/{document_version_id}/deindex",
    response_model=DeindexResponse,
)
async def deindex_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> DeindexResponse:
    """Remove chunks and vectors for a document version to allow editing."""

    return await deindex_document_version(
        session,
        document_version_id,
    )
