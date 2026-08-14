# Mục đích: tìm kiếm từ khóa bằng PostgreSQL FTS.
# Câu hỏi
# → S2 tách metadata
# → S3 tạo eligibility conditions
# → PostgreSQL Full-Text Search
# → xếp hạng keyword -> đánh giá điểm khớp từ khóa 
# → LangChainDocument[] -> ds chunk từ PostgreSQL keyword search 

from __future__ import annotations

from langchain_core.documents import Document as LangChainDocument
import re

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
)
from app.retrieval.s2_metadata_filter import (
    QueryMetadataFilter,
    extract_metadata_filter,
)
from app.retrieval.s3_eligibility import (
    EligibilityContext,
    EligibilityPolicy,
)


# Vietnamese has no built-in PostgreSQL stemmer in the standard installation.
# Build an OR tsquery from meaningful query terms rather than asking FTS to
# match every word of a natural-language question.  The latter makes sparse
# retrieval return no rows when a chunk contains the answer but not fillers
# such as "khi", "nào", "được", or the full question wording.
_FTS_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_FTS_STOP_WORDS = frozenset(
    {
        "ai", "bao", "các", "cho", "có", "của", "đã", "để", "đến",
        "điều", "được", "gì", "hay", "khi", "là", "lại", "mà", "mỗi",
        "một", "nào", "như", "những", "ở", "đâu", "phải", "sau", "sẽ", "sinh",
        "số", "từ", "theo", "thì", "trong", "và", "về", "với", "vào",
    }
)


def build_sparse_tsquery(query: str):
    """Build a recall-oriented OR query suitable for Vietnamese FTS.

    ``websearch_to_tsquery`` treats a whitespace-separated natural-language
    question as a very restrictive AND query.  This helper retains meaningful
    tokens, deduplicates them and joins them with ``|`` so ranking can select
    the most lexically relevant candidates.  The existing ``ts_rank_cd``
    ordering remains responsible for ranking the candidates.
    """

    tokens: list[str] = []
    seen: set[str] = set()
    for token in _FTS_TOKEN_PATTERN.findall(query.casefold()):
        if len(token) < 2 or token in _FTS_STOP_WORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)

    if not tokens:
        return None

    # Tokens come exclusively from the regex above, so no tsquery operators
    # can be injected into the expression.
    return func.to_tsquery("simple", " | ".join(tokens))


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

    # Search by meaningful terms using OR semantics. This is more robust for
    # Vietnamese natural-language questions than websearch_to_tsquery's
    # restrictive all-term matching.
    ts_query = build_sparse_tsquery(query)
    if ts_query is None:
        return []
    
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

    # LƯU Ý: domain/document_type/department do s2 suy đoán từ chữ trong câu hỏi
    # (vd "ký túc xá" -> domain=sinh_vien). KHÔNG dùng chúng làm điều kiện WHERE
    # cứng vì đoán sai sẽ loại nhầm tài liệu đúng. Độ khớp chủ đề đã do FTS rank
    # + LexicalReranker (s8) xử lý. Chỉ giữ eligibility (s3) và document_key/
    # version_key tường minh.

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
