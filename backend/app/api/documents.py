from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.documents.service import get_document_version, list_document_versions
from app.schemas.documents_management import DocumentVersionDetail, DocumentVersionSummary


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
