import pytest
from pydantic import ValidationError

from app.schemas.chunks import Chunk


def test_parent_chunk_accepts_valid_data():
    chunk = Chunk(
        document_key="doc-001",
        version_key="doc-001-v1",
        chunk_key="p-001",
        chunk_type="parent",
        content="Noi dung parent",
        chunk_index=0,
    )

    assert chunk.chunk_key == "p-001"
    assert chunk.parent_chunk_key is None


def test_child_chunk_requires_parent_chunk_key():
    with pytest.raises(ValidationError):
        Chunk(
            document_key="doc-001",
            version_key="doc-001-v1",
            chunk_key="c-001",
            chunk_type="child",
            content="Noi dung child",
            chunk_index=1,
        )


def test_child_chunk_accepts_parent_chunk_key():
    chunk = Chunk(
        document_key="doc-001",
        version_key="doc-001-v1",
        chunk_key="c-001",
        parent_chunk_key="p-001",
        chunk_type="child",
        content="Noi dung child",
        chunk_index=1,
    )

    assert chunk.parent_chunk_key == "p-001"


def test_parent_chunk_rejects_parent_chunk_key():
    with pytest.raises(ValidationError):
        Chunk(
            document_key="doc-001",
            version_key="doc-001-v1",
            chunk_key="p-001",
            parent_chunk_key="root",
            chunk_type="parent",
            content="Noi dung parent",
            chunk_index=0,
        )


def test_chunk_rejects_invalid_page_range():
    with pytest.raises(ValidationError):
        Chunk(
            document_key="doc-001",
            version_key="doc-001-v1",
            chunk_key="p-001",
            chunk_type="parent",
            content="Noi dung parent",
            chunk_index=0,
            page_start=5,
            page_end=2,
        )


def test_chunk_cleans_heading_path():
    chunk = Chunk(
        document_key="doc-001",
        version_key="doc-001-v1",
        chunk_key="p-001",
        chunk_type="parent",
        content="Noi dung parent",
        chunk_index=0,
        heading_path=["  Chuong 1  ", "", " Dieu 2 "],
    )

    assert chunk.heading_path == ["Chuong 1", "Dieu 2"]
