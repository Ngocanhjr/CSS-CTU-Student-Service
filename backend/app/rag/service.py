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
from app.retrieval.models import RetrievalContext, RetrievalResult
from app.schemas.rag import ConversationContext, RagAnswer
from app.vectorstore.qdrant_client import get_qdrant_client


logger = logging.getLogger(__name__)


def _next_conversation_context(
    *,
    input_context: RetrievalContext,
    topic: str,
    answer: RagAnswer | None,
    results: list[RetrievalResult] | None = None,
) -> ConversationContext:
    """Return only stable source identifiers for the next client request."""

    citations = answer.citations if answer is not None else []
    first_citation = citations[0] if citations else None
    used_chunk_keys = list(
        dict.fromkeys(
            [*input_context.used_chunk_keys]
            + [result.chunk_key for result in results or []]
            + [citation.chunk_key for citation in citations]
        )
    )[-100:]

    return ConversationContext(
        recent_topic=input_context.recent_topic or topic,
        document_key=(
            input_context.current_document_key
            or (first_citation.document_key if first_citation else None)
        ),
        version_key=(
            input_context.current_version_key
            or (first_citation.version_key if first_citation else None)
        ),
        used_chunk_keys=used_chunk_keys,
    )


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
        context: RetrievalContext | None = None,
    ) -> tuple[bool, str, RagAnswer | None, ConversationContext]:
        context = context or RetrievalContext()
        decision = complete_or_clarify_query(question, context=context)
        if not decision.should_search:
            return (
                False,
                decision.response_message
                or decision.clarification_question
                or "",
                None,
                _next_conversation_context(
                    input_context=context,
                    topic=decision.query,
                    answer=None,
                ),
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
            exclude_chunk_keys=(
                set(context.used_chunk_keys)
                if decision.is_follow_up
                else None
            ),
        )
        if decision.is_follow_up and not results:
            return (
                False,
                (
                    "Tôi chưa tìm thấy thông tin bổ sung liên quan trực tiếp "
                    "đến nội dung bạn vừa hỏi trong tài liệu đã tra cứu."
                ),
                None,
                _next_conversation_context(
                    input_context=context,
                    topic=decision.query,
                    answer=None,
                    results=[],
                ),
            )
        # generate_rag_answer gọi LLM đồng bộ (chain.invoke).
        # Chạy trong thread để không chặn event loop của FastAPI.
        answer = await asyncio.to_thread(
            generate_rag_answer,
            question,
            results,
        )
        return (
            True,
            "",
            answer,
            _next_conversation_context(
                input_context=context,
                topic=decision.query,
                answer=answer,
                results=results,
            ),
        )
