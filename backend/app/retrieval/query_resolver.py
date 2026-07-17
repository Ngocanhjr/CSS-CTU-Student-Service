# Xử lý câu hỏi trước khi gửi đến retrieval engine.

from __future__ import annotations

from app.retrieval.models import QueryDecision, RetrievalContext


GREETINGS = {
    "hi",
    "hello",
    "chào",
    "xin chào",
    "alo",
}

UNDERSPECIFIED_QUERIES = {
    "điều kiện là gì",
    "hồ sơ gồm gì",
    "nộp ở đâu",
    "cần gì",
    "cần giấy gì",
}


def normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def is_greeting_or_smalltalk(query: str) -> bool:
    return normalize_query(query).lower() in GREETINGS


def complete_or_clarify_query(
    query: str,
    *,
    context: RetrievalContext | None = None,
) -> QueryDecision:
    normalized = normalize_query(query)

    if not normalized:
        return QueryDecision(
            should_search=False,
            query="",
            clarification_question="Vui lòng nhập câu hỏi.",
        )

    if is_greeting_or_smalltalk(normalized):
        return QueryDecision(
            should_search=False,
            query=normalized,
            clarification_question=(
                "Chào bạn, mình là trợ lý hỗ trợ tra cứu thông tin "
                "sinh viên CTU. Bạn muốn hỏi về nội dung nào?"
            ),
        )

    context = context or RetrievalContext()
    is_ambiguous = normalized.lower() in UNDERSPECIFIED_QUERIES

    has_context = bool(
        context.current_document_key
        or context.current_version_key
        or context.recent_topic
    )

    if is_ambiguous and not has_context:
        return QueryDecision(
            should_search=False,
            query=normalized,
            clarification_question=(
                "Bạn muốn hỏi điều kiện hoặc hồ sơ của thủ tục nào?"
            ),
        )

    resolved_query = normalized
    if is_ambiguous and context.recent_topic:
        resolved_query = f"{normalized} cho {context.recent_topic}"

    return QueryDecision(
        should_search=True,
        query=resolved_query,
        document_key=context.current_document_key,
        version_key=context.current_version_key,
    )