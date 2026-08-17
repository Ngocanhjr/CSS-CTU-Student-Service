from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.documents.service import delete_document_version


class _Session:
    def __init__(self, *, has_other_versions):
        self.version = SimpleNamespace(
            id=7,
            document_id=3,
            version_key="version-7",
            rag_status="not_indexed",
            canonical_markdown_path="canonical/test.md",
            source_path="source/test.md",
        )
        self._scalars = iter(
            [self.version, self.version, has_other_versions]
        )
        self.added = []
        self.executed = []
        self.deleted = []
        self.commits = 0

    async def scalar(self, _statement):
        return next(self._scalars)

    def add(self, value):
        self.added.append(value)

    async def execute(self, statement):
        self.executed.append(statement)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        if self.added and self.added[-1].id is None:
            self.added[-1].id = 11

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass

    @asynccontextmanager
    async def begin(self):
        yield


class DeleteDocumentVersionTest(IsolatedAsyncioTestCase):
    async def test_external_cleanup_precedes_database_delete(self):
        session = _Session(has_other_versions=None)

        with patch(
            "app.documents.service._cleanup_deleted_version_artifacts",
            new=AsyncMock(),
        ) as cleanup:
            await delete_document_version(session, 7)

        cleanup.assert_awaited_once_with(
            version_key="version-7",
            object_paths=["canonical/test.md", "source/test.md"],
        )
        self.assertEqual(session.version.rag_status, "deactivated")
        self.assertEqual(session.commits, 1)
        self.assertEqual(session.deleted, [session.version])
        self.assertTrue(
            any(
                "DELETE FROM css.documents" in str(item)
                for item in session.executed
            )
        )

    async def test_parent_remains_when_another_version_exists(self):
        session = _Session(has_other_versions=8)

        with patch(
            "app.documents.service._cleanup_deleted_version_artifacts",
            new=AsyncMock(),
        ):
            await delete_document_version(session, 7)

        self.assertFalse(
            any(
                "DELETE FROM css.documents" in str(item)
                for item in session.executed
            )
        )
