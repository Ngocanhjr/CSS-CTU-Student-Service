# Lấy các chunk đã chọn từ fusion và bổ sung dữ liệu hoàn chỉnh từ PostgreSQL.

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import urlparse

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import (
    Document,
    DocumentChunk,
    DocumentType,
    DocumentVersion,
)
from app.retrieval.models import ExpansionReason, RetrievalResult


def get_file_name(path_or_url: str | None) -> str | None:
    """Lấy tên file từ R2 object key hoặc URL."""

    if not path_or_url:
        return None

    parsed = urlparse(path_or_url)
    path = parsed.path if parsed.scheme else path_or_url
    file_name = PurePosixPath(path.replace("\\", "/")).name

    return file_name or None


def build_citation(
    *,
    source_file: str,
    page_start: int | None,
    page_end: int | None,
    heading_path: list[str] | None = None,
) -> str:
    """Tạo nội dung trích dẫn đi kèm chunk."""

    if page_start is not None and page_end is not None:
        if page_start == page_end:
            return f"{source_file}, trang {page_start}"

        return f"{source_file}, trang {page_start}-{page_end}"

    if heading_path:
        return f"{source_file}, mục {heading_path[-1]}"

    return source_file


async def hydrate_langchain_documents(
    session: AsyncSession,
    docs: list[LangChainDocument],
    *,
    expansion_reason: ExpansionReason = "direct_hit",
) -> list[RetrievalResult]:
    """Bổ sung dữ liệu PostgreSQL cho các kết quả sau fusion."""

    chunk_ids = [
        int(doc.metadata["postgres_chunk_id"])
        for doc in docs
        if doc.metadata.get("postgres_chunk_id") is not None
    ]

    if not chunk_ids:
        return []

    rows = (
        await session.execute(
            select(
                DocumentChunk,
                DocumentVersion,
                Document,
                DocumentType,
            )
            .join(
                DocumentVersion,
                DocumentVersion.id
                == DocumentChunk.document_version_id,
            )
            .join(
                Document,
                Document.id == DocumentVersion.document_id,
            )
            .outerjoin(
                DocumentType,
                DocumentType.id == Document.document_type_id,
            )
            .where(DocumentChunk.id.in_(set(chunk_ids)))
        )
    ).all()

    records_by_chunk_id = {
        chunk.id: (
            chunk,
            version,
            document,
            document_type,
        )
        for chunk, version, document, document_type in rows
    }

    # Lấy nội dung chunk cha.
    parent_ids = {
        chunk.parent_chunk_id
        for chunk, _, _, _ in records_by_chunk_id.values()
        if chunk.parent_chunk_id is not None
    }

    parent_by_id: dict[int, DocumentChunk] = {}

    if parent_ids:
        parent_rows = await session.execute(
            select(DocumentChunk).where(
                DocumentChunk.id.in_(parent_ids)
            )
        )

        parent_by_id = {
            parent.id: parent
            for parent in parent_rows.scalars()
        }

    results: list[RetrievalResult] = []

    # Duyệt theo thứ tự docs để giữ thứ hạng từ fusion.
    for doc in docs:
        metadata = dict(doc.metadata or {})

        db_chunk_id = metadata.get("postgres_chunk_id")
        if db_chunk_id is None:
            continue

        record = records_by_chunk_id.get(int(db_chunk_id))
        if record is None:
            continue

        chunk, version, document, document_type = record

        parent = parent_by_id.get(chunk.parent_chunk_id)

        parent_chunk_key = (
            metadata.get("parent_chunk_key")
            or (
                parent.chunk_key
                if parent is not None
                else None
            )
        )

        heading_path = (
            metadata.get("heading_path")
            or getattr(chunk, "heading_path", None)
            or []
        )

        item_path = (
            metadata.get("item_path")
            or getattr(chunk, "item_path", None)
            or []
        )

        page_start = metadata.get("page_start")
        if page_start is None:
            page_start = getattr(chunk, "page_start", None)

        page_end = metadata.get("page_end")
        if page_end is None:
            page_end = getattr(chunk, "page_end", None)

        # Ba nguồn được giữ riêng biệt.
        source_path = version.source_path or ""
        canonical_markdown_path = (
            version.canonical_markdown_path or ""
        )

        source_url = (
            getattr(version, "source_url", None)
            or getattr(document, "source_url", None)
            or metadata.get("source_url")
            or ""
        )

        # Tên file hiển thị ưu tiên PDF gốc, không ưu tiên file OCR.
        source_file = (
            get_file_name(source_path)
            or get_file_name(metadata.get("source_file"))
            or get_file_name(canonical_markdown_path)
            or version.title
            or document.title
        )

        logical_item_key = metadata.get("logical_item_key")

        logical_item_keys = (
            metadata.get("logical_item_keys")
            or (
                [logical_item_key]
                if logical_item_key
                else []
            )
        )

        results.append(
            RetrievalResult(
                postgres_chunk_id=int(db_chunk_id),
                postgres_parent_chunk_id=(
                    metadata.get("postgres_parent_chunk_id")
                    or chunk.parent_chunk_id
                ),
                document_key=document.document_key,
                version_key=version.version_key,
                chunk_key=(
                    metadata.get("chunk_key")
                    or chunk.chunk_key
                ),
                parent_chunk_key=parent_chunk_key,
                score=float(
                    metadata.get(
                        "_score",
                        metadata.get("score", 0.0),
                    )
                ),
                content=chunk.content,
                title=version.title or document.title,
                page_start=page_start,
                page_end=page_end,
                source_file=source_file,
                source_url=source_url,
                citation=build_citation(
                    source_file=source_file,
                    page_start=page_start,
                    page_end=page_end,
                    heading_path=heading_path,
                ),
                heading_path=heading_path,
                item_path=item_path,
                legal_unit_type=metadata.get(
                    "legal_unit_type",
                    "none",
                ),
                block_type=metadata.get("block_type"),
                logical_item_key=logical_item_key,
                logical_item_keys=logical_item_keys,
                parent_item_key=metadata.get(
                    "parent_item_key"
                ),
                logical_table_key=metadata.get(
                    "logical_table_key"
                ),
                logical_code_key=metadata.get(
                    "logical_code_key"
                ),
                split_index=int(
                    metadata.get("split_index", 0)
                ),
                split_count=int(
                    metadata.get("split_count", 1)
                ),
                chunk_index=metadata.get("chunk_index"),
                item_marker=metadata.get("item_marker"),
                item_level=metadata.get("item_level"),
                expansion_reason=expansion_reason,
                parent_content=(
                    parent.content
                    if parent is not None
                    else None
                ),
                issued_date=version.issued_date,
                issuing_authority=version.issuing_authority,
                document_type=(
                    document_type.name
                    if document_type is not None
                    else None
                ),
                source_path=source_path,
                canonical_markdown_path=(
                    canonical_markdown_path
                ),
            )
        )

    return results