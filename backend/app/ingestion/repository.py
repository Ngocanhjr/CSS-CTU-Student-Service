from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models.documents import (
    Document,
    DocumentType,
    DocumentVersion,
)
from app.databases.models.ingestion import IngestionJob
from app.schemas.documents import DocumentMetadata