import os
from datetime import date, datetime, timezone

import pytest
from dotenv import load_dotenv
from sqlalchemy import delete, select

from app.databases.models import (
    Asset,
    Department,
    Document,
    DocumentAsset,
    DocumentChunk,
    DocumentType,
    DocumentVersion,
    DocumentVersionRelationship,
    DocumentVersionStatus,
    IngestionJob,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL.endswith("/ctu_student_service_test"):
    pytest.skip(
        "Database smoke tests require DATABASE_URL ending with /ctu_student_service_test",
        allow_module_level=True,
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
        now = datetime.now(timezone.utc)

        department = Department(
            code="TEST",
            name="Phong Test",
            description="Only for database smoke test",
            updated_at=now,
        )
        document_type = DocumentType(
            code="guide",
            name="Huong dan test",
            description="Only for database smoke test",
            updated_at=now,
        )

        try:
            session.add_all([department, document_type])
            await session.flush()

            document = Document(
                document_key="test-document",
                title="Test Document",
                department_id=department.id,
                document_type_id=document_type.id,
                domain="test",
                audience=["student"],
                updated_at=now,
            )
            session.add(document)
            await session.flush()

            version = DocumentVersion(
                document_id=document.id,
                title="Test Document V1",
                code="TEST-001",
                issued_date=date(2026, 6, 19),
                effective_date=date(2026, 6, 19),
                expiry_date=date(2026, 12, 31),
                is_latest=True,
                version_key="test-document-v1",
                version_label="v1",
                version_role="base",
                source_url="",
                source_file="test.md",
                source_path="test/test.md",
                file_type="md",
                canonical_markdown_path="test/test.md",
                language="vi",
                citation_type="section",
                checksum="test-checksum",
                updated_at=now,
            )
            session.add(version)
            await session.flush()

            status = DocumentVersionStatus(
                document_version_id=version.id,
                validity_status="valid",
                collection_status="collected",
                ocr_status="done",
                review_status="approved",
                rag_status="published",
                updated_at=now,
            )

            asset = Asset(
                asset_key="test-asset",
                asset_type="form",
                title="Test Asset",
                file_path="",
                file_type="pdf",
                download_url="",
                validity_status="valid",
                is_latest=True,
                review_status="approved",
                rag_status="published",
            )

            session.add_all([status, asset])
            await session.flush()

            document_asset = DocumentAsset(
                document_version_id=version.id,
                asset_id=asset.id,
                relation_type="reference",
                required=False,
                display_order=0,
            )

            parent_chunk = DocumentChunk(
                document_version_id=version.id,
                chunk_index=0,
                chunk_level="parent",
                heading_path=["Root"],
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
                parent_id=parent_chunk.id,
                chunk_index=1,
                chunk_level="child",
                heading_path=["Root", "Child"],
                section_title="Child",
                content="Child content",
                page_start=1,
                page_end=1,
                token_count=2,
                qdrant_point_id="test-point-1",
                index_status="not_indexed",
            )

            relationship = DocumentVersionRelationship(
                source_version_id=version.id,
                target_version_id=version.id,
                relation_type="self_test",
            )

            job = IngestionJob(
                document_version_id=version.id,
                job_type="smoke_test",
                status="done",
                current_stage="database",
                tool_name="pytest",
                processed_chunks=1,
                created_by="pytest",
            )

            session.add_all([child_chunk, relationship, job])
            await session.commit()

            result = await session.execute(
                select(Document).where(Document.document_key == "test-document")
            )
            assert result.scalar_one().title == "Test Document"
        finally:
            await session.rollback()
            await cleanup_test_data(session)
