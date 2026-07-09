from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.markdown_reader import read_markdown_document, split_frontmatter


def test_split_frontmatter_valid():
    frontmatter, body = split_frontmatter(VALID_MARKDOWN)

    assert frontmatter["document_key"] == "test-doc"
    assert "# Test Document" in body


def test_read_markdown_document_valid(tmp_path: Path):
    path = tmp_path / "test.md"
    path.write_text(VALID_MARKDOWN, encoding="utf-8")

    document = read_markdown_document(path)

    assert document.metadata.document_key == "test-doc"
    assert document.metadata.version_key == "test-doc-v1"
    assert document.body.startswith("# Test Document")


def test_reader_rejects_missing_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        split_frontmatter("# No YAML")


def test_reader_rejects_empty_body():
    text = """---
document_key: "x"
---
"""

    with pytest.raises(ValueError, match="empty"):
        split_frontmatter(text)


def test_reader_rejects_invalid_publish_status(tmp_path: Path):
    invalid = VALID_MARKDOWN.replace('ocr_status: "done"', 'ocr_status: "not_started"')
    path = tmp_path / "invalid.md"
    path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValidationError):
        read_markdown_document(path)