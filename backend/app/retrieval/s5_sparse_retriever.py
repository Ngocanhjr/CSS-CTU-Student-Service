# Mục đích: tìm kiếm từ khóa bằng PostgreSQL FTS.
# Câu hỏi
# → S2 tách metadata
# → S3 tạo eligibility conditions
# → PostgreSQL Full-Text Search
# → xếp hạng keyword -> đánh giá điểm khớp từ khóa 
# → LangChainDocument[] -> ds chunk từ PostgreSQL keyword search 

from __future__ import annotations

from importlib import import_module

from langchain_core.documents import Document as LangChainDocument
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import (
    Department,
    Document,
    DocumentChunk,
    DocumentRecipient,
    DocumentType,
    DocumentVersion,
)
from backend.app.retrieval.s3_eligibility import (
    EligibilityContext,
    EligibilityPolicy,
)

_metadata_filter_module = import_module("app.retrieval.02_metadata_filter")
QueryMetadataFilter = _metadata_filter_module.QueryMetadataFilter
extract_metadata_filter = _metadata_filter_module.extract_metadata_filter


async def search_sparse_documents(
    session: AsyncSession,
    *,
    query: str,
    top_k: int,
    audience: str,
    document_key: str | None = None,
    version_key: str | None = None,
    metadata_filter: QueryMetadataFilter | None = None,
) -> list[LangChainDocument]:
    if not query.strip():
        return []

    metadata_filter = metadata_filter or extract_metadata_filter(
        query,
        document_key=document_key,
        version_key=version_key,
    )

    #Chuyển câu hỏi thành truy vấn full text
    ts_query = func.websearch_to_tsquery("simple", query)
    
    #lập chỉ mục từ nội dung chunk
    search_vector = func.to_tsvector(
        "simple",
        DocumentChunk.content,
    )
    
    #tính độ khớp từ khóa
    rank = func.ts_rank_cd(
        search_vector,
        ts_query,
    ).label("score")

    #Gọi s3 lấy chunk hợp lệ theo điều kiện
    eligibility_conditions = (
        EligibilityPolicy.build_postgres_conditions(
            EligibilityContext(
                audience=audience,
                document_key=metadata_filter.document_key,
                version_key=metadata_filter.version_key,
            )
        )
    )

    #thêm metadata từ s2 
    metadata_conditions = []
    
    if metadata_filter.department:
        metadata_conditions.append(
            DocumentVersion.recipients.any(
                DocumentRecipient.department.has(
                    Department.code == metadata_filter.department
                )
            )
        )
    if metadata_filter.document_type:
        metadata_conditions.append(
            Document.document_type.has(
                DocumentType.code == metadata_filter.document_type
            )
        )
    if metadata_filter.domain:
        metadata_conditions.append(Document.domain == metadata_filter.domain)

    #Câu lệnh sql
    statement = (
        select(
            DocumentChunk,
            DocumentVersion,
            Document,
            rank,
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
        #xét điều kiện là child chunk, và indexed rồi, có liên kết với Qdrant, 
        .where(
            DocumentChunk.chunk_type == "child",
            DocumentChunk.index_status == "indexed",
            DocumentChunk.qdrant_point_id.is_not(None),
            *eligibility_conditions,
            *metadata_conditions,
            search_vector.op("@@")(ts_query),
        )
        #Sắp xếp kết quả theo điểm khớp từ khóa giảm dần: chunk khớp nhất đứng đầu.
        .order_by(desc(rank))
        .limit(top_k * 3)
    )
    #thực thi sql 
    rows = (await session.execute(statement)).all()

    return [
        LangChainDocument(
            page_content=chunk.content,
            metadata={
                "postgres_chunk_id": chunk.id,
                "qdrant_point_id": chunk.qdrant_point_id,
                "chunk_key": chunk.chunk_key,
                "parent_chunk_id": chunk.parent_chunk_id,
                "document_key": document.document_key,
                "version_key": version.version_key,
                "_score": float(score),
            },
        )
        for chunk, version, document, score in rows
    ]
