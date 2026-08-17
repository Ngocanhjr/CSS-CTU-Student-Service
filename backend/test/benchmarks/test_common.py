from test.benchmarks.common import citation_precision, load_benchmark, no_answer_correct, summary_chart, write_csv
from test.benchmarks.ct239h_retrieval_benchmark_30 import normalized


def test_custom_metrics_and_chart(tmp_path):
    assert citation_precision([{"document_key": "a"}, {"document_key": "x"}], ["a"], answerable=True) == 0.5
    assert citation_precision([], ["a"], answerable=False) == 1.0
    assert no_answer_correct({"answer_status": "insufficient_evidence", "should_search": True, "citations": [{"document_key": "suggested-doc"}]})
    assert not no_answer_correct({"answer_status": "answered", "should_search": True, "citations": [{"document_key": "doc-a"}]})
    assert not no_answer_correct({})
    output = tmp_path / "summary.png"
    summary_chart(output, "Test", {"precision": 0.5, "mean_latency_seconds": 1.2}, seconds={"mean_latency_seconds"})
    assert output.is_file() and output.stat().st_size > 0


def test_normalized_span_match_is_whitespace_and_case_insensitive():
    assert normalized("  Đóng   PHÍ\nKTX ") == normalized("đóng phí ktx")


def test_load_benchmark_csv(tmp_path):
    source = tmp_path / "cases.csv"
    source.write_text('id,question,page_hint,gold_answer_spans,answerable\nR01,Q,"[1, 1]","[""Evidence đầy đủ""]",true\n', encoding="utf-8")
    case = load_benchmark(source)["cases"][0]
    assert case["page_hint"] == [1, 1]
    assert case["gold_answer_spans"] == ["Evidence đầy đủ"]
    assert case["answerable"] is True


def test_load_retrieval_csv_with_page_columns_and_single_span(tmp_path):
    source = tmp_path / "retrieval.csv"
    source.write_text("id,question,page_hint_start,page_hint_end,gold_answer_spans\nR01,Q,1,2,Evidence đầy đủ\n", encoding="utf-8")
    case = load_benchmark(source)["cases"][0]
    assert case["page_hint"] == [1, 2]
    assert case["gold_answer_spans"] == ["Evidence đầy đủ"]


def test_load_retrieval_csv_splits_spans_with_double_pipe(tmp_path):
    source = tmp_path / "retrieval.csv"
    source.write_text("id,gold_answer_spans\nR01,span một || span hai\n", encoding="utf-8")
    assert load_benchmark(source)["cases"][0]["gold_answer_spans"] == ["span một", "span hai"]


def test_write_csv_preserves_list_as_json(tmp_path):
    output = tmp_path / "results.csv"
    write_csv(output, [{"id": "R01", "keys": ["chunk-1"]}])
    assert '""chunk-1""' in output.read_text(encoding="utf-8-sig")
