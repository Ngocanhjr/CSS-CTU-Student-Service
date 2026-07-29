"""
Dùng lưu link youtube, form
"""

from __future__ import annotations
from datetime import datetime

from pydantic import AnyHttpUrl, Field

from app.schemas.base import StrictSchema
from app.schemas.enums import (
    AssetType,
    DocumentAssetRelationType,
)


class AssetWrite(StrictSchema):
    title: str = Field(min_length=1, max_length=500)
    url: AnyHttpUrl
    asset_type: AssetType


class LinkedAssetResponse(StrictSchema):
    asset_key: str
    title: str
    url: str
    asset_type: AssetType
    relation_type: DocumentAssetRelationType
    display_order: int = Field(ge=0)

class AssetMetadata(StrictSchema):
    asset_key: str = Field(min_length=1)
    asset_type: AssetType
    title: str = ""
    
    url: str = ""
    checksum: str | None = None
    created_at: datetime | None = None

class DocumentAssetRelation(StrictSchema):
    document_key: str = Field(min_length=1)
    #version_key: str = Field(min_length=1)
    asset_key: str = Field(min_length=1)

    relation_type: DocumentAssetRelationType = "reference"
    required_when: str | None = None
    display_order: int = Field(default=0, ge=0)
