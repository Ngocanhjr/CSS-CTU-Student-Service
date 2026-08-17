from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import httpx
import numpy as np
from test.benchmarks.common import citation_precision, input_path, load_benchmark, no_answer_correct, summary_chart, write_csv, write_json


async def run_case(client: httpx.AsyncClient, case: dict) -> dict:
    started = time.perf_counter()
    response = await client.post("/api/v1/rag/answer", json={"question": case["question"], "top_k": 5})
    latency = time.perf_counter() - started
    response.raise_for_status()
    payload = response.json()
    return {"id": case["id"], "question": case["question"], "answerable": case["answerable"], "reference_facts": case["reference_facts"], "expected_document_keys": case["expected_document_keys"], "response": payload, "http_status": response.status_code, "response_latency_seconds": latency, "citation_precision": citation_precision(payload["citations"], case["expected_document_keys"], answerable=case["answerable"]), "no_answer_correct": (not case["answerable"] and no_answer_correct(payload)), "answer_correctness": None, "faithfulness": None}


def ragas_scores(rows: list[dict]) -> None:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_correctness, faithfulness
    # Citation text is stable public context. Full PostgreSQL content intentionally stays server-side.
    answerable_rows = [row for row in rows if row["answerable"]]
    dataset = Dataset.from_dict({"question": [row["question"] for row in answerable_rows], "answer": [row["response"]["answer"] for row in answerable_rows], "contexts": [[citation["citation"] for citation in row["response"]["citations"]] for row in answerable_rows], "ground_truth": ["\n".join(row["reference_facts"]) for row in answerable_rows]})
    table = evaluate(dataset, metrics=[faithfulness, answer_correctness]).to_pandas()
    for row, (_, score) in zip(answerable_rows, table.iterrows()):
        row["answer_correctness"] = float(score["answer_correctness"])
        row["faithfulness"] = float(score["faithfulness"])


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    source = input_path("ct239h_end_to_end_10.json", args.input)
    output_dir = Path(args.output_dir) if args.output_dir else source.parent
    payload = load_benchmark(source)
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=180) as client:
        rows = [await run_case(client, case) for case in payload["cases"]]
    ragas_scores(rows)
    latencies = [row["response_latency_seconds"] for row in rows]
    answerable_rows = [row for row in rows if row["answerable"]]
    scores = {"answer_correctness": float(np.mean([row["answer_correctness"] for row in answerable_rows])), "faithfulness": float(np.mean([row["faithfulness"] for row in answerable_rows])), "citation_precision": float(np.mean([row["citation_precision"] for row in answerable_rows])), "no_answer_accuracy": float(np.mean([row["no_answer_correct"] for row in rows if not row["answerable"]])), "mean_latency_seconds": float(np.mean(latencies)), "p95_latency_seconds": float(np.quantile(latencies, 0.95))}
    cases = [{"id": row["id"], "input": {"question": row["question"]}, "expected": {"answerable": row["answerable"], "document_keys": row["expected_document_keys"], "reference_facts": row["reference_facts"], "expected_behavior": row.get("expected_behavior") or (None if row["answerable"] else "abstain_or_no_context_without_fabricated_citation")}, "actual": {"http_status": row["http_status"], "should_search": row["response"]["should_search"], "answer_status": row["response"].get("answer_status"), "answer": row["response"]["answer"], "citations": row["response"]["citations"], "response_latency_seconds": row["response_latency_seconds"], "answer_correctness": row["answer_correctness"], "faithfulness": row["faithfulness"], "citation_precision": row["citation_precision"], "no_answer_correct": None if row["answerable"] else row["no_answer_correct"], "notes": None}} for row in rows]
    result = {"meta": {"name": "CT239H End-to-End RAG Results", "source_test_file": source.name, "note": "Run the production RAG pipeline. Expected fields are fixed before execution; actual fields are produced by the benchmark runner."}, "summary": scores, "cases": cases}
    write_json(output_dir / "ct239h_e2e_results.json", result)
    write_csv(output_dir / "ct239h_e2e_results.csv", [{"id": case["id"], "question": case["input"]["question"], "answerable": case["expected"]["answerable"], "expected_document_keys": case["expected"]["document_keys"], "reference_facts": case["expected"]["reference_facts"], "expected_behavior": case["expected"]["expected_behavior"], **case["actual"]} for case in cases])
    summary_chart(output_dir / "ct239h_e2e_summary.png", "CT239H End-to-End RAG Evaluation", scores, seconds={"mean_latency_seconds", "p95_latency_seconds"})


if __name__ == "__main__":
    asyncio.run(main())
