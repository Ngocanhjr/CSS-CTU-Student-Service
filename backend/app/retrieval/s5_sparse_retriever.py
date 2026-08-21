# Mục đích: Sparse Retrieval bằng PostgreSQL FTS + BM25.
#
# Câu hỏi
# → S2 tách metadata
# → S3 tạo eligibility conditions
# → PostgreSQL FTS lọc candidate
# → BM25 xếp hạng candidate theo keyword relevance
# → LangChainDocument[]
# → RRF với Dense Retrieval

from __future__ import annotations

import re

from langchain_core.documents import Document as LangChainDocument
from rank_bm25 import BM25Okapi

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


# =========================================================
# Tokenization
# =========================================================

_FTS_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)

_FTS_STOP_WORDS = frozenset(
    {
        "ai", "bao", "các", "cho", "có", "của", "đã", "để", "đến",
        "điều", "được", "gì", "hay", "khi", "là", "lại", "mà", "mỗi",
        "một", "nào", "như", "những", "ở", "đâu", "phải", "sau", "sẽ",
        "số", "từ", "theo", "thì", "trong", "và", "về", "với", "vào",
    }
)


def tokenize_sparse_text(
    text: str,
    *,
    deduplicate: bool = False,
) -> list[str]:
    """
    Tokenize text dùng chung cho PostgreSQL FTS và BM25.

    Quan trọng:
    - Query có thể deduplicate.
    - Document KHÔNG deduplicate vì BM25 cần term frequency (TF).
    """

    tokens: list[str] = []
    seen: set[str] = set()

    for token in _FTS_TOKEN_PATTERN.findall(text.casefold()):
        if len(token) < 2:
            continue

        if token in _FTS_STOP_WORDS:
            continue

        if deduplicate:
            if token in seen:
                continue

            seen.add(token)

        tokens.append(token)

    return tokens


# =========================================================
# PostgreSQL FTS query
# =========================================================

def build_sparse_tsquery(query: str):
    """
    Tạo PostgreSQL OR tsquery.

    Ví dụ:
        "học phí sinh viên"

    →
        học | phí | sinh | viên
    """

    tokens = tokenize_sparse_text(
        query,
        deduplicate=True,
    )

    if not tokens:
        return None

    return func.to_tsquery(
        "simple",
        " | ".join(tokens),
    )


# =========================================================
# BM25 ranking
# =========================================================

def bm25_rerank(
    *,
    query: str,
    rows: list,
    top_k: int,
) -> list[LangChainDocument]:
    """
    Rerank các candidate do PostgreSQL FTS trả về bằng BM25.

    PostgreSQL FTS:
        tìm candidate

    BM25:
        tính final sparse score
        và sắp xếp candidate
    """

    if not rows:
        return []

    # Query không cần giữ từ lặp.
    query_tokens = tokenize_sparse_text(
        query,
        deduplicate=True,
    )

    if not query_tokens:
        return []

    # Corpus phải giữ term frequency.
    # Vì vậy KHÔNG deduplicate document tokens.
    tokenized_corpus = [
        tokenize_sparse_text(
            chunk.content,
            deduplicate=False,
        )
        for chunk, version, document, fts_score in rows
    ]

    # Build BM25 index trên candidate corpus.
    bm25 = BM25Okapi(
        tokenized_corpus,
        k1=1.5,
        b=0.75,
    )

    # BM25 score cho từng candidate.
    bm25_scores = bm25.get_scores(query_tokens)

    # Ghép row với BM25 score.
    scored_rows = [
        (
            chunk,
            version,
            document,
            float(fts_score),
            float(bm25_score),
        )
        for (
            chunk,
            version,
            document,
            fts_score,
        ), bm25_score in zip(
            rows,
            bm25_scores,
        )
    ]

    # Final Sparse ranking = BM25.
    scored_rows.sort(
        key=lambda item: item[4],
        reverse=True,
    )

    # Giữ giống logic cũ:
    # sparse trả nhiều candidate hơn top_k cho RRF.
    return_k = top_k * 3

    scored_rows = scored_rows[:return_k]

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

                # Score chính của Sparse Retrieval
                "_score": bm25_score,

                # Chỉ để debug / quan sát candidate FTS
                "_fts_candidate_score": fts_score,

                # Cho biết loại sparse rank
                "_sparse_ranker": "bm25",
            },
        )
        for (
            chunk,
            version,
            document,
            fts_score,
            bm25_score,
        ) in scored_rows
    ]


# =========================================================
# Sparse Retrieval
# =========================================================

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

    # =====================================================
    # S2 - Metadata filter
    # =====================================================

    metadata_filter = metadata_filter or extract_metadata_filter(
        query,
        document_key=document_key,
        version_key=version_key,
    )

    # =====================================================
    # Build FTS query
    # =====================================================

    ts_query = build_sparse_tsquery(query)

    if ts_query is None:
        return []

    # PostgreSQL tsvector.
    search_vector = func.to_tsvector(
        "simple",
        DocumentChunk.content,
    )

    # -----------------------------------------------------
    # FTS candidate score
    #
    # LƯU Ý:
    # ts_rank_cd KHÔNG còn là final Sparse score.
    #
    # Nó chỉ dùng để ưu tiên candidate trước khi đưa
    # sang BM25.
    # -----------------------------------------------------

    fts_candidate_rank = func.ts_rank_cd(
        search_vector,
        ts_query,
    ).label("fts_candidate_score")

    # =====================================================
    # S3 - Eligibility
    # =====================================================

    eligibility_conditions = (
        EligibilityPolicy.build_postgres_conditions(
            EligibilityContext(
                audience=audience,
                document_key=metadata_filter.document_key,
                version_key=metadata_filter.version_key,
            )
        )
    )

    # =====================================================
    # PostgreSQL FTS candidate retrieval
    # =====================================================

    # BM25 cần pool candidate lớn hơn final top_k.
    #
    # Ví dụ:
    # top_k = 20
    # → lấy khoảng 180 candidate FTS
    # → BM25 rerank
    # → trả tối đa 60 cho RRF
    fts_candidate_k = max(
        top_k * 9,
        100,
    )

    statement = (
        select(
            DocumentChunk,
            DocumentVersion,
            Document,
            fts_candidate_rank,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id
            == DocumentChunk.document_version_id,
        )
        .join(
            Document,
            Document.id
            == DocumentVersion.document_id,
        )
        .where(
            DocumentChunk.chunk_type == "child",
            DocumentChunk.index_status == "indexed",
            DocumentChunk.qdrant_point_id.is_not(None),

            *eligibility_conditions,

            # PostgreSQL FTS chỉ lấy document
            # có keyword match.
            search_vector.op("@@")(ts_query),
        )

        # Chỉ để chọn candidate tốt trước BM25.
        .order_by(
            desc(fts_candidate_rank)
        )

        .limit(
            fts_candidate_k
        )
    )

    # =====================================================
    # Execute PostgreSQL
    # =====================================================

    rows = (
        await session.execute(statement)
    ).all()

    # =====================================================
    # BM25 final ranking
    # =====================================================

    return bm25_rerank(
        query=query,
        rows=rows,
        top_k=top_k,
    )