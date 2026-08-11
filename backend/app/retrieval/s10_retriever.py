# Mục đích: điều phối toàn bộ pipeline retrieval.
# Đây nên là file chính mà API chat gọi.

### Trách nhiệm không thuộc `Retriever`
# - Greeting/smalltalk.
# - Clarification question.
# - Prompt construction.
# - LLM answer generation.

from __future__ import annotations

import asyncio

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

        fused_per_query = []
        for search_query in search_queries:
            dense_docs = await asyncio.to_thread(
                retrieve_child_chunks,
                search_query,
                top_k=candidate_k,
                audience=audience,
                document_key=document_key,
                version_key=version_key,
                qdrant_client=self.qdrant_client,
                collection_name=self.collection_name,
            )

            sparse_docs = await search_sparse_documents(
                session,
                query=search_query,
                top_k=candidate_k,
                audience=audience,
                document_key=document_key,
                version_key=version_key,
            )
            fused_per_query.append(
                reciprocal_rank_fusion(
                    dense_docs,
                    sparse_docs,
                    limit=candidate_k,
                )
            )

        fused_docs = multi_reciprocal_rank_fusion(
            fused_per_query,
            limit=candidate_k,
        )

        direct_hits = await hydrate_langchain_documents(
            session,
            fused_docs,
            expansion_reason="direct_hit",
        )

        # Reranker gọi API bên ngoài bằng httpx đồng bộ.
        reranked_hits = await asyncio.to_thread(
            self.reranker.rerank,
            query,
            direct_hits,
        )

        final_hits = reranked_hits[:top_k]

        expanded = await expand_structural_context(
            session,
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
            direct_hits=final_hits,
            query=query,
        )

        return expanded
