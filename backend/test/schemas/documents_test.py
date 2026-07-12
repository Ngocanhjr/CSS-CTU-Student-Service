from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.documents import DocumentMetadata, DocumentVersionStatusFields


def test_document_version_status_fields_use_pipeline_defaults():
    status = DocumentVersionStatusFields()

    assert status.ocr_status == "not_started"
    assert status.review_status == "not_reviewed"
    assert status.rag_status == "not_indexed"
    assert status.status_note is None


def test_document_metadata_accepts_valid_published_document():
    document = DocumentMetadata(
        document_key="doc-001",
        version_key="doc-001-v1",
        title="Quy trinh mau",
        document_type="quy_trinh",
        ocr_status="done",
        review_status="approved",
        rag_status="published",
        checksum="abc123",
        responsible_department=["CTSV", "PDT"],
        effective_date=date(2026, 1, 1),
    )

    assert document.document_key == "doc-001"
    assert document.rag_status == "published"
    assert document.effective_date == date(2026, 1, 1)
    assert document.responsible_department == ["CTSV", "PDT"]


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("ocr_status", "not_started"),
        ("review_status", "not_reviewed"),
    ],
)
def test_published_document_requires_ready_statuses(field_name, field_value):
    data = {
        "document_key": "doc-001",
        "version_key": "doc-001-v1",
        "document_type": "quy_trinh",
        "ocr_status": "done",
        "review_status": "approved",
        "rag_status": "published",
        "checksum": "abc123",
    }
    data[field_name] = field_value

    with pytest.raises(ValidationError):
        DocumentMetadata(**data)


def test_document_requires_checksum():
    with pytest.raises(ValidationError):
        DocumentMetadata(
            document_key="doc-001",
            version_key="doc-001-v1",
            document_type="quy_trinh",
        )


def test_document_cleans_list_fields():
    document = DocumentMetadata(
        document_key="doc-001",
        version_key="doc-001-v1",
        document_type="quy_trinh",
        checksum="abc123",
        audience=[" sinh_vien ", "", " can_bo "],
        responsible_department=[" CTSV ", "PDT"],
    )

    assert document.audience == ["sinh_vien", "can_bo"]
    assert document.responsible_department == ["CTSV", "PDT"]


def test_document_rejects_legacy_english_audience_value():
    with pytest.raises(ValidationError):
        DocumentMetadata(
            document_key="doc-001",
            version_key="doc-001-v1",
            document_type="quy_trinh",
            checksum="abc123",
            audience=["student"],
        )
