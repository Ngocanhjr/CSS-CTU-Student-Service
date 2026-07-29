from __future__ import annotations
from typing import get_args

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.databases.models.documents import DocumentType, Department
from app.schemas.reference import DocumentTypeResponse, DepartmentResponse, EnumOptionsResponse

from app.schemas.enums import (
    Audience,
    Domain,
    OcrStatus,
    RagStatus,
    ReviewStatus,
    ValidityStatus,
    AssetType,
)

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/document-types", response_model=list[DocumentTypeResponse])
async def list_document_types(
    session: AsyncSession = Depends(get_session),
) -> list[DocumentTypeResponse]:
    result = await session.execute(
        select(DocumentType).where(DocumentType.is_active == True)
    )
    return result.scalars().all()


@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(
    session: AsyncSession = Depends(get_session),
) -> list[DepartmentResponse]:
    result = await session.execute(
        select(Department).where(Department.is_active == True)
    )
    return result.scalars().all()

@router.get("/enums", response_model=EnumOptionsResponse)
async def list_enum_options() -> EnumOptionsResponse:
    return EnumOptionsResponse(
        domains=list(get_args(Domain)),
        audiences=list(get_args(Audience)),
        ocr_statuses=list(get_args(OcrStatus)),
        review_statuses=list(get_args(ReviewStatus)),
        validity_statuses=list(get_args(ValidityStatus)),
        rag_statuses=list(get_args(RagStatus)),
        asset_types=list(get_args(AssetType)),
    )
