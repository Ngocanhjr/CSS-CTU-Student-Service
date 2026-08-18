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
    """Normalize nội dung nhưng vẫn giữ nguyên Markdown syntax."""
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", text).casefold(),
    ).strip()


def normalized_markdown(text: str) -> str:
    """
    Normalize chỉ phần trình bày Markdown để resolve gold span.

    Không paraphrase, không fuzzy match và không thay đổi nội dung ngữ nghĩa.
    """
    text = unicodedata.normalize("NFKC", text).casefold()

    # Heading:
    # #### Điều 2. -> Điều 2.
    # ## do có chứng chỉ... -> do có chứng chỉ...
    text = re.sub(
        r"(?m)^\s{0,3}#{1,6}[ \t]+",
        "",
        text,
    )

    # Markdown escapes:
    # \* -> *
    # \+ -> +
    # \- -> -
    text = re.sub(
        r"\\([\\`*{}\[\]()#+\-.!_>])",
        r"\1",
        text,
    )

    # Strong emphasis:
    # **text** -> text
    # __text__ -> text
    text = text.replace("**", "")
    text = text.replace("__", "")

    # Bỏ marker danh sách ở đầu dòng.
    # Ví dụ:
    # - + Số tín chỉ... -> Số tín chỉ...
    # * Lưu ý...        -> Lưu ý...
    #
    # Chỉ bỏ marker trình bày đầu dòng, không xóa dấu +-* trong nội dung.
    text = re.sub(
        r"(?m)^\s*(?:[-+*]\s+)+",
        "",
        text,
    )

    return re.sub(r"\s+", " ", text).strip()


async def gold_keys(session, case: dict) -> list[str]:
    expected = case.get("expected", case)

    document_key = expected.get(
        "document_key",
        expected.get("expected_document_key"),
    )
    version_key = expected.get(
        "version_key",
        expected.get("expected_version_key"),
    )

    if not document_key or not version_key:
        raise RuntimeError(
            f"{case['id']}: thiếu expected document/version key."
        )

    first, last = expected["page_hint"]

    spans = expected.get("gold_answer_spans")
    if (
        not isinstance(spans, list)
        or not spans
        or not all(
            isinstance(span, str) and span.strip()
            for span in spans
        )
    ):
        raise RuntimeError(
            f"{case['id']}: gold_answer_spans phải là "
            "danh sách đoạn đáp án không rỗng."
        )

    rows = (
        await session.execute(
            select(DocumentChunk)
            .join(DocumentVersion)
            .join(Document)
            .where(
                Document.document_key == document_key,
                DocumentVersion.version_key == version_key,
                DocumentChunk.chunk_type == "child",
                or_(
                    DocumentChunk.page_start.is_(None),
                    DocumentChunk.page_start <= last,
                ),
                or_(
                    DocumentChunk.page_end.is_(None),
                    DocumentChunk.page_end >= first,
                ),
            )
        )
    ).scalars().all()

    # Chuẩn bị nhiều representation cho mỗi child chunk.
    #
    # content_exact:
    #   Nội dung chunk nguyên bản, chỉ normalize Unicode/whitespace.
    #
    # content_markdown:
    #   Nội dung chunk đã bỏ Markdown presentation.
    #
    # contextual_markdown:
    #   heading_path + content.
    #   Cần thiết khi heading nằm trong heading_path thay vì content.
    normalized_rows = []

    for row in rows:
        content = row.content or ""

        content_exact = normalized(content)
        content_markdown = normalized_markdown(content)

        heading_path = row.heading_path or []

        contextual_text = "\n".join(
            [
                *heading_path,
                content,
            ]
        )

        contextual_markdown = normalized_markdown(
            contextual_text
        )

        normalized_rows.append(
            {
                "row": row,
                "content_exact": content_exact,
                "content_markdown": content_markdown,
                "contextual_markdown": contextual_markdown,
            }
        )

    resolved: list[str] = []

    for span in spans:
        # --------------------------------------------------
        # Tier 1: exact normalized match
        # --------------------------------------------------
        #
        # Ưu tiên tuyệt đối vì đây là trường hợp gold span
        # thực sự xuất hiện trong child content.
        exact_needle = normalized(span)

        exact_matches = [
            item
            for item in normalized_rows
            if exact_needle in item["content_exact"]
        ]

        if exact_matches:
            best = min(
                exact_matches,
                key=lambda item: (
                    len(item["content_exact"]),
                    item["row"].chunk_index,
                ),
            )

            best_row = best["row"]

            if best_row.chunk_key not in resolved:
                resolved.append(best_row.chunk_key)

            continue

        # --------------------------------------------------
        # Tier 2: Markdown-presentation normalized match
        # --------------------------------------------------
        #
        # Chỉ dùng khi exact match thất bại.
        #
        # Có thể match:
        # - canonical span với #### nhưng chunk không có ####
        # - **text** với text
        # - \* / \+ với marker đã được chunker xử lý
        # - heading nằm trong heading_path thay vì content
        markdown_needle = normalized_markdown(span)

        markdown_matches = [
            item
            for item in normalized_rows
            if (
                markdown_needle in item["content_markdown"]
                or
                markdown_needle
                in item["contextual_markdown"]
            )
        ]

        if not markdown_matches:
            print("\n" + "=" * 100)
            print(f"DEBUG GOLD RESOLUTION: {case['id']}")
            print(f"SPAN RAW: {span!r}")
            print(f"SPAN NORMALIZED: {normalized(span)!r}")
            print(
                "SPAN MARKDOWN NORMALIZED:",
                repr(normalized_markdown(span)),
            )

            print(f"\nCANDIDATE CHILD CHUNKS ({len(rows)}):")

            for item in normalized_rows:
                row = item["row"]

                print("\n---")
                print("chunk_key:", row.chunk_key)
                print("chunk_index:", row.chunk_index)
                print("page:", row.page_start, "-", row.page_end)
                print("heading_path:", row.heading_path)
                print("content RAW:", repr(row.content))
                print(
                    "content_markdown:",
                    repr(item["content_markdown"]),
                )
                print(
                    "contextual_markdown:",
                    repr(item["contextual_markdown"]),
                )

            print("=" * 100 + "\n")

                
            raise RuntimeError(
                f"{case['id']}: không resolve được "
                f"gold_answer_span {span!r} trong "
                f"{document_key}/{version_key}, "
                f"trang {first}-{last}."
            )

        # Chọn child chunk ngắn nhất chứa evidence.
        # Không dùng fuzzy score.
        best = min(
            markdown_matches,
            key=lambda item: (
                len(item["content_exact"]),
                item["row"].chunk_index,
            ),
        )

        best_row = best["row"]

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
