from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.schemas.rag import AnswerRequest, AnswerResponse, CitationResponse
from app.rag.service import RagService


router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
rag_service = RagService()


@router.post("/answer", response_model=AnswerResponse)
async def answer_question(
    request: AnswerRequest,
    session: AsyncSession = Depends(get_session),
) -> AnswerResponse:
    should_search, direct_answer, rag_answer = await rag_service.answer(
        session,
        question=request.question,
        top_k=request.top_k,
    )
    if not should_search:
        return AnswerResponse(
            answer=direct_answer,
            citations=[],
            should_search=False,
        )

    assert rag_answer is not None
    return AnswerResponse(
        answer=rag_answer.answer,
        citations=[
            CitationResponse(
                document_key=citation.document_key,
                version_key=citation.version_key,
                chunk_key=citation.chunk_key,
                title=citation.title,
                page_start=citation.page_start,
                page_end=citation.page_end,
                citation=citation.citation,
                source_file=citation.source_file,
                issued_date=citation.issued_date,
                issuing_authority=citation.issuing_authority,
                document_type=citation.document_type,
            )
            for citation in rag_answer.citations
        ],
        should_search=True,
    )
