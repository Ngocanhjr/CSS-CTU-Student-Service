from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.documents import DocumentMetadata, DocumentVersionStatus


def test_document_version_status_uses_pipeline_defaults():
    status = DocumentVersionStatus()

    assert status.validity_status == "unchecked"
    assert status.collection_status == "collected"
    assert status.ocr_status == "not_started"
    assert status.review_status == "not_reviewed"
    assert status.rag_status == "not_indexed"


def test_document_metadata_accepts_valid_published_document():
    document = DocumentMetadata(
        document_key="doc-001",
        version_key="doc-001-v1",
        title="Quy trinh mau",
        document_type="quy_trinh",
        ocr_status="done",
        review_status="approved",
        validity_status="valid",
        rag_status="published",
        checksum="abc123",
    )

    assert document.document_key == "doc-001"
    assert document.rag_status == "published"


def test_expired_indexed_document_is_allowed():
    document = DocumentMetadata(
        document_key="doc-old",
        version_key="doc-old-v1",
        document_type="quy_trinh",
        ocr_status="done",
        review_status="approved",
        validity_status="expired",
        rag_status="indexed",
        checksum="abc123",
    )

    assert document.validity_status == "expired"
    assert document.rag_status == "indexed"


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("ocr_status", "not_started"),
        ("review_status", "not_reviewed"),
        ("validity_status", "expired"),
    ],
)
def test_published_document_requires_ready_statuses(field_name, field_value):
    data = {
        "document_key": "doc-001",
        "version_key": "doc-001-v1",
        "document_type": "quy_trinh",
        "ocr_status": "done",
        "review_status": "approved",
        "validity_status": "valid",
        "rag_status": "published",
        "checksum": "abc123",
    }
    data[field_name] = field_value

    with pytest.raises(ValidationError):
        DocumentMetadata(**data)


def test_document_rejects_invalid_effective_expiry_range():
    with pytest.raises(ValidationError):
        DocumentMetadata(
            document_key="doc-001",
            version_key="doc-001-v1",
            document_type="quy_trinh",
            checksum="abc123",
            effective_date=date(2026, 1, 2),
            expiry_date=date(2026, 1, 1),
        )


def test_replaced_document_requires_replaced_by():
    with pytest.raises(ValidationError):
        DocumentMetadata(
            document_key="doc-old",
            version_key="doc-old-v1",
            document_type="quy_trinh",
            validity_status="replaced",
            checksum="abc123",
        )


@pytest.mark.parametrize(
    ("version_role", "relation_field"),
    [
        ("replacement", "replaces"),
        ("amendment", "amends"),
        ("supplement", "supplements"),
    ],
)
def test_version_roles_require_relation_keys(version_role, relation_field):
    valid_data = {
        "document_key": "doc-001",
        "version_key": "doc-001-v1",
        "document_type": "quy_trinh",
        "checksum": "abc123",
        "version_role": version_role,
        relation_field: ["doc-old-v1"],
    }

    assert DocumentMetadata(**valid_data).version_role == version_role

    invalid_data = dict(valid_data)
    invalid_data[relation_field] = []

    with pytest.raises(ValidationError):
        DocumentMetadata(**invalid_data)


def test_document_cleans_list_fields():
    document = DocumentMetadata(
        document_key="doc-001",
        version_key="doc-001-v1",
        document_type="quy_trinh",
        checksum="abc123",
        audience=[" sinh vien ", "", " can bo "],
        related_asset_keys=[" asset-001 ", "", "asset-002"],
    )

    assert document.audience == ["sinh vien", "can bo"]
    assert document.related_asset_keys == ["asset-001", "asset-002"]
