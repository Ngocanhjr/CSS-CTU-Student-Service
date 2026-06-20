from app.schemas import (
    AssetMetadata,
    Chunk,
    DocumentAssetRelation,
    DocumentBaseMetadata,
    DocumentMetadata,
    DocumentVersionMetadata,
    DocumentVersionStatus,
)


def test_schema_package_exports_public_models():
    assert AssetMetadata is not None
    assert Chunk is not None
    assert DocumentAssetRelation is not None
    assert DocumentBaseMetadata is not None
    assert DocumentMetadata is not None
    assert DocumentVersionMetadata is not None
    assert DocumentVersionStatus is not None
