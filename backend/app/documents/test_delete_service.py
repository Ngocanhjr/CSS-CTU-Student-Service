from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app.documents.service import delete_document_version


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, *, has_other_versions):
        self.version = SimpleNamespace(
            id=7,
            document_id=3,
            rag_status="not_indexed",
            canonical_markdown_path=None,
            source_path=None,
        )
        self.has_other_versions = has_other_versions
        self.executed = []
        self.committed = False

    async def execute(self, statement):
        self.executed.append(statement)
        return _Result(self.version) if len(self.executed) == 1 else None

    async def scalar(self, _statement):
        if not hasattr(self, "version_reloaded"):
            self.version_reloaded = True
            return self.version
        return self.has_other_versions

    async def rollback(self):
        pass

    async def delete(self, _value):
        pass

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True


class DeleteDocumentVersionTest(IsolatedAsyncioTestCase):
    async def test_parent_is_deleted_only_with_last_version(self):
        last_version = _Session(has_other_versions=None)
        last_version.version.canonical_markdown_path = "canonical/test.md"
        last_version.version.source_path = "source/test.md"
        with (
            patch("app.documents.service.delete_canonical_markdown") as delete_canonical,
            patch("app.documents.service.delete_source_file") as delete_source,
        ):
            await delete_document_version(last_version, 7)
        delete_canonical.assert_called_once_with("canonical/test.md")
        delete_source.assert_called_once_with("source/test.md")
        self.assertIn("DELETE FROM css.documents", str(last_version.executed[-1]))
        self.assertTrue(last_version.committed)

        has_history = _Session(has_other_versions=8)
        await delete_document_version(has_history, 7)
        self.assertNotIn("DELETE FROM css.documents", str(has_history.executed[-1]))
        self.assertTrue(has_history.committed)
