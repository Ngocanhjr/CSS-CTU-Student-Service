# Mục đích: lấy canonical content từ PostgreSQL và chuyển thành ​RetrievalResult​.
# Skeleton trên gọi DB từng chunk. Production nên batch query bằng ​WHERE id IN (...)​ để tránh N+1 query.

from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import DocumentChunk
from app.retrieval.models import ExpansionReason, RetrievalResult


def build_citation(
    *,
    source_file: str,
    page_start: int | None,
    page_end: int | None,
    heading_path: list[str] | None = None,
) -> str:
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
    results: list[RetrievalResult] = []

    for doc in docs:
        metadata = dict(doc.metadata or {})
        db_chunk_id = metadata.get("postgres_chunk_id")

        if db_chunk_id is None:
            continue

        chunk = await session.get(
            DocumentChunk,
            int(db_chunk_id),
        )
        if chunk is None:
            continue

        parent_chunk_key = metadata.get("parent_chunk_key")
        if (
            parent_chunk_key is None
            and chunk.parent_chunk_id is not None
        ):
            parent = await session.get(
                DocumentChunk,
                chunk.parent_chunk_id,
            )
            if parent is not None:
                parent_chunk_key = parent.chunk_key

        heading_path = (
            metadata.get("heading_path")
            or getattr(chunk, "heading_path", None)
            or []
        )
        item_path = metadata.get("item_path") or []

        page_start = metadata.get("page_start")
        if page_start is None:
            page_start = getattr(chunk, "page_start", None)

        page_end = metadata.get("page_end")
        if page_end is None:
            page_end = getattr(chunk, "page_end", None)

        source_file = metadata.get("source_file", "")
        logical_item_key = metadata.get("logical_item_key")
        logical_item_keys = (
            metadata.get("logical_item_keys")
            or ([logical_item_key] if logical_item_key else [])
        )

        results.append(
            RetrievalResult(
                postgres_chunk_id=int(db_chunk_id),
                postgres_parent_chunk_id=(
                    metadata.get("postgres_parent_chunk_id")
                    or chunk.parent_chunk_id
                ),
                document_key=metadata.get("document_key", ""),
                version_key=metadata.get("version_key", ""),
                chunk_key=metadata.get(
                    "chunk_key",
                    chunk.chunk_key,
                ),
                parent_chunk_key=parent_chunk_key,
                score=float(metadata.get("_score", 0.0)),
                content=chunk.content,
                title=metadata.get("title", ""),
                page_start=page_start,
                page_end=page_end,
                source_file=source_file,
                source_url=metadata.get("source_url", ""),
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
                parent_item_key=metadata.get("parent_item_key"),
                logical_table_key=metadata.get(
                    "logical_table_key"
                ),
                logical_code_key=metadata.get(
                    "logical_code_key"
                ),
                split_index=int(metadata.get("split_index", 0)),
                split_count=int(metadata.get("split_count", 1)),
                chunk_index=metadata.get("chunk_index"),
                item_marker=metadata.get("item_marker"),
                item_level=metadata.get("item_level"),
                expansion_reason=expansion_reason,
            )
        )

    return results