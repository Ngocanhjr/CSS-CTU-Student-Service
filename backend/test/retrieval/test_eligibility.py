from app.retrieval.eligibility import EligibilityContext, EligibilityPolicy


def test_postgres_eligibility_uses_publish_status_and_json_audience() -> None:
    conditions = EligibilityPolicy.build_postgres_conditions(
        EligibilityContext(audience="sinh_vien")
    )

    rendered_conditions = " ".join(str(condition) for condition in conditions)
    assert "review_status" in rendered_conditions
    assert "rag_status" in rendered_conditions
    assert "audience" in rendered_conditions
    assert "is_latest" not in rendered_conditions


def test_qdrant_eligibility_does_not_hard_filter_is_latest() -> None:
    query_filter = EligibilityPolicy.build_qdrant_filter(
        EligibilityContext(audience="sinh_vien")
    )

    condition_keys = [condition.key for condition in query_filter.must]
    assert condition_keys == [
        "review_status",
        "rag_status",
        "chunk_type",
        "audience",
    ]
