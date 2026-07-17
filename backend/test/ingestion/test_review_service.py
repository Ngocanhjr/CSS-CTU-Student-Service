import pytest

from app.ingestion.markdown_reader import split_frontmatter
from app.ingestion.review_service import _prepare_reviewed_markdown


SOURCE = """---
document_key: qd3266
version_key: qd3266-v1
document_type: quyet_dinh
title: Quy định học vụ
checksum: ocr-provenance-checksum
---

# Nội dung
"""


def test_review_approves_and_preserves_checksum():
    reviewed, metadata = _prepare_reviewed_markdown(
        canonical_markdown=SOURCE,
        stored_document_key="qd3266",
        stored_version_key="qd3266-v1",
        stored_checksum="ocr-provenance-checksum",
        canonical_markdown_path="storage/canonical/qd3266-v1.md",
    )

    frontmatter, _ = split_frontmatter(reviewed)

    assert metadata.review_status == "approved"
    assert metadata.rag_status == "not_indexed"
    assert frontmatter["checksum"] == "ocr-provenance-checksum"


def test_review_rejects_changed_checksum():
    with pytest.raises(ValueError, match="Không được thay đổi checksum"):
        _prepare_reviewed_markdown(
            canonical_markdown=SOURCE.replace(
                "ocr-provenance-checksum",
                "changed-checksum",
            ),
            stored_document_key="qd3266",
            stored_version_key="qd3266-v1",
            stored_checksum="ocr-provenance-checksum",
            canonical_markdown_path="storage/canonical/qd3266-v1.md",
        )
