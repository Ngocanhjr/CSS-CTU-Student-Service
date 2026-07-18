#Lấy file chunk đã chọn lọc từ fusion để bổ sung dữ liệu cho từng chunk hoàn chỉnh

from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import Document, DocumentChunk, DocumentVersion
from app.retrieval.models import ExpansionReason, RetrievalResult

#tạo citation - thông tin đi kèm chunk -> để LLM có thể nói rõ câu trả lời lấy từ đâu (Nguồn)
def build_citation(
    *,
    source_file: str,
    page_start: int | None,
    page_end: int | None,
    heading_path: list[str] | None = None,
) -> str:
    #nếu có đầy đủ số trang
    if page_start is not None and page_end is not None:
        if page_start == page_end:
            return f"{source_file}, trang {page_start}"
        return f"{source_file}, trang {page_start}-{page_end}"

    #nếu có heading
    if heading_path:
        return f"{source_file}, mục {heading_path[-1]}"

    return source_file


async def hydrate_langchain_documents(
    session: AsyncSession,
    docs: list[LangChainDocument],
    *,
    expansion_reason: ExpansionReason = "direct_hit",
) -> list[RetrievalResult]:
    
    #tìm chunk gốc trong postgreSQL
    chunk_ids = [
        int(doc.metadata["postgres_chunk_id"])
        for doc in docs
        if doc.metadata.get("postgres_chunk_id") is not None
    ]
    if not chunk_ids:
        return []

    #Hàm query PostgreSQL để lấy cùng lúc: DocumentChunk + DocumentVersion + Document => nd chuẩn của chunk 
    rows = (
        await session.execute(
            select(DocumentChunk, DocumentVersion, Document)
            .join(
                DocumentVersion,
                DocumentVersion.id == DocumentChunk.document_version_id,
            )
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(DocumentChunk.id.in_(set(chunk_ids)))
        )
    ).all()
    records_by_chunk_id = {chunk.id: (chunk, version, document) for chunk, version, document in rows}

    #nếu child_chunk có parent_chunk, truy vấn các parent_chunk để lấy content
    parent_ids = {
        chunk.parent_chunk_id
        for chunk, _, _ in records_by_chunk_id.values()
        if chunk.parent_chunk_id is not None
    }
    parent_by_id: dict[int, DocumentChunk] = {}
    if parent_ids:
        parent_rows = await session.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(parent_ids))
        )
        parent_by_id = {parent.id: parent for parent in parent_rows.scalars()}

    #Gộp metadata retrieval/Qdrant với canonical data từ PostgreSQL.
    #Duyệt theo thứ tự `docs` để giữ nguyên thứ hạng đã được fusion tạo ra.
    results: list[RetrievalResult] = []
    for doc in docs:
        metadata = dict(doc.metadata or {})
        db_chunk_id = metadata.get("postgres_chunk_id")
        if db_chunk_id is None:
            continue

        record = records_by_chunk_id.get(int(db_chunk_id))
        if record is None:
            continue

        chunk, version, document = record
        parent = parent_by_id.get(chunk.parent_chunk_id)
        parent_chunk_key = metadata.get("parent_chunk_key") or (
            parent.chunk_key if parent is not None else None
        )

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

        source_file = (
            version.canonical_markdown_path
            or version.source_path
            or metadata.get("source_file", "")
        )
        logical_item_key = metadata.get("logical_item_key")
        logical_item_keys = (
            metadata.get("logical_item_keys")
            or ([logical_item_key] if logical_item_key else [])
        )

        #Chuẩn hóa thành RetrievalResult, bao gồm content, citation,
        #metadata cấu trúc và parent_content cho các bước sau.
        results.append(
            RetrievalResult(
                postgres_chunk_id=int(db_chunk_id),
                postgres_parent_chunk_id=(
                    metadata.get("postgres_parent_chunk_id")
                    or chunk.parent_chunk_id
                ),
                document_key=document.document_key,
                version_key=version.version_key,
                chunk_key=metadata.get(
                    "chunk_key",
                    chunk.chunk_key,
                ),
                parent_chunk_key=parent_chunk_key,
                score=float(metadata.get("_score", 0.0)),
                content=chunk.content,
                title=version.title or document.title,
                page_start=page_start,
                page_end=page_end,
                source_file=source_file,
                source_url=version.source_url,
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
                parent_content=parent.content if parent is not None else None,
            )
        )

    return results
