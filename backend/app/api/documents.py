from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("/{document_version_id}", response_model=DocumentVersionDetail)
async def get_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> DocumentVersionDetail:
    try:
        return await get_document_version(
            session,
            document_version_id=document_version_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{document_version_id}", response_model=DocumentVersionUpdateResponse)
async def update_version(
    document_version_id: int,
    payload: DocumentVersionUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentVersionUpdateResponse:
    try:
        return await update_document_version(
            session,
            document_version_id=document_version_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put(
    "/{document_version_id}/assets",
    response_model=DocumentVersionDetail,
)
async def update_version_assets(
    document_version_id: int,
    payload: DocumentAssetsUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> DocumentVersionDetail:
    try:
        return await update_document_version_assets(
            session,
            document_version_id=document_version_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/{document_version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a document version if not indexed."""
    try:
        await delete_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{document_version_id}/publish",
    response_model=PublishResponse,
)
async def publish_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> PublishResponse:
    """Publish a document version to make it available in RAG chatbot."""
    try:
        return await publish_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/{document_version_id}/unpublish",
    response_model=UnpublishResponse,
)
async def unpublish_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> UnpublishResponse:
    """Unpublish a document version to hide it from RAG chatbot."""
    try:
        return await unpublish_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/{document_version_id}/deindex",
    response_model=DeindexResponse,
)
async def deindex_version(
    document_version_id: int,
    session: AsyncSession = Depends(get_session),
) -> DeindexResponse:
    """Remove chunks and vectors for a document version to allow editing."""
    try:
        return await deindex_document_version(session, document_version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
