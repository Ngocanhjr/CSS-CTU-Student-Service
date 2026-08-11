# điều phối resolver -> Qdrant -> hydration -> LLM
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.rag_chain import generate_rag_answer
from app.retrieval.s1_query_resolver import complete_or_clarify_query
from app.retrieval.s0_query_rewriter import (
    get_query_rewrite_timeout_seconds,
    rewrite_query,
)
from app.retrieval.s10_retriever import Retriever
from app.retrieval.s8_reranker import get_reranker
from app.schemas.rag import RagAnswer
from app.vectorstore.qdrant_client import get_qdrant_client


logger = logging.getLogger(__name__)


class RagService:
    def __init__(self, *, retriever: Retriever | None = None) -> None:
        self.retriever = retriever or Retriever(
            qdrant_client=get_qdrant_client(),
            reranker=get_reranker(),
        )

    async def answer(
        self,
        session: AsyncSession,
        *,
        question: str,
        top_k: int,
    ) -> tuple[bool, str, RagAnswer | None]:
        decision = complete_or_clarify_query(question)
        if not decision.should_search:
            return (
                False,
                decision.response_message
                or decision.clarification_question
                or "",
                None,
            )

        try:
            queries = await asyncio.wait_for(
                asyncio.to_thread(
                    rewrite_query,
                    decision.query,
                ),
                timeout=get_query_rewrite_timeout_seconds() + 1,
            )
        except TimeoutError:
            logger.warning(
                "Query rewrite exceeded its timeout; using the original query."
            )
            queries = [decision.query]

        results = await self.retriever.search_resolved_query(
            session,
            query=decision.query,
            queries=queries,
            top_k=top_k,
            document_key=decision.document_key,
            version_key=decision.version_key,
        )
        # generate_rag_answer gọi LLM đồng bộ (chain.invoke).
        # Chạy trong thread để không chặn event loop của FastAPI.
        answer = await asyncio.to_thread(
            generate_rag_answer,
            question,
            results,
        )
        return True, "", answer
