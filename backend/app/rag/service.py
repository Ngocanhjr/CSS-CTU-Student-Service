# điều phối resolver -> Qdrant -> hydration -> LLM
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.rag_chain import RagAnswer, generate_rag_answer
from app.retrieval.s1_query_resolver import complete_or_clarify_query
from app.retrieval.s10_retriever import Retriever
from app.retrieval.s8_reranker import get_reranker
from app.vectorstore.qdrant_client import get_qdrant_client


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

        results = await self.retriever.search_resolved_query(
            session,
            query=decision.query,
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
