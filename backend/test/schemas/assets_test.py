import pytest
from pydantic import ValidationError

from app.schemas.assets import AssetMetadata, DocumentAssetRelation


def test_asset_metadata_accepts_valid_asset():
    asset = AssetMetadata(
        asset_key="form-cap-bang-diem",
        asset_type="form",
        title="Don xin cap bang diem",
        file_type="docx",
    )

    assert asset.asset_key == "form-cap-bang-diem"
    assert asset.file_type == "docx"
    assert asset.rag_status == "not_indexed"


def test_asset_metadata_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AssetMetadata(
            asset_key="form-cap-bang-diem",
            asset_type="form",
            unknown_field=True,
        )


def test_document_asset_relation_accepts_defaults():
    relation = DocumentAssetRelation(
        document_key="doc-001",
        asset_key="asset-001",
    )

    assert relation.relation_type == "reference"
    assert relation.required is False
    assert relation.display_order == 0


def test_document_asset_relation_rejects_negative_display_order():
    with pytest.raises(ValidationError):
        DocumentAssetRelation(
            document_key="doc-001",
            asset_key="asset-001",
            display_order=-1,
        )
