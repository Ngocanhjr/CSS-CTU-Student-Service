from typing import get_args

import pytest
from pydantic import ValidationError

from app.ocr.validation.apply_metadata import BACKEND_AUDIENCES, BACKEND_DOCUMENT_TYPES
from app.schemas.documents import DocumentBaseMetadata
from app.schemas.enums import Audience, DocumentType


def test_ocr_enum_contract_uses_schema_values() -> None:
    assert BACKEND_AUDIENCES == set(get_args(Audience))
    assert BACKEND_DOCUMENT_TYPES == set(get_args(DocumentType))


def test_document_schema_rejects_invalid_domain() -> None:
    with pytest.raises(ValidationError):
        DocumentBaseMetadata(
            document_key="document",
            document_type="unknown",
            domain="invalid",
        )
