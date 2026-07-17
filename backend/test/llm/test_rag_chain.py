from app.llm.rag_chain import NO_CONTEXT_ANSWER, generate_rag_answer


def test_generate_rag_answer_skips_llm_without_context() -> None:
    result = generate_rag_answer("Điều kiện là gì?", [])

    assert result.answer == NO_CONTEXT_ANSWER
    assert result.citations == []
