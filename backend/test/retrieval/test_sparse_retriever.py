from app.retrieval.s5_sparse_retriever import build_sparse_tsquery


def test_sparse_tsquery_uses_or_for_meaningful_vietnamese_terms() -> None:
    statement = build_sparse_tsquery(
        "Khi chuyển khoản tiền KTX học kỳ 3, nội dung phải ghi theo cú pháp nào?"
    )

    assert statement is not None
    assert statement.clauses.clauses[1].value == (
        "chuyển | khoản | tiền | ktx | học | kỳ | nội | dung | ghi | cú | pháp"
    )


def test_sparse_tsquery_returns_none_when_only_stop_words() -> None:
    assert build_sparse_tsquery("khi nào và ở đâu") is None
