from __future__ import annotations

import argparse
import asyncio
import os
import re
import unicodedata
from pathlib import Path

import ir_measures
from ir_measures import P, R, Qrel, ScoredDoc
from sqlalchemy import or_, select

from app.databases.models import Document, DocumentChunk, DocumentVersion
from app.databases.session import AsyncSessionLocal
from app.retrieval.s4_dense_retriever import retrieve_child_chunks
from app.retrieval.s5_sparse_retriever import search_sparse_documents
from app.retrieval.s6_fusion import reciprocal_rank_fusion
from app.retrieval.s7_hydration import hydrate_langchain_documents
from app.retrieval.s8_reranker import JinaReranker
from test.benchmarks.common import input_path, load_benchmark, summary_chart, write_csv, write_json


MEASURES = [P@5, R@5]


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


async def gold_keys(session, case: dict) -> list[str]:
    expected = case.get("expected", case)
    document_key = expected.get("document_key", expected.get("expected_document_key"))
    version_key = expected.get("version_key", expected.get("expected_version_key"))
    if not document_key or not version_key:
        raise RuntimeError(f"{case['id']}: thiếu expected document/version key.")
    first, last = expected["page_hint"]
    spans = expected.get("gold_answer_spans")
    if not isinstance(spans, list) or not spans or not all(isinstance(span, str) and span.strip() for span in spans):
        raise RuntimeError(f"{case['id']}: gold_answer_spans phải là danh sách đoạn đáp án không rỗng.")
    rows = (await session.execute(select(DocumentChunk).join(DocumentVersion).join(Document).where(Document.document_key == document_key, DocumentVersion.version_key == version_key, DocumentChunk.chunk_type == "child", or_(DocumentChunk.page_start.is_(None), DocumentChunk.page_start <= last), or_(DocumentChunk.page_end.is_(None), DocumentChunk.page_end >= first)))).scalars().all()
    normalized_rows = [(row, normalized(row.content)) for row in rows]
    resolved: list[str] = []
    for span in spans:
        needle = normalized(span)
        matches = [(row, content) for row, content in normalized_rows if needle in content]
        if not matches:
            raise RuntimeError(f"{case['id']}: không resolve được gold_answer_span {span!r} trong {document_key}/{version_key}, trang {first}-{last}.")
        # Span exact match: chunk ngắn nhất chứa span là vị trí evidence cụ thể nhất.
        best_row, _ = min(matches, key=lambda item: (len(item[1]), item[0].chunk_index))
        if best_row.chunk_key not in resolved:
            resolved.append(best_row.chunk_key)
    return resolved


async def direct_hits(session, query: str, config: str):
    dense = lambda: asyncio.to_thread(retrieve_child_chunks, query, top_k=20, audience="sinh_vien")
    sparse = lambda: search_sparse_documents(session, query=query, top_k=20, audience="sinh_vien")
    if config == "dense_only":
        docs = await dense()
    elif config == "sparse_only":
        docs = await sparse()
    else:
        dense_docs, sparse_docs = await asyncio.gather(dense(), sparse())
        docs = reciprocal_rank_fusion(dense_docs, sparse_docs, limit=20)
    hits = await hydrate_langchain_documents(session, docs, expansion_reason="direct_hit")
    if config == "hybrid_rrf_jina":
        key = os.getenv("JINA_API_KEY", "").strip()
        if not key:
            raise RuntimeError("hybrid_rrf_jina cần JINA_API_KEY; không dùng identity fallback để benchmark.")
        hits = await asyncio.to_thread(JinaReranker(api_key=key).rerank, query, hits)
    return hits[:5]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    source = input_path("ct239h_retrieval_benchmark_30.json", args.input)
    output_dir = Path(args.output_dir) if args.output_dir else source.parent
    payload = load_benchmark(source)
    configs = ["dense_only", "sparse_only", "hybrid_rrf", "hybrid_rrf_jina"]
    results = {
        "benchmark": source.stem,
        "input": str(source),
        "configs": {},
    }
    async with AsyncSessionLocal() as session:
        for case in payload["cases"]:
            case["resolved_gold_chunk_keys"] = await gold_keys(session, case)
        for config in configs:
            qrels, run, cases = [], [], []
            for case in payload["cases"]:
                query_id = case["id"]
                gold = case["resolved_gold_chunk_keys"]
                hits = await direct_hits(session, case.get("query", case["question"]), config)
                qrels.extend(Qrel(query_id, key, 1) for key in gold)
                run.extend(ScoredDoc(query_id, hit.chunk_key, hit.score) for hit in hits)
                actual = [{"rank": index, "chunk_key": hit.chunk_key, "document_key": hit.document_key, "version_key": hit.version_key, "score": hit.score, "page_start": hit.page_start, "page_end": hit.page_end} for index, hit in enumerate(hits, 1)]
                found = [item["chunk_key"] for item in actual]
                cases.append({"id": query_id, "expected": {"document_key": case.get("expected_document_key", case.get("expected", {}).get("document_key")), "version_key": case.get("expected_version_key", case.get("expected", {}).get("version_key")), "page_hint": case.get("page_hint", case.get("expected", {}).get("page_hint")), "gold_answer_spans": case.get("gold_answer_spans", case.get("expected", {}).get("gold_answer_spans")), "resolved_gold_chunk_keys": gold}, "actual": actual, "precision_at_5": len(set(found) & set(gold)) / 5, "recall_at_5": len(set(found) & set(gold)) / len(gold), "reciprocal_rank": next((1 / rank for rank, key in enumerate(found, 1) if key in set(gold)), 0.0)})
            aggregate = ir_measures.calc_aggregate(MEASURES, qrels, run)
            results["configs"][config] = {"precision_at_5": aggregate[P@5], "recall_at_5": aggregate[R@5], "mrr": sum(case["reciprocal_rank"] for case in cases) / len(cases), "cases": cases}
    chart_metrics = {f"{name} P@5": item["precision_at_5"] for name, item in results["configs"].items()} | {f"{name} Recall@5": item["recall_at_5"] for name, item in results["configs"].items()} | {f"{name} MRR": item["mrr"] for name, item in results["configs"].items()}
    write_json(output_dir / "ct239h_retrieval_results.json", results)
    write_csv(output_dir / "ct239h_retrieval_results.csv", [{"configuration": config, "id": case["id"], "document_key": case["expected"]["document_key"], "version_key": case["expected"]["version_key"], "page_hint": case["expected"]["page_hint"], "gold_answer_spans": case["expected"]["gold_answer_spans"], "resolved_gold_chunk_keys": case["expected"]["resolved_gold_chunk_keys"], "actual_top5": case["actual"], "precision_at_5": case["precision_at_5"], "recall_at_5": case["recall_at_5"], "reciprocal_rank": case["reciprocal_rank"]} for config, data in results["configs"].items() for case in data["cases"]])
    summary_chart(output_dir / "ct239h_retrieval_summary.png", "CT239H Retrieval Benchmark", chart_metrics)


if __name__ == "__main__":
    asyncio.run(main())
