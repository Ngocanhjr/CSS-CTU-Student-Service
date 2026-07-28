# Mục đích: điều phối toàn bộ pipeline retrieval.
# Đây nên là file chính mà API chat gọi.

### Trách nhiệm không thuộc `Retriever`
# - Greeting/smalltalk.
# - Clarification question.
# - Prompt construction.
# - LLM answer generation.

from __future__ import annotations

from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.s4_dense_retriever import (
    DEFAULT_TOP_K,
    retrieve_child_chunks,
)
from app.retrieval.s5_sparse_retriever import search_sparse_documents
from app.retrieval.s6_fusion import reciprocal_rank_fusion
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
        top_k: int = DEFAULT_TOP_K,
        audience: str = "sinh_vien",
        document_key: str | None = None,
        version_key: str | None = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            return []

        dense_docs = retrieve_child_chunks(
            query,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
        )

        sparse_docs = await search_sparse_documents(
            session,
            query=query,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )
        fused_docs = reciprocal_rank_fusion(
            dense_docs,
            sparse_docs,
            limit=top_k,
        )

        direct_hits = await hydrate_langchain_documents(
            session,
            fused_docs,
            expansion_reason="direct_hit",
        )

        reranked_hits = self.reranker.rerank(
            query,
            direct_hits,
        )

        expanded = await expand_structural_context(
            session,
            qdrant_client=self.qdrant_client,
            collection_name=self.collection_name,
            direct_hits=reranked_hits,
            query=query,
        )

        return expanded
