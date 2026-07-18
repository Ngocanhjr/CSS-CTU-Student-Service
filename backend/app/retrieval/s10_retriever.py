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

from app.embedding.embedder import TextEmbedder
from backend.app.retrieval.s4_dense_retriever import (
    DEFAULT_TOP_K,
    build_dense_retriever,
)
from backend.app.retrieval.s9_expansion import expand_structural_context
# from app.retrieval.finalizer import finalize_retrieval_results
from backend.app.retrieval.s6_fusion import reciprocal_rank_fusion
from backend.app.retrieval.s7_hydration import hydrate_langchain_documents
from app.retrieval.models import RetrievalResult
# from app.retrieval.payload import (
#     attach_point_id_from_document,
#     attach_qdrant_payloads,
# )
from backend.app.retrieval.s8_reranker import Reranker
from backend.app.retrieval.s5_sparse_retriever import (
    search_sparse_documents,
)
from app.vectorstore.repository import DEFAULT_COLLECTION


class Retriever:
    def __init__(
        self,
        *,
        embedder: TextEmbedder,
        qdrant_client: QdrantClient,
        reranker: Reranker,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.embedder = embedder
        self.qdrant_client = qdrant_client
        self.reranker = reranker
        self.collection_name = collection_name

    async def search_resolved_query(
        self,
        session: AsyncSession,
        *,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        audience: str = "student",
        document_key: str | None = None,
        version_key: str | None = None,
        context_budget: int = 6000,
    ) -> list[RetrievalResult]:
        if not query.strip():
            return []

        dense_retriever = build_dense_retriever(
            qdrant_client=self.qdrant_client,
            embedder=self.embedder,
            collection_name=self.collection_name,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )

        dense_docs = dense_retriever.invoke(query)
        dense_docs = attach_point_id_from_document(dense_docs)
        dense_docs = attach_qdrant_payloads(
            self.qdrant_client,
            collection_name=self.collection_name,
            docs=dense_docs,
        )

        sparse_docs = await search_sparse_documents(
            session,
            query=query,
            top_k=top_k,
            audience=audience,
            document_key=document_key,
            version_key=version_key,
        )
        sparse_docs = attach_qdrant_payloads(
            self.qdrant_client,
            collection_name=self.collection_name,
            docs=sparse_docs,
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

        return finalize_retrieval_results(
            expanded,
            context_budget=context_budget,
        )