# điều phối resolver -> Qdrant -> hydration -> LLM
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.rag_chain import RagAnswer, generate_rag_answer
from backend.app.retrieval.s4_dense_retriever import retrieve_child_chunks
from backend.app.retrieval.s7_hydration import hydrate_langchain_documents
from app.retrieval.s1_query_resolver import complete_or_clarify_query


class RagService:
    async def answer(
        self,
        session: AsyncSession,
        *,
        question: str,
        top_k: int,
    ) -> tuple[bool, str, RagAnswer | None]:
        decision = complete_or_clarify_query(question)
        if not decision.should_search:
            return False, decision.clarification_question or "", None

        dense_docs = retrieve_child_chunks(
            decision.query,
            top_k=top_k,
            document_key=decision.document_key,
            version_key=decision.version_key,
        )
        results = await hydrate_langchain_documents(session, dense_docs)
        return True, "", generate_rag_answer(question, results)
