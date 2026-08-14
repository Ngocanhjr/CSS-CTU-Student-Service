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
    context = RetrievalContext(
        recent_topic=request.recent_topic,
    )
    should_search, direct_answer, rag_answer, recent_topic = (
        await rag_service.answer(
            session,
            question=request.question,
            top_k=request.top_k,
            context=context,
        )
    )

    if not should_search:
        return AnswerResponse(
            answer=direct_answer,
            citations=[],
            should_search=False,
            recent_topic=recent_topic,
        )

    assert rag_answer is not None

    return AnswerResponse(
        answer=rag_answer.answer,
        citations=rag_answer.citations,
        should_search=True,
        recent_topic=recent_topic,
    )
