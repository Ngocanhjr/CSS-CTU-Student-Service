#ghép kết quả retrieval thành context, đưa question + context vào prompt và LLM để sinh câu trả lời; 
#đồng thời tạo danh sách citations trả về cho client.
#nơi thực hiện để tạo câu trả lời cuối cùng.
"""Grounded answer generation from hydrated retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain_core.output_parsers import StrOutputParser

from app.llm.generator import get_chat_model
from app.llm.prompts import RAG_ANSWER_PROMPT
from app.retrieval.models import RetrievalResult
from app.retrieval.s11_context_builder import build_retrieval_context


NO_CONTEXT_ANSWER = (
    "Tôi không tìm thấy thông tin phù hợp "
    "trong tài liệu đã được duyệt."
)


@dataclass(frozen=True)
class AnswerCitation:
    document_key: str
    version_key: str
    chunk_key: str

    title: str
    page_start: int | None
    page_end: int | None
    citation: str

    # Metadata phục vụ màn Chi tiết tài liệu.
    source_file: str
    issued_date: date | None
    issuing_authority: str | None
    document_type: str | None

    # Nguồn để client mở tài liệu.
    source_url: str | None = None
    source_path: str | None = None
    canonical_markdown_path: str | None = None


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[AnswerCitation]


def build_answer_citations(
    results: list[RetrievalResult],
) -> list[AnswerCitation]:
    """Chuyển RetrievalResult thành danh sách citation không trùng lặp."""

    citations: list[AnswerCitation] = []

    seen_sources: set[
        tuple[str, str, int | None, int | None]
    ] = set()

    for result in results:
        source_key = (
            result.document_key,
            result.version_key,
            result.page_start,
            result.page_end,
        )

        if source_key in seen_sources:
            continue

        citations.append(
            AnswerCitation(
                document_key=result.document_key,
                version_key=result.version_key,
                chunk_key=result.chunk_key,
                title=result.title,
                page_start=result.page_start,
                page_end=result.page_end,
                citation=result.citation,
                source_file=result.source_file,
                issued_date=result.issued_date,
                issuing_authority=result.issuing_authority,
                document_type=result.document_type,
                source_url=result.source_url or None,
                source_path=result.source_path or None,
                canonical_markdown_path=(
                    result.canonical_markdown_path or None
                ),
            )
        )

        seen_sources.add(source_key)

    return citations


def generate_rag_answer(
    question: str,
    results: list[RetrievalResult],
    *,
    model: Any | None = None,
    max_context_characters: int = 12_000,
) -> RagAnswer:
    """Sinh câu trả lời từ retrieval context và trả citation."""

    context = build_retrieval_context(
        results,
        max_characters=max_context_characters,
    )

    if not context:
        return RagAnswer(
            answer=NO_CONTEXT_ANSWER,
            citations=[],
        )

    chat_model = (
        model
        if model is not None
        else get_chat_model()
    )

    chain = (
        RAG_ANSWER_PROMPT
        | chat_model
        | StrOutputParser()
    )

    answer = str(
        chain.invoke(
            {
                "question": question.strip(),
                "context": context,
            }
        )
    ).strip()

    return RagAnswer(
        answer=answer,
        citations=build_answer_citations(results),
    )