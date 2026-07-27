from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.databases.models.documents import DocumentType, Department
from app.schemas.reference import DocumentTypeResponse, DepartmentResponse


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
