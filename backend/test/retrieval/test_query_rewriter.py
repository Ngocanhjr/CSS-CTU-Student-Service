from types import SimpleNamespace

import pytest

from app.retrieval.s0_query_rewriter import rewrite_query
from app.retrieval.models import RetrievalContext
from app.retrieval.s1_query_resolver import complete_or_clarify_query
from app.rag.service import RagService
from app.schemas.rag import AnswerRequest, ConversationContext


class FakeModel:
    def invoke(self, prompt: str) -> SimpleNamespace:
        assert "xếp hạng học lực" in prompt
        return SimpleNamespace(
            content=(
                '{"queries": ['
                '"xếp loại kết quả học tập", '
                '"đánh giá kết quả học tập"'
                ']}'
            )
        )


def test_rewrite_query_preserves_original_and_deduplicates(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUERY_REWRITE_ENABLED", "true")
    monkeypatch.setenv("QUERY_REWRITE_MAX_QUERIES", "3")

    assert rewrite_query(
        "xếp hạng học lực",
        model=FakeModel(),
    ) == [
        "xếp hạng học lực",
        "xếp loại kết quả học tập",
        "đánh giá kết quả học tập",
    ]


def test_rewrite_query_falls_back_to_original_on_invalid_json(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUERY_REWRITE_ENABLED", "true")

    assert rewrite_query(
        "xếp hạng học lực",
        model=SimpleNamespace(invoke=lambda _: SimpleNamespace(content="invalid")),
    ) == ["xếp hạng học lực"]


def test_answer_request_accepts_legacy_recent_topic() -> None:
    request = AnswerRequest.model_validate(
        {
            "question": "Còn gì không?",
            "recent_topic": "đóng học phí KTX học kỳ 3",
        }
    )

    assert request.recent_topic == "đóng học phí KTX học kỳ 3"
    assert request.conversation_context is None


def test_answer_request_accepts_structured_conversation_context() -> None:
    request = AnswerRequest.model_validate(
        {
            "question": "Còn gì không?",
            "conversation_context": {
                "recent_topic": "đóng học phí KTX học kỳ 3",
                "document_key": "ctu-ctsv-tbdk-hk32526",
                "version_key": "ctu-ctsv-tbdk-hk32526-a42b92f1401a",
                "used_chunk_keys": ["ctu-ctsv-tbdk-hk32526-a42b92f1401a::c::0006"],
            },
        }
    )

    assert request.conversation_context == ConversationContext(
        recent_topic="đóng học phí KTX học kỳ 3",
        document_key="ctu-ctsv-tbdk-hk32526",
        version_key="ctu-ctsv-tbdk-hk32526-a42b92f1401a",
        used_chunk_keys=["ctu-ctsv-tbdk-hk32526-a42b92f1401a::c::0006"],
    )


def test_follow_up_without_context_requests_clarification() -> None:
    decision = complete_or_clarify_query("Còn gì không?")

    assert decision.should_search is False
    assert decision.clarification_question is not None


def test_follow_up_reuses_topic_and_source_scope_from_context() -> None:
    decision = complete_or_clarify_query(
        "trả lời tiếp",
        context=RetrievalContext(
            recent_topic="đóng học phí KTX học kỳ 3 năm học 2025-2026",
            current_document_key="ctu-ctsv-tbdk-hk32526",
            current_version_key="ctu-ctsv-tbdk-hk32526-a42b92f1401a",
        ),
    )

    assert decision.should_search is True
    assert decision.query == "đóng học phí KTX học kỳ 3 năm học 2025-2026"
    assert decision.document_key == "ctu-ctsv-tbdk-hk32526"
    assert decision.version_key == "ctu-ctsv-tbdk-hk32526-a42b92f1401a"


class _NoAdditionalResultsRetriever:
    def __init__(self) -> None:
        self.kwargs = None

    async def search_resolved_query(self, session, **kwargs):
        del session
        self.kwargs = kwargs
        return []


@pytest.mark.asyncio
async def test_follow_up_without_new_chunks_returns_supplementary_info_message() -> None:
    retriever = _NoAdditionalResultsRetriever()
    service = RagService(retriever=retriever)

    should_search, message, answer, next_context = await service.answer(
        session=None,
        question="còn gì không",
        top_k=5,
        context=RetrievalContext(
            recent_topic="đóng học phí KTX học kỳ 3",
            current_document_key="ctu-ctsv-tbdk-hk32526",
            current_version_key="ctu-ctsv-tbdk-hk32526-a42b92f1401a",
            used_chunk_keys=("ctu-ctsv-tbdk-hk32526-a42b92f1401a::c::0006",),
        ),
    )

    assert should_search is False
    assert answer is None
    assert "chưa tìm thấy thông tin bổ sung" in message
    assert retriever.kwargs["document_key"] == "ctu-ctsv-tbdk-hk32526"
    assert retriever.kwargs["version_key"] == "ctu-ctsv-tbdk-hk32526-a42b92f1401a"
    assert retriever.kwargs["exclude_chunk_keys"] == {
        "ctu-ctsv-tbdk-hk32526-a42b92f1401a::c::0006"
    }
    assert next_context.used_chunk_keys == [
        "ctu-ctsv-tbdk-hk32526-a42b92f1401a::c::0006"
    ]
