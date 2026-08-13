# Mục đích: điều phối toàn bộ pipeline retrieval.
# Đây nên là file chính mà API chat gọi.

### Trách nhiệm không thuộc `Retriever`
# - Greeting/smalltalk.
# - Clarification question.
# - Prompt construction.
# - LLM answer generation.

from __future__ import annotations

import asyncio
import logging

from langchain_core.documents import Document as LangChainDocument
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings_loader import get_rag_settings
from app.retrieval.s4_dense_retriever import (
    DEFAULT_TOP_K,
    retrieve_child_chunks,
)
from app.retrieval.s5_sparse_retriever import search_sparse_documents
from app.retrieval.s6_fusion import (
    multi_reciprocal_rank_fusion,
    reciprocal_rank_fusion,
)
from app.retrieval.s7_hydration import hydrate_langchain_documents
from app.retrieval.s8_reranker import Reranker
from app.retrieval.s9_expansion import expand_structural_context
from app.retrieval.models import RetrievalResult
from app.vectorstore.repository import COLLECTION_NAME

logger = logging.getLogger(__name__)


def _summarize_document(
    doc: LangChainDocument,
    *,
    rank: int,
) -> dict:
    metadata = doc.metadata or {}
    return {
        "rank": rank,
        "score": metadata.get("_score"),
        "document_key": metadata.get("document_key"),
        "version_key": metadata.get("version_key"),
        "chunk_key": metadata.get("chunk_key"),
        "postgres_chunk_id": metadata.get("postgres_chunk_id"),
    }


def _summarize_hit(
    hit: RetrievalResult,
    *,
    rank: int,
) -> dict:
    return {
        "rank": rank,
        "score": round(hit.score, 6),
        "document_key": hit.document_key,
        "version_key": hit.version_key,
        "chunk_key": hit.chunk_key,
        "reason": hit.expansion_reason,
        "title": hit.title,
        "page_start": hit.page_start,
        "page_end": hit.page_end,
    }


def _log_documents(
    label: str,
    docs: list[LangChainDocument],
    *,
    top_n: int = 5,
    extra: dict | None = None,
) -> None:
    if not logger.isEnabledFor(logging.INFO):
        return

    logger.info(
        "retrieval.%s count=%s extra=%s top=%s",
        label,
        len(docs),
        extra or {},
        [
            _summarize_document(doc, rank=rank)
            for rank, doc in enumerate(docs[:top_n], start=1)
        ],
    )


def _log_hits(
    label: str,
    hits: list[RetrievalResult],
    *,
    top_n: int = 5,
    extra: dict | None = None,
) -> None:
    if not logger.isEnabledFor(logging.INFO):
        return

    logger.info(
        "retrieval.%s count=%s extra=%s top=%s",
        label,
        len(hits),
        extra or {},
        [
            _summarize_hit(hit, rank=rank)
            for rank, hit in enumerate(hits[:top_n], start=1)
        ],
    )


class Retriever:
    def __init__(
        self,
        *,
        qdrant_client: QdrantClient,
        reranker: Reranker,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self.qdrant_client = qdrant_client
        self.reranker = reranker
        self.collection_name = collection_name

    async def search_resolved_query(
        self,
        session: AsyncSession,
        *,
        query: str,
        queries: list[str] | None = None,
        top_k: int = DEFAULT_TOP_K,
        audience: str = "sinh_vien",
        document_key: str | None = None,
        version_key: str | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            return []

        candidate_k = max(
            top_k,
            get_rag_settings().retrieval.candidate_k,
        )

        search_queries = [query]
        seen_queries = {query.casefold().strip()}
        for candidate in queries or []:
            normalized = " ".join(candidate.split()).strip()
            key = normalized.casefold()
            if normalized and key not in seen_queries:
                search_queries.append(normalized)
                seen_queries.add(key)

        logger.info(
            "retrieval.start query=%r variants=%s top_k=%s candidate_k=%s",
            query,
            search_queries,
            top_k,
            candidate_k,
        )

        fused_per_query = []
        for search_query in search_queries:
            # dense đưa vào asyncio.to.thread để dense & sparse chạy song song, tránh blocking event loop.
            dense_task = asyncio.to_thread(
                retrieve_child_chunks,
                search_query,
                top_k=candidate_k,
                audience=audience,
                document_key=document_key,
                version_key=version_key,
                qdrant_client=self.qdrant_client,
                collection_name=self.collection_name,
            )
            sparse_task = search_sparse_documents(
                session,
                query=search_query,
                top_k=candidate_k,
                audience=audience,
                document_key=document_key,
                version_key=version_key,
            )

            dense_docs, sparse_docs = await asyncio.gather(
                dense_task,
                sparse_task,
            )

            log_extra = {"query": search_query}
            _log_documents("dense", dense_docs, extra=log_extra)
            _log_documents("sparse", sparse_docs, extra=log_extra)

            fused_docs_for_query = reciprocal_rank_fusion(
                dense_docs,
                sparse_docs,
                limit=candidate_k,
            )
            _log_documents(
                "fused_query",
                fused_docs_for_query,
                extra=log_extra,
            )

            fused_per_query.append(fused_docs_for_query)

        fused_docs = multi_reciprocal_rank_fusion(
            fused_per_query,
            limit=candidate_k,
        )
        _log_documents("fused_multi_query", fused_docs)

        direct_hits = await hydrate_langchain_documents(
            session,
            fused_docs,
            expansion_reason="direct_hit",
        )
        _log_hits("hydrated_direct", direct_hits)

        # Reranker gọi API bên ngoài bằng httpx đồng bộ.
        reranked_hits = await asyncio.to_thread(
            self.reranker.rerank,
            query,
            direct_hits,
        )
        _log_hits("reranked", reranked_hits)

        final_hits = reranked_hits[:top_k]
        _log_hits("final_direct", final_hits)

        expanded = await expand_structural_context(
            session,
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
            direct_hits=final_hits,
            query=query,
        )
        _log_hits("expanded", expanded, top_n=10)

        return expanded
