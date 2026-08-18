from app.retrieval.models import RetrievalContext
from app.retrieval.s1_query_resolver import complete_or_clarify_query


def test_new_explicit_question_is_not_limited_to_previous_document() -> None:
    context = RetrievalContext(
        current_document_key="quy-che-hoc-vu",
        current_version_key="2025",
        recent_topic="điều kiện cảnh báo học vụ",
    )

    decision = complete_or_clarify_query(
        "Thủ tục đăng ký bảo hiểm y tế như thế nào?",
        context=context,
    )

    assert decision.should_search is True
    assert decision.is_follow_up is False
    assert decision.document_key is None
    assert decision.version_key is None


def test_continuation_remains_limited_to_previous_document() -> None:
    context = RetrievalContext(
        current_document_key="quy-che-hoc-vu",
        current_version_key="2025",
        recent_topic="điều kiện cảnh báo học vụ",
    )

    decision = complete_or_clarify_query("tiếp", context=context)

    assert decision.should_search is True
    assert decision.is_follow_up is True
    assert decision.document_key == "quy-che-hoc-vu"
    assert decision.version_key == "2025"
