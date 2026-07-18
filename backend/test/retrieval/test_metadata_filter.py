from importlib import import_module


extract_metadata_filter = import_module(
    "app.retrieval.02_metadata_filter"
).extract_metadata_filter


def test_extracts_explicit_department_domain_and_document_type() -> None:
    metadata_filter = extract_metadata_filter(
        "Cho tôi biểu mẫu học bổng của PCTSV"
    )

    assert metadata_filter.department == "PCTSV"
    assert metadata_filter.document_type == "bieu_mau"
    assert metadata_filter.domain == "hoc_bong"


def test_does_not_infer_metadata_without_an_explicit_alias() -> None:
    metadata_filter = extract_metadata_filter("Tôi cần biết điều kiện đăng ký")

    assert metadata_filter.department is None
    assert metadata_filter.document_type is None
    assert metadata_filter.domain is None


def test_keeps_retrieval_context_filters() -> None:
    metadata_filter = extract_metadata_filter(
        "Thông báo KTX",
        document_key="noi-quy-ktx",
        version_key="noi-quy-ktx-v2",
    )

    assert metadata_filter.document_type == "thong_bao"
    assert metadata_filter.domain == "sinh_vien"
    assert metadata_filter.document_key == "noi-quy-ktx"
    assert metadata_filter.version_key == "noi-quy-ktx-v2"
