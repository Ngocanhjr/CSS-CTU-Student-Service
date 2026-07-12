import os
from datetime import date
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv
from sqlalchemy import delete, select

from app.databases.models import (
    Asset,
    Department,
    Document,
    DocumentAsset,
    DocumentChunk,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
    IngestionJob,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    raise RuntimeError(
        "Refusing to run database smoke tests unless DATABASE_URL points to "
        "ctu_student_service_test"
    )

from app.databases.session import AsyncSessionLocal  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def cleanup_test_data(session):
    await session.execute(delete(Document).where(Document.document_key == "test-document"))
    await session.execute(delete(Asset).where(Asset.asset_key == "test-asset"))
    await session.execute(delete(Department).where(Department.code == "TEST"))
    await session.execute(delete(DocumentType).where(DocumentType.code == "guide"))
    await session.commit()


async def test_insert_core_database_models():
    async with AsyncSessionLocal() as session:
        await cleanup_test_data(session)

        department = Department(
            code="TEST",
            name="Phong Test",
            description="Only for database smoke test",
        )
        document_type = DocumentType(
            code="guide",
            name="Huong dan test",
            description="Only for database smoke test",
        )

        try:
            session.add_all([department, document_type])
            await session.flush()

            document = Document(
                document_key="test-document",
                title="Test Document",
                document_type_id=document_type.id,
                domain="test",
                audience=["sinh_vien"],
            )
            session.add(document)
            await session.flush()

            # Status fields (ocr/review/rag) nam truc tiep tren document_versions.
            version = DocumentVersion(
                document_id=document.id,
                version_key="test-document-v1",
                title="Test Document V1",
                code="TEST-001",
                issued_date=date(2026, 6, 19),
                is_latest=True,
                source_url="",
                source_path="test/test.md",
                canonical_markdown_path="test/test.md",
                file_type="md",
                language="vi",
                issuing_authority="Phong Test",
                signer_name="",
                checksum="test-checksum",
                accessed_date=date(2026, 6, 19),
                ocr_status="done",
                review_status="approved",
                rag_status="published",
            )
            session.add(version)
            await session.flush()
            await session.refresh(version)
            assert version.updated_at is not None
            initial_updated_at = version.updated_at

            version.title = "Test Document V1 Updated"
            await session.flush()
            await session.refresh(version)
            assert version.updated_at is not None
            assert version.updated_at >= initial_updated_at

            recipient = DocumentRecipient(
                document_version_id=version.id,
                department_id=department.id,
                effective_date=date(2026, 6, 19),
            )

            asset = Asset(
                asset_key="test-asset",
                title="Test Asset",
                asset_type="form",
                url="",
                checksum=None,
            )

            session.add_all([recipient, asset])
            await session.flush()

            document_asset = DocumentAsset(
                document_version_id=version.id,
                asset_id=asset.id,
                relation_type="reference",
                required_when=None,
                display_order=0,
            )

            parent_chunk = DocumentChunk(
                document_version_id=version.id,
                chunk_key="test-document-v1::p::0001",
                chunk_index=0,
                chunk_type="parent",
                heading_path="Root",
                section_title="Root",
                content="Parent content",
                page_start=1,
                page_end=1,
                token_count=2,
                index_status="not_indexed",
            )

            session.add_all([document_asset, parent_chunk])
            await session.flush()

            child_chunk = DocumentChunk(
                document_version_id=version.id,
                parent_chunk_id=parent_chunk.id,
                chunk_key="test-document-v1::c::0001",
                chunk_index=1,
                chunk_type="child",
                heading_path="Root > Child",
                section_title="Child",
                content="Child content",
                page_start=1,
                page_end=1,
                token_count=2,
                qdrant_point_id="test-point-1",
                index_status="not_indexed",
            )

            job = IngestionJob(
                document_version_id=version.id,
                job_type="smoke_test",
                status="done",
                current_step="database",
                processed_chunks=1,
                created_by="pytest",
            )

            session.add_all([child_chunk, job])
            await session.commit()

            result = await session.execute(
                select(Document).where(Document.document_key == "test-document")
            )
            assert result.scalar_one().title == "Test Document"
        finally:
            await session.rollback()
            await cleanup_test_data(session)
