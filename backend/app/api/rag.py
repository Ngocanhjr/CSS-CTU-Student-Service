from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.rag.service import RagService
from app.retrieval.models import RetrievalContext
from app.schemas.rag import AnswerRequest, AnswerResponse


router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
rag_service = RagService()


@router.post("/answer", response_model=AnswerResponse)
async def answer_question(
    request: AnswerRequest,
    session: AsyncSession = Depends(get_session),
) -> AnswerResponse:
    supplied_context = request.conversation_context
    context = RetrievalContext(
        current_document_key=(
            supplied_context.document_key if supplied_context else None
        ),
        current_version_key=(
            supplied_context.version_key if supplied_context else None
        ),
        recent_topic=(
            (supplied_context.recent_topic if supplied_context else None)
            or request.recent_topic
        ),
        used_chunk_keys=(
            tuple(supplied_context.used_chunk_keys)
            if supplied_context
            else ()
        ),
    )
    should_search, direct_answer, rag_answer, response_context = await rag_service.answer(
        session,
        question=request.question,
        top_k=request.top_k,
        context=context,
    )

    if not should_search:
        return AnswerResponse(
            answer=direct_answer,
            citations=[],
            should_search=False,
            recent_topic=response_context.recent_topic,
            conversation_context=response_context,
        )

    assert rag_answer is not None

    return AnswerResponse(
        answer=rag_answer.answer,
        citations=rag_answer.citations,
        should_search=True,
        recent_topic=response_context.recent_topic,
        conversation_context=response_context,
    )
