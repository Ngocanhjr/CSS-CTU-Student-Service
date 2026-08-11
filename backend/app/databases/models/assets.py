"""
Dành cho lưu trữ các link mà tài liệu cần dùng: ví dụ link youtube, link form
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.databases.base import Base

class Asset(Base):
    __tablename__ = "assets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document_links: Mapped[list["DocumentAsset"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
class DocumentAsset(Base):
    __tablename__ = "document_assets"
    
    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("css.assets.id", ondelete="CASCADE"), primary_key=True)
    
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, primary_key=True)  # reference, required, optional
    required_when: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
   
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="asset_links")
    asset: Mapped["Asset"] = relationship(back_populates="document_links")