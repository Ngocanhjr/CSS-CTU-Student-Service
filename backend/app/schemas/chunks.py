from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.base import StrictSchema
from app.schemas.enums import ChunkType

class Chunk(StrictSchema):
    document_key: str = Field(min_length=1)
    version_key: str = Field(min_length=1)

    chunk_id: str = Field(min_length=1)
    parent_chunk_id: str | None = None
    chunk_type: ChunkType

    content: str = Field(min_length=1)
    heading_path: list[str] = Field(default_factory=list)

    page_start: int = Field(default=None, ge=1)
    page_end: int = Field(default=None, ge=1)
    chunk_index: int = Field(ge=0)
    token_count: int = Field(default=None, ge=0)

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("heading_path")
    @classmethod
    def clean_heading_path(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @model_validator(mode="after")
    def validate_chunk_contract(self) -> "Chunk":
        if self.page_start is not None and self.page_end is not None:
            if self.page_start > self.page_end:
                raise ValueError("page_start must be <= page_end")

        if self.chunk_type == "parent" and self.parent_chunk_id is not None:
            raise ValueError("parent chunk must not have parent_chunk_id")

        if self.chunk_type == "child" and not self.parent_chunk_id:
            raise ValueError("child chunk requires parent_chunk_id")

        return self