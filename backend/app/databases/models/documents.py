from __future__ import annotations

import code
from datetime import date, datetime

from distro import name
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.databases.models.chunks import DocumentChunk
    from app.databases.models.ingestion import IngestionJob
    
class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
    
    documents: Mapped[list["Document"]] = relationship(back_populates="department")
    
class DocumentType(Base):
    __tablename__ = "document_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True) 
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
    
    documents: Mapped[list["Document"]] = relationship(back_populates="document_type")
    
class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("css.departments.id"))
    document_type_id: Mapped[int] = mapped_column(ForeignKey("css.document_types.id"))
    domain: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    audience: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
    
    department: Mapped["Department"] = relationship(back_populates="documents")
    document_type: Mapped["DocumentType"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    
class DocumentVersion(Base):
    __tablename__ = "document_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("css.documents.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500),default="", nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    
    version_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    version_label: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    version_role: Mapped[str] = mapped_column(String(50), default="base", nullable=False)
    
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), default= "md", nullable=False)
    canonical_markdown_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    
    
    language: Mapped[str] = mapped_column(String(20), default="vi", nullable=False)
    citation_type: Mapped[str] = mapped_column(String(50), default="page", nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    accessed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=False)

    document: Mapped["Document"] = relationship(back_populates="versions")
    status: Mapped["DocumentVersionStatus | None"] = relationship(back_populates="document_version", cascade="all, delete-orphan", uselist=False)
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("expiry_date IS NULL OR effective_date IS NULL OR effective_date <= expiry_date", name="chk_document_versions_date_range"),
    )
    
class DocumentVersionStatus(Base):
    __tablename__ = "document_version_status"
    
    document_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", 
                                                                ondelete="CASCADE"),
                                                     primary_key=True)
    validity_status: Mapped[str] = mapped_column(String(50), default="unchecked", nullable=False, index=True)
    collection_status: Mapped[str] = mapped_column(String(50), default="collected", nullable=False, index=True)
    ocr_status: Mapped[str] = mapped_column(String(50), default="not_started", nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(50), default="not_reviewed", nullable=False, index=True)
    rag_status: Mapped[str] = mapped_column(String(50), default="not_indexed", nullable=False, index=True)
    
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="status")
class DocumentVersionRelationship(Base):
    __tablename__ = "document_version_relationships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    target_version_id: Mapped[int] = mapped_column(ForeignKey("css.document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
   
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    source_version: Mapped["DocumentVersion"] = relationship(foreign_keys=[source_version_id])
    target_version: Mapped["DocumentVersion"] = relationship(foreign_keys=[target_version_id])

    __table_args__ = (
        UniqueConstraint("source_version_id", "target_version_id", "relation_type", name="uq_document_version_relationship"),
    )
    
