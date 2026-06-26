from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.databases.base import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("css.document_chunks.id", ondelete="CASCADE"))

    chunk_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    section_title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    index_status: Mapped[str] = mapped_column(String(50), default="not_indexed", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
    parent: Mapped["DocumentChunk | None"] = relationship(remote_side=[id])

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunk_index"),
        UniqueConstraint("document_version_id", "chunk_key", name="uq_document_chunk_key"), 
        CheckConstraint("chunk_type IN ('parent', 'child')", name="chk_document_chunks_type"),
       CheckConstraint("page_start <= page_end", name="chk_document_chunks_page_range"),
    )
