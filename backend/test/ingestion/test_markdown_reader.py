from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ingestion.markdown_reader import read_markdown_document, split_frontmatter


VALID_MARKDOWN = """---
document_key: "test-doc"
version_key: "test-doc-v1"
title: "Test Document"
document_type: "quy_trinh"
domain: "test"
department: "PDT"
audience:
  - "student"
version_label: "v1"
version_role: "base"
is_latest: true
source_file: "test.md"
source_path: "test.md"
canonical_markdown_path: "test.md"
file_type: "md"
language: "vi"
citation_type: "page"
checksum: "test-checksum"
collection_status: "collected"
ocr_status: "done"
review_status: "approved"
validity_status: "valid"
rag_status: "published"
---

# Test Document
"""


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
