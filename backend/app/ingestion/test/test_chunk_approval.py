from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.ingestion.indexing_service import (
    _assert_approved_chunks_match,
    approve_chunk_preview,
)
from app.ingestion.chunking.chunker import ChunkingResult
from app.schemas.chunks import Chunk


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            document_key="doc",
            version_key="v1",
            chunk_key="v1::p::0001",
            chunk_index=0,
            chunk_type="parent",
            content="Parent",
            heading_path=["Mục 1"],
        ),
        Chunk(
            document_key="doc",
            version_key="v1",
            chunk_key="v1::c::0001",
            parent_chunk_key="v1::p::0001",
            chunk_index=1,
            chunk_type="child",
            content="Child",
            heading_path=["Mục 1"],
        ),
    ]


class _Session:
    def __init__(self) -> None:
        self.version = SimpleNamespace(
            id=7,
            ocr_status="done",
            review_status="approved",
            rag_status="not_indexed",
            canonical_markdown_path="canonical/v1.md",
            document=SimpleNamespace(domain="dao_tao", audience=["sinh_vien"]),
        )
        self.added = []

    async def scalar(self, _statement):
        return self.version

    def add(self, value):
        self.added.append(value)

    @asynccontextmanager
    async def begin(self):
        yield


class ChunkApprovalTest(IsolatedAsyncioTestCase):
    async def test_approve_persists_chunks_and_durable_step(self):
        chunks = _chunks()
        result = ChunkingResult(
            parent_chunks=[chunks[0]],
            child_chunks=[chunks[1]],
            warnings=[],
            errors=[],
        )
        snapshot = {
            "version_id": 7,
            "canonical_path": "canonical/v1.md",
            "domain": "dao_tao",
            "audience": ["sinh_vien"],
        }
        session = _Session()

        with (
            patch(
                "app.ingestion.indexing_service._build_chunking_snapshot",
                new=AsyncMock(return_value=(snapshot, object(), result)),
            ),
            patch(
                "app.ingestion.indexing_service.replace_version_chunks",
                new=AsyncMock(),
            ) as replace_chunks,
            patch(
                "app.ingestion.indexing_service._get_chunk_approval_job",
                new=AsyncMock(return_value=None),
            ),
        ):
            response = await approve_chunk_preview(
                session,
                document_version_id=7,
            )

        replace_chunks.assert_awaited_once_with(
            session,
            document_version_id=7,
            chunks=chunks,
        )
        self.assertTrue(response.approved)
        self.assertEqual(response.total_chunks, 2)
        self.assertEqual(session.added[0].current_step, "chunks_approved")

    def test_index_rejects_rows_different_from_approved_snapshot(self):
        parent, child = _chunks()
        rows = [
            SimpleNamespace(
                id=1,
                parent_chunk_id=None,
                chunk_key=parent.chunk_key,
                chunk_index=parent.chunk_index,
                chunk_type=parent.chunk_type,
                content=parent.content,
                heading_path=parent.heading_path,
                page_start=None,
                page_end=None,
                token_count=None,
            ),
            SimpleNamespace(
                id=2,
                parent_chunk_id=1,
                chunk_key=child.chunk_key,
                chunk_index=child.chunk_index,
                chunk_type=child.chunk_type,
                content=child.content,
                heading_path=child.heading_path,
                page_start=None,
                page_end=None,
                token_count=None,
            ),
        ]

        _assert_approved_chunks_match(rows, [parent, child])
        rows[1].content = "Changed"
        with self.assertRaisesRegex(Exception, "approve chunks lại"):
            _assert_approved_chunks_match(rows, [parent, child])
