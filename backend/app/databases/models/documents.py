from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    Date,
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

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.databases.models.chunks import DocumentChunk
    from app.databases.models.ingestion import IngestionJob
    from app.databases.models.assets import DocumentAsset
    
class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    recipients: Mapped[list["DocumentRecipient"]] = relationship(back_populates="department")

class DocumentType(Base):
    __tablename__ = "document_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True) 
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    documents: Mapped[list["Document"]] = relationship(back_populates="document_type")
    
class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    
    domain: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    audience: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    
    document_type_id: Mapped[int] = mapped_column(ForeignKey("css.document_types.id"))
    
    document_type: Mapped["DocumentType"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    
class DocumentVersion(Base):
    __tablename__ = "document_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("css.documents.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    
    version_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500),default="", nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
   
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    canonical_markdown_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), default= "md", nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="vi", nullable=False)
    accessed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

    ocr_status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(50), default="not_reviewed", nullable=False, index=True)
    rag_status: Mapped[str] = mapped_column(String(50), default="not_indexed", nullable=False, index=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    document: Mapped["Document"] = relationship(back_populates="versions") #versions: Mapped[list["DocumentVersion"]] ở phía trên
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    recipients: Mapped[list["DocumentRecipient"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    asset_links: Mapped[list["DocumentAsset"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    
class DocumentRecipient(Base):
    __tablename__ = "document_recipients"
    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("css.departments.id"), primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, primary_key=True)
    
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="recipients")
    department: Mapped["Department"] = relationship(back_populates="recipients")